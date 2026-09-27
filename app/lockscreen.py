"""JARVIS follows the Windows lock screen: it rests while the PC is locked and greets you on unlock.

Windows gives no signal an ordinary app can wait on here, so the desktop is polled. The check is a
single `OpenInputDesktop` call, so once a second costs nothing measurable.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState

log = logging.getLogger("jarvis.core")

POLL_SECONDS = 1.0
SETTLE_TRIES = 15  # JARVIS may be mid-sentence when the screen locks; keep asking it to rest


class LockWatcher:
    def __init__(self, core: Jarvis, is_locked: Callable[[], bool], greeting: str,
                 poll_seconds: float = POLL_SECONDS,
                 bad_passwords: Callable[[], int | None] = lambda: None,
                 set_lock_face: Callable[[str], bool] | None = None) -> None:
        self._core = core
        self._is_locked = is_locked
        self._greeting = greeting
        self._poll = poll_seconds
        self._bad_passwords = bad_passwords
        self._set_face = set_lock_face
        self._locked = is_locked()
        self._wrong_at_lock = bad_passwords() or 0
        self._intruder = False
        self._wrong_seen = 0  # Windows resets the counter on a good login, so keep the peak
        threading.Thread(target=self._run, name="lock-watcher", daemon=True).start()

    def _run(self) -> None:
        while True:
            time.sleep(self._poll)
            try:
                self.check()
            except Exception:
                log.exception("Lock watcher failed")

    def check(self) -> None:
        """Poll once. Public so the behaviour can be tested without a real lock screen."""
        locked = self._is_locked()
        if locked == self._locked:
            if locked:
                self._watch_for_wrong_passwords()
            return
        self._locked = locked
        if locked:
            self._wrong_at_lock = self._bad_passwords() or 0
            self._intruder = False
            self._wrong_seen = 0
            self._face("watchful")
            self._rest()
        else:
            self._greet()

    def _wrong_passwords_since_lock(self) -> int:
        """The most attempts seen at any point. The live count drops back to zero once you get in."""
        now = self._bad_passwords()
        if now is not None:
            self._wrong_seen = max(self._wrong_seen, now - self._wrong_at_lock)
        return max(0, self._wrong_seen)

    def _watch_for_wrong_passwords(self) -> None:
        """Someone is trying passwords. JAS scowls from the lock screen."""
        if self._intruder or self._wrong_passwords_since_lock() <= 0:
            return
        self._intruder = True
        log.info("Wrong password entered while locked; showing the angry face")
        self._face("angry")

    def _face(self, mood: str) -> None:
        if not self._set_face:
            return
        try:
            self._set_face(mood)
        except Exception:
            log.exception("Could not change the lock screen face")

    def _rest(self) -> None:
        """Go quiet with the screen, stopping anything in progress."""
        if self._core.paused:  # already silent, and paused is the user's choice to leave alone
            return
        for attempt in range(SETTLE_TRIES):
            if self._core.state.current is JarvisState.RESTING:
                return
            if self._core.rest("screen locked"):
                log.info("Screen locked: resting")
                return
            if attempt == 0:
                self._core.interrupt("screen locked")
            time.sleep(0.2)
        log.warning("Screen locked but JARVIS stayed in %s", self._core.state.current.name)

    def _greet(self) -> None:
        tried = self._wrong_passwords_since_lock()
        self._face("watchful")
        if not self._core.state.transition_from(JarvisState.RESTING, JarvisState.STANDBY, "screen unlocked"):
            return
        log.info("Screen unlocked: greeting (%d wrong passwords while away)", tried)
        if tried:
            attempts = "once" if tried == 1 else f"{tried} times"
            self._core.announce(f"{self._greeting} Someone got your password wrong {attempts} while you were away.")
        else:
            self._core.announce(self._greeting)
