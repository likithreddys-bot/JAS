from datetime import datetime

import pytest

from app.core.events.events import WakeWordDetected
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.memory.store import MemoryStore
from app.routines import briefing
from app.tools import weather
from app.voice import quick
from app.wellbeing import ActivityMonitor

REPORT = {"city": "Bengaluru", "now_celsius": 25, "feels_like_celsius": 27, "now": "overcast skies",
          "high_celsius": 28, "low_celsius": 21, "rain_chance_percent": 80, "today": "showers"}


@pytest.fixture
def memory(tmp_path):
    return MemoryStore(tmp_path / "memory.db")


def test_briefing_greets_by_name_with_weather_projects_and_todos(memory, monkeypatch):
    monkeypatch.setattr(weather, "today", lambda city: REPORT)
    memory.add_todo("finish the BERT model")
    text = briefing.build_briefing("Likki", "Bengaluru", memory, lambda: ["AI-Tester", "JARVIS"],
                                   now=lambda: datetime(2026, 9, 23, 8, 30))
    assert text.startswith("Hey, hi Likki! Good morning.")
    assert "In Bengaluru it's 25 degrees with overcast skies, with a high of 28 today" in text
    assert "80 percent chance of rain" in text
    assert "can't see your meetings yet" in text  # honest until Google is connected
    assert "AI-Tester and JARVIS" in text and "finish the BERT model" in text
    assert text.endswith("What's on your to-do list for today?")


def test_briefing_survives_weather_failure(memory, monkeypatch):
    def offline(city):
        raise OSError("no internet")

    monkeypatch.setattr(weather, "today", offline)
    text = briefing.build_briefing("Likki", "Bengaluru", memory, lambda: [], now=lambda: datetime(2026, 9, 23, 19, 0))
    assert "Good evening" in text and "couldn't get the weather" in text


def test_go_offline_is_an_instant_command():
    for said in ["Go offline", "Jarvis, go to sleep", "take rest", "rest mode"]:
        assert quick.match(said)[0] == "go_offline"


def test_rest_and_wake_transitions():
    core = Jarvis()
    core.start(resting=True)
    assert core.state.current is S.RESTING
    core.bus.publish(WakeWordDetected(0.9))
    assert core.state.current is S.WAKE_DETECTED  # woken from rest (the pipeline gives the briefing)


def test_announcements_only_when_idle():
    core = Jarvis()
    core.start()
    assert core.announce("Take a break")
    assert core.state.current is S.WAKE_DETECTED and core.announcement == "Take a break"
    core.state.transition(S.LISTENING)
    assert not core.announce("again")  # busy -> no interruption


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_break_reminder_after_continuous_use_and_reset_by_a_break():
    core = Jarvis()
    core.start()
    clock, idle = FakeClock(), {"s": 0.0}
    monitor = ActivityMonitor(core, "Likki", break_minutes=90, idle=lambda: idle["s"], clock=clock)
    for _ in range(89 * 4):  # 89 minutes of use, one tick every 15 s
        clock.now += 15
        monitor.tick()
    assert core.state.current is S.STANDBY  # not yet
    idle["s"] = 400  # a 6-minute break resets the count
    monitor.tick()
    idle["s"] = 0
    for _ in range(60 * 4):
        clock.now += 15
        monitor.tick()
    assert core.state.current is S.STANDBY  # only 60 min since the break
    for _ in range(31 * 4):
        clock.now += 15
        monitor.tick()
    assert core.state.current is S.WAKE_DETECTED
    assert core.announcement.startswith("Likki, your screen time is high")


def test_laptop_waking_from_sleep_puts_jarvis_to_rest():
    core = Jarvis()
    core.start()
    clock = FakeClock()
    monitor = ActivityMonitor(core, "Likki", break_minutes=90, idle=lambda: 0.0, clock=clock)
    clock.now += 3600  # an hour passes between two ticks: the laptop was asleep
    monitor.tick()
    assert core.state.current is S.RESTING
