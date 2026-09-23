"""What JARVIS says when woken from rest: greeting, weather, calendar, projects, to-dos."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from app.memory.store import MemoryStore
from app.tools import weather

log = logging.getLogger("jarvis.routines")


def greeting(now: datetime, name: str) -> str:
    part = "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening"
    return f"Hey, hi {name}! Good {part}."


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build_briefing(
    name: str,
    city: str,
    memory: MemoryStore,
    projects: Callable[[], list[str]],
    meetings: Callable[[], list[str]] | None = None,
    now: Callable[[], datetime] = datetime.now,
) -> str:
    parts = [greeting(now(), name)]
    try:
        parts.append("Today's weather: " + weather.describe(weather.today(city)))
    except Exception as exc:
        log.warning("Briefing weather failed: %s", exc)
        parts.append("I couldn't get the weather right now.")
    if meetings is None:
        parts.append("I can't see your meetings yet; once your Google account is connected, I'll read them to you.")
    else:
        try:
            today_meetings = meetings()
        except Exception as exc:
            log.warning("Briefing calendar failed: %s", exc)
            today_meetings = []
            parts.append("I couldn't reach your calendar just now.")
        if today_meetings:
            parts.append(f"You have {len(today_meetings)} meeting{'s' if len(today_meetings) > 1 else ''} today: "
                         + _join(today_meetings[:3]) + ".")
        else:
            parts.append("No meetings in your calendar today.")
    try:
        names = projects()[:4]
    except Exception:
        names = []
    if names:
        parts.append(f"Your recent projects are {_join(names)}.")
    end_of_day = now().replace(hour=23, minute=59, second=59)
    today = memory.upcoming_reminders(until=end_of_day)
    if today:
        items = [f"{r['text']} at {r['due']:%I:%M %p}".replace(" 0", " ") for r in today[:3]]
        parts.append(f"You have {len(today)} reminder{'s' if len(today) > 1 else ''} today: {_join(items)}.")
    todos = [text for _, text in memory.open_todos()]
    if todos:
        parts.append(f"Still open from before: {_join(todos[:3])}" + (f", and {len(todos) - 3} more." if len(todos) > 3 else "."))
    parts.append("What's on your to-do list for today?")
    return " ".join(parts)
