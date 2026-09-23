from datetime import datetime, timedelta

import pytest

from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.memory.store import MemoryStore
from app.reminders import ReminderService
from app.tools.memory_tools import memory_tools, parse_when

NOW = datetime(2026, 9, 22, 17, 0)  # Tuesday 5 PM


@pytest.mark.parametrize("at, minutes, expected", [
    ("2026-09-22T18:00", 0, datetime(2026, 9, 22, 18, 0)),
    ("2026-09-23 09:30", 0, datetime(2026, 9, 23, 9, 30)),
    ("18:00", 0, datetime(2026, 9, 22, 18, 0)),
    ("6:30 pm", 0, datetime(2026, 9, 22, 18, 30)),
    ("9 AM", 0, datetime(2026, 9, 23, 9, 0)),  # 9 AM already passed today -> tomorrow
    ("", 20, datetime(2026, 9, 22, 17, 20)),
])
def test_times_are_understood(at, minutes, expected):
    assert parse_when(at, minutes, NOW) == expected


@pytest.mark.parametrize("at", ["2026-09-21T10:00", "", "whenever"])
def test_bad_or_past_times_are_rejected(at):
    with pytest.raises(ValueError):
        parse_when(at, 0, NOW)


@pytest.fixture
def memory(tmp_path):
    return MemoryStore(tmp_path / "memory.db")


def test_reminder_tools(memory):
    tools = {t.name: t for t in memory_tools(memory, "Bengaluru", now=lambda: NOW)}
    made = tools["create_reminder"].run(text="call Rahul", at="18:00")
    assert made.ok and made.data["when"] == "Tuesday 22 September, 06:00 PM"
    assert [r["text"] for r in tools["list_reminders"].run().data["reminders"]] == ["call Rahul"]
    assert tools["cancel_reminder"].run(match="rahul").data["cancelled"] == ["call Rahul"]
    assert tools["list_reminders"].run().data["reminders"] == []
    assert not tools["create_reminder"].run(text="x", at="yesterday").ok


def test_repeating_reminders_move_forward(memory):
    daily = memory.add_reminder("stand up", datetime(2026, 9, 22, 9, 0), "daily")
    weekdays = memory.add_reminder("standup meeting", datetime(2026, 9, 25, 10, 0), "weekdays")  # Friday
    memory.reminder_fired(daily, datetime(2026, 9, 22, 9, 0, 5))
    memory.reminder_fired(weekdays, datetime(2026, 9, 25, 10, 0, 5))
    due = {r["text"]: r["due"] for r in memory.upcoming_reminders()}
    assert due["stand up"] == datetime(2026, 9, 23, 9, 0)
    assert due["standup meeting"] == datetime(2026, 9, 28, 10, 0)  # skips the weekend to Monday


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def service(memory, clock, core=None):
    core = core or Jarvis()
    if core.state.current is S.STARTING:
        core.start()
    shown = []
    return core, shown, ReminderService(core, memory, "Likki", lambda title, text: shown.append((title, text)) or True, clock)


def test_reminder_is_notified_and_spoken_on_time(memory):
    clock = Clock(NOW)
    memory.add_reminder("call Rahul", NOW + timedelta(minutes=10))
    core, shown, reminders = service(memory, clock)
    reminders.tick()
    assert shown == []  # not yet
    clock.now = NOW + timedelta(minutes=10, seconds=3)
    reminders.tick()
    assert shown == [("\U0001f514 Reminder", "call Rahul")]
    assert core.state.current is S.WAKE_DETECTED and core.announcement == "Likki, reminder: call Rahul."
    reminders.tick()
    assert len(shown) == 1  # delivered once


def test_missed_reminders_are_delivered_at_startup(memory):
    memory.add_reminder("take medicine", NOW - timedelta(hours=2))
    core, shown, reminders = service(memory, Clock(NOW))
    reminders.tick()
    assert shown[0][0].startswith("\U0001f514 Reminder (missed")
    assert "while I was off" in core.announcement


def test_spoken_reminder_waits_until_jarvis_is_free(memory):
    core = Jarvis()
    core.start()
    for s in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING):
        core.state.transition(s)  # busy answering something
    memory.add_reminder("call Rahul", NOW)
    _, shown, reminders = service(memory, Clock(NOW), core)
    reminders.tick()
    assert len(shown) == 1 and core.announcement is None  # notification now, voice later
    core.state.transition(S.STANDBY)
    reminders.tick()
    assert core.announcement == "Likki, reminder: call Rahul."


def test_briefing_mentions_todays_reminders(memory, monkeypatch):
    from app.routines import briefing
    from app.tools import weather

    monkeypatch.setattr(weather, "today", lambda city: (_ for _ in ()).throw(OSError()))
    memory.add_reminder("call Rahul", datetime(2026, 9, 22, 18, 0))
    text = briefing.build_briefing("Likki", "Bengaluru", memory, lambda: [], now=lambda: NOW)
    assert "You have 1 reminder today: call Rahul at 6:00 PM." in text
