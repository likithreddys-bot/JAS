import pytest

from app.core.events.events import StateChanged, ToolFinished, ToolStarted
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.tools.base import Risk, TaskCancelled, Tool, ToolResult
from app.tools.computer import apps, keyboard, windows
from app.tools.executor import ToolExecutor


def make_tool(name="echo", risk=Risk.LOW, run=None):
    return Tool(
        name=name,
        description="test tool",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        run=run or (lambda text: ToolResult(True, {"echo": text})),
        label=lambda text: f"Echo {text}",
        risk=risk,
        confirm_question=lambda text: f"Echo {text}?",
    )


def thinking_core():
    core = Jarvis()
    core.start()
    for s in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING):
        core.state.transition(s)
    return core


def collect(core, *types):
    events = []
    for t in types:
        core.bus.subscribe(t, events.append)
    return events


# --- executor ---------------------------------------------------------------

def test_low_risk_tool_runs_and_reports_steps_and_states():
    core = thinking_core()
    events = collect(core, ToolStarted, ToolFinished, StateChanged)
    result = ToolExecutor(core, [make_tool()]).run("echo", {"text": "hi"})
    assert result == {"ok": True, "echo": "hi"}
    assert [type(e).__name__ for e in events] == ["StateChanged", "ToolStarted", "ToolFinished", "StateChanged"]
    assert events[0].current is S.EXECUTING and events[-1].current is S.OBSERVING
    assert events[1].label == "Echo hi" and events[2].ok


@pytest.mark.parametrize("args, problem", [
    ({}, "missing 'text'"),
    ({"text": 5}, "'text' must be string"),
    ({"text": "a", "extra": 1}, "unexpected 'extra'"),
])
def test_invalid_arguments_are_rejected_without_running(args, problem):
    ran = []
    tool = make_tool(run=lambda text: ran.append(text) or ToolResult(True))
    result = ToolExecutor(thinking_core(), [tool]).run("echo", args)
    assert result == {"ok": False, "error": f"Invalid arguments: {problem}"} and ran == []


def test_unknown_tool():
    assert ToolExecutor(thinking_core(), []).run("format_disk", {})["ok"] is False


def test_medium_risk_needs_confirmation():
    core = thinking_core()
    ran = []
    tool = make_tool(risk=Risk.MEDIUM, run=lambda text: ran.append(text) or ToolResult(True))
    executor = ToolExecutor(core, [tool])
    asked = []

    executor.set_confirmer(lambda q: asked.append(q) or False)
    result = executor.run("echo", {"text": "x"})
    assert result["ok"] is False and result["declined_by_user"] is True
    assert ran == [] and asked == ["Echo x?"]

    executor.set_confirmer(lambda q: True)
    assert executor.run("echo", {"text": "y"})["ok"] and ran == ["y"]


def test_medium_risk_without_a_way_to_ask_is_refused():
    tool = make_tool(risk=Risk.MEDIUM)
    assert ToolExecutor(thinking_core(), [tool]).run("echo", {"text": "x"})["ok"] is False


def test_paused_task_is_cancelled_before_running():
    core = thinking_core()
    core.pause()
    with pytest.raises(TaskCancelled):
        ToolExecutor(core, [make_tool()]).run("echo", {"text": "x"})


def test_crashing_tool_becomes_an_error_result():
    def boom(text):
        raise OSError("disk on fire")

    result = ToolExecutor(thinking_core(), [make_tool(run=boom)]).run("echo", {"text": "x"})
    assert result == {"ok": False, "error": "OSError: disk on fire"}


# --- keyboard ---------------------------------------------------------------

def test_key_combos_parse_and_flag_danger():
    assert keyboard.parse_combo("Ctrl + S") == ("ctrl", "s")
    assert keyboard.parse_combo("volume up") == ("volumeup",)
    assert keyboard.parse_combo("media_play_pause") == ("playpause",)
    assert keyboard.parse_combo("Volume_Up") == ("volumeup",)
    assert keyboard.parse_combo("media next track") == ("nexttrack",)
    assert keyboard.is_dangerous(keyboard.parse_combo("alt+f4"))
    assert not keyboard.is_dangerous(keyboard.parse_combo("ctrl+s"))
    with pytest.raises(ValueError):
        keyboard.parse_combo("ctrl+banana")


# --- app matching -----------------------------------------------------------

def index_with(*names):
    index = apps.AppIndex()
    index._apps = [apps.App(n, f"id-{n}") for n in names]
    return index


@pytest.mark.parametrize("spoken, expected", [
    ("notepad", "Notepad"),
    ("Chrome", "Google Chrome"),
    ("vs code", "Visual Studio Code"),
    ("whatsapp", "WhatsApp"),
    ("calculater", "Calculator"),  # speech-recognition typo
    ("word", "Word"),
])
def test_app_names_match_how_people_say_them(spoken, expected):
    index = index_with("Notepad", "Google Chrome", "Visual Studio Code", "WhatsApp", "Calculator", "WordPad", "Word")
    assert index.find(spoken).name == expected


@pytest.mark.parametrize("spoken", ["photoshop", "spotify", "notes app"])
def test_unknown_app_is_not_guessed(spoken):
    assert index_with("Notepad", "Calculator", "Photos", "Sticky Notes").find(spoken) is None


# --- real Windows API smoke test ---------------------------------------------

def test_window_listing_works_on_this_machine():
    listed = windows.list_windows()
    assert all(w.title for w in listed)
    assert all(w.hwnd for w in listed)


def test_interrupted_task_runs_no_more_tools():
    core = thinking_core()
    ran = []
    executor = ToolExecutor(core, [make_tool(run=lambda text: ran.append(text) or ToolResult(True))])
    core.cancelled.set()  # user said "Jarvis, stop"
    core.state.transition(S.STANDBY)
    core.state.transition(S.WAKE_DETECTED)  # ...and even if a new request has already begun
    with pytest.raises(TaskCancelled):
        executor.run("echo", {"text": "x"})
    assert ran == []
