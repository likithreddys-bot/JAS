"""Delivers reminders on time: a Windows notification plus JARVIS saying it out loud.

Reminders live in memory.db, so they survive restarts; ones that came due while JARVIS was
off are delivered at startup, marked as missed. If JARVIS is busy when a reminder is due, the
notification shows at once and the spoken reminder waits (up to 10 minutes) until it's free.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable

from app.core.jarvis import Jarvis
from app.memory.store import MemoryStore

log = logging.getLogger("jarvis.reminders")

TICK_SECONDS = 5
MISSED_AFTER = timedelta(minutes=2)
SPEAK_WITHIN = timedelta(minutes=10)


class ReminderService:
    def __init__(
        self,
        core: Jarvis,
        memory: MemoryStore,
        user_name: str,
        notify: Callable[[str, str], bool],
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._core = core
        self._memory = memory
        self._name = user_name
        self._notify = notify
        self._now = now
        self._to_speak: list[tuple[datetime, str]] = []

    def start(self) -> None:
        threading.Thread(target=self._run, name="reminders", daemon=True).start()

    def _run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception:
                log.exception("Reminder check failed")
            time.sleep(TICK_SECONDS)

    def tick(self) -> None:
        now = self._now()
        for reminder in self._memory.upcoming_reminders(until=now):
            missed = now - reminder["due"] > MISSED_AFTER
            when = f"{reminder['due']:%I:%M %p}".lstrip("0")
            self._notify("\U0001f514 Reminder" + (f" (missed, {when})" if missed else ""), reminder["text"])
            spoken = (f"{self._name}, while I was off you had a reminder at {when}: {reminder['text']}." if missed
                      else f"{self._name}, reminder: {reminder['text']}.")
            self._to_speak.append((now, spoken))
            self._memory.reminder_fired(reminder["id"], now)
            log.info("Reminder %s delivered: %s", reminder["id"], reminder["text"])
        self._to_speak = [(at, text) for at, text in self._to_speak if now - at <= SPEAK_WITHIN]
        if self._to_speak and self._core.announce(self._to_speak[0][1]):
            self._to_speak.pop(0)
