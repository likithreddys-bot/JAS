import pytest

from app.config import env_file
from app.config.settings import Settings
from app.core.events.events import AssistantReply, ToolFinished, TranscriptReady, WakeWordDetected
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.memory.store import MemoryStore
from ui.activity import ActivityLog
from ui.dashboard import EDITABLE, DashboardBridge
from ui.hotkey import parse_shortcut

ENV = """# JARVIS settings
USER_NAME=Likki
HOME_CITY=Bengaluru

# --- voice ---
TTS_SPEED=1.0
"""


def test_env_values_are_updated_in_place_keeping_comments(tmp_path):
    env = tmp_path / ".env"
    env.write_text(ENV, encoding="utf-8")
    changed = env_file.update_values(env, {"HOME_CITY": "Hyderabad", "TTS_SPEED": "1.0", "HOTKEY": "ctrl+alt+j"})
    assert sorted(changed) == ["HOME_CITY", "HOTKEY"]  # unchanged values are left alone
    text = env.read_text(encoding="utf-8")
    assert "# JARVIS settings" in text and "# --- voice ---" in text
    assert "HOME_CITY=Hyderabad" in text and "USER_NAME=Likki" in text
    assert text.index("USER_NAME") < text.index("HOME_CITY") < text.index("TTS_SPEED")  # order kept
    assert "HOTKEY=ctrl+alt+j" in text  # new keys appended
    assert env_file.read_values(env)["HOME_CITY"] == "Hyderabad"


def test_activity_log_records_the_conversation():
    core = Jarvis()
    activity = ActivityLog(core.bus)
    core.start()
    core.bus.publish(WakeWordDetected(0.9))
    core.bus.publish(TranscriptReady("open notepad"))
    core.bus.publish(ToolFinished(1, "Opening notepad", True))
    core.bus.publish(AssistantReply("Done,"))
    core.bus.publish(AssistantReply("Done, Notepad is open."))  # replies grow sentence by sentence
    entries = activity.entries()
    assert [e["text"] for e in entries] == [
        "Done, Notepad is open.", "Opening notepad", "“open notepad”", "Wake word heard"]  # newest first
    assert activity.requests_today == 1 and activity.actions_today == 1


def test_failed_actions_and_errors_are_shown():
    core = Jarvis()
    activity = ActivityLog(core.bus)
    core.start()
    core.bus.publish(ToolFinished(1, "Opening Photoshop", False, "No installed app matches 'photoshop'."))
    core.state.transition(S.ERROR, "Microphone unavailable")
    texts = [e["text"] for e in activity.entries()]
    assert "Microphone unavailable" in texts
    assert "Opening Photoshop — No installed app matches 'photoshop'." in texts


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(ENV, encoding="utf-8")
    settings = Settings(_env_file=None)
    monkeypatch.setitem(settings.model_config, "env_file", env)
    core = Jarvis()
    memory = MemoryStore(tmp_path / "memory.db")
    activity = ActivityLog(core.bus)
    core.start()
    return DashboardBridge(core, memory, activity, settings, lambda: ["Standup at 10:00"], lambda: True), core, memory


def test_status_summarises_jarvis(dashboard):
    bridge, core, memory = dashboard
    memory.remember("Likki likes short answers")
    memory.add_todo("finish the BERT model")
    bridge.refresh()
    status = bridge.status
    assert status["state"] == "Ready" and status["facts"] == 1 and status["todos"] == 1
    assert status["cpu"].endswith("%") and status["ram"].endswith("MB")
    assert [s["name"] for s in status["services"]][:2] == ["AI brain (gemini)", "Google Calendar & Gmail"]
    assert next(s for s in status["services"] if s["name"].startswith("Google"))["ok"] is True


def test_settings_tab_lists_current_values_and_saves(dashboard):
    bridge, _, _ = dashboard
    values = {row["key"]: row["value"] for row in bridge.settingsList}
    assert set(values) == {key for key, _, _ in EDITABLE}
    assert values["HOME_CITY"] == "Bengaluru" and values["HOTKEY"] == "ctrl+space"  # falls back to the default

    messages = []
    bridge.savedMessage.connect(messages.append)
    bridge.save({"HOME_CITY": "Hyderabad", "HOTKEY": "ctrl+alt+j"})
    assert "Saved 2 settings" in messages[-1] and "Restart JARVIS to apply" in messages[-1]
    assert {r["key"]: r["value"] for r in bridge.settingsList}["HOME_CITY"] == "Hyderabad"
    bridge.save({"HOME_CITY": "Hyderabad"})
    assert messages[-1] == "Nothing changed."


def test_typed_request_wakes_jarvis(dashboard):
    bridge, core, _ = dashboard
    bridge.ask("what's the weather?")
    assert core.state.current is S.WAKE_DETECTED and core.typed_request == "what's the weather?"


@pytest.mark.parametrize("shortcut, expected", [
    ("ctrl+space", (0x0002, 0x20)),
    ("Ctrl + Alt + J", (0x0003, ord("J"))),
    ("win+f2", (0x0008, 0x71)),
])
def test_shortcuts_are_parsed(shortcut, expected):
    assert parse_shortcut(shortcut) == expected


@pytest.mark.parametrize("bad", ["", "ctrl+", "meta+space", "ctrl+banana"])
def test_bad_shortcuts_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_shortcut(bad)
