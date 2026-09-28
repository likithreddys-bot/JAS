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


# --- retry (Phase 11: recovery) ----------------------------------------------

def test_a_low_risk_crash_is_retried_once_and_can_then_succeed():
    """A crash - a stale window handle, a COM call made too soon - deserves one more try before
    it becomes the LLM's problem to improvise around."""
    calls = []

    def flaky(text):
        calls.append(text)
        if len(calls) == 1:
            raise OSError("not ready yet")
        return ToolResult(True, {"echo": text})

    result = ToolExecutor(thinking_core(), [make_tool(run=flaky)]).run("echo", {"text": "x"})
    assert result == {"ok": True, "echo": "x"}
    assert calls == ["x", "x"], "exactly one retry, not zero and not more"


def test_an_ordinary_false_result_is_never_retried():
    """A tool that deliberately returns ok=False - "nothing found", "nothing to do" - gave a clean,
    deterministic answer that will not have changed an instant later. Retrying it would only double
    the cost of every routine miss from a vision or COM call, for no benefit at all."""
    calls = []

    def clean_miss(text):
        calls.append(text)
        return ToolResult(False, error="I can't see that on screen")

    result = ToolExecutor(thinking_core(), [make_tool(run=clean_miss)]).run("echo", {"text": "x"})
    assert result == {"ok": False, "error": "I can't see that on screen"}
    assert len(calls) == 1, "a deliberate 'no' is not a crash and must not be retried"


def test_a_crash_that_will_not_fix_itself_still_ends_as_one_error():
    """If the retry crashes too, the caller sees one clean failure - not two, not a raised exception."""
    calls = []

    def always_crashes(text):
        calls.append(text)
        raise OSError("disk on fire")

    result = ToolExecutor(thinking_core(), [make_tool(run=always_crashes)]).run("echo", {"text": "x"})
    assert result == {"ok": False, "error": "OSError: disk on fire"}
    assert len(calls) == 2, "one original attempt plus exactly one retry"


def test_only_one_step_is_shown_for_a_retried_tool():
    """The retry is an internal recovery detail - the UI checklist must show one step, not two,
    or a single command would visibly appear to run itself twice."""
    core = thinking_core()
    events = collect(core, ToolStarted, ToolFinished)
    calls = []

    def flaky(text):
        calls.append(text)
        if len(calls) == 1:
            raise OSError("nope")
        return ToolResult(True)

    ToolExecutor(core, [make_tool(run=flaky)]).run("echo", {"text": "x"})
    assert len(events) == 2, "one ToolStarted, one ToolFinished - never two of either"
    assert isinstance(events[0], ToolStarted) and isinstance(events[1], ToolFinished)
    assert events[1].ok is True


@pytest.mark.parametrize("risk", [Risk.MEDIUM, Risk.HIGH])
def test_medium_and_high_risk_crashes_are_never_retried(risk):
    """These already asked for and received the user's confirmation once. Silently repeating a
    consequential action they were never asked to repeat could mean doing it twice - a tool that
    half-sent a message must not risk sending it again on our own initiative."""
    calls = []

    def crashes_once_then_would_succeed(text):
        calls.append(text)
        if len(calls) == 1:
            raise OSError("nope")
        return ToolResult(True)

    executor = ToolExecutor(thinking_core(), [make_tool(risk=risk, run=crashes_once_then_would_succeed)])
    executor.set_confirmer(lambda q: True)
    result = executor.run("echo", {"text": "x"})
    assert result["ok"] is False
    assert len(calls) == 1, "no retry - even though a second attempt here would have succeeded"


def test_pausing_between_the_crash_and_the_retry_cancels_instead_of_retrying():
    """The retry re-checks cancellation - a pause landing in that gap must stop the task, not
    barrel through with one more attempt regardless."""
    core = thinking_core()

    def crash_then_pause(text):
        core.pause()
        raise OSError("nope")

    with pytest.raises(TaskCancelled):
        ToolExecutor(core, [make_tool(run=crash_then_pause)]).run("echo", {"text": "x"})


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


def test_win_l_is_refused_instead_of_silently_doing_nothing():
    """Windows ignores synthetic Win+L, so press_keys must not report success for it."""
    from app.tools.computer import computer_tools
    from app.tools.computer.apps import AppIndex

    tools = {t.name: t for t in computer_tools(AppIndex())}
    result = tools["press_keys"].run(keys="windows+l")
    assert not result.ok
    assert "lock_pc" in result.error

    assert not tools["press_keys"].run(keys="ctrl+alt+delete").ok


def test_lock_pc_reports_failure_when_the_screen_did_not_lock(monkeypatch):
    from app.tools.computer import computer_tools, session
    from app.tools.computer.apps import AppIndex

    tools = {t.name: t for t in computer_tools(AppIndex())}
    monkeypatch.setattr(session, "lock", lambda: False)
    assert not tools["lock_pc"].run().ok

    monkeypatch.setattr(session, "lock", lambda: True)
    assert tools["lock_pc"].run().data == {"locked": True}


def test_the_session_is_not_locked_while_these_tests_run():
    """is_locked() is what makes lock_pc honest, so check it against reality."""
    from app.tools.computer import session

    assert session.is_locked() is False
