"""Background watcher for screen time (break reminders) and the laptop waking from sleep.

Screen time counts continuous keyboard/mouse use; 5 idle minutes counts as a break. After the
laptop resumes from sleep JARVIS goes to rest, so "wake up, Jarvis" gives the day's briefing.
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes
from typing import Callable

from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState

log = logging.getLogger("jarvis.wellbeing")

TICK_SECONDS = 15
BREAK_IDLE_SECONDS = 5 * 60
SLEEP_GAP_SECONDS = 90  # a tick that arrives this late means the laptop was asleep


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


ctypes.windll.kernel32.GetTickCount.restype = wintypes.DWORD


def idle_seconds() -> float:
    info = _LastInputInfo(ctypes.sizeof(_LastInputInfo), 0)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0  # wrap-safe


class ActivityMonitor:
    def __init__(
        self,
        core: Jarvis,
        user_name: str,
        break_minutes: int,
        idle: Callable[[], float] = idle_seconds,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._core = core
        self._name = user_name
        self._break_seconds = break_minutes * 60
        self._idle = idle
        self._clock = clock
        self._session_start: float | None = None
        self._last_tick = clock()

    def start(self) -> None:
        threading.Thread(target=self._run, name="wellbeing", daemon=True).start()

    def _run(self) -> None:
        while True:
            time.sleep(TICK_SECONDS)
            try:
                self.tick()
            except Exception:
                log.exception("Wellbeing check failed")

    def tick(self) -> None:
        now = self._clock()
        if now - self._last_tick > SLEEP_GAP_SECONDS:
            log.info("Laptop was asleep for %.0f s", now - self._last_tick)
            self._session_start = None
            self._core.rest("laptop woke up")
        self._last_tick = now

        if self._idle() >= BREAK_IDLE_SECONDS:
            self._session_start = None  # they took a break
            return
        if self._session_start is None:
            self._session_start = now
            return
        used = now - self._session_start
        if self._break_seconds and used >= self._break_seconds and self._core.state.current is JarvisState.STANDBY:
            minutes = int(used // 60)
            if self._core.announce(f"{self._name}, your screen time is high: you've been at it for "
                                   f"{minutes} minutes straight. Please take a short break, or shall we continue?"):
                log.info("Break reminder after %d minutes", minutes)
                self._session_start = now  # next reminder after another full stretch
