"""Thread-safe state machine that validates transitions and publishes StateChanged."""
from __future__ import annotations

import logging
import threading

from app.core.events.bus import EventBus
from app.core.events.events import StateChanged
from app.core.state.states import TRANSITIONS, JarvisState

log = logging.getLogger("jarvis.core.state")


class InvalidTransition(Exception):
    pass


class StateMachine:
    def __init__(self, bus: EventBus, initial: JarvisState = JarvisState.STARTING) -> None:
        self._bus = bus
        self._state = initial
        # Reentrant so a StateChanged handler may itself trigger a transition.
        self._lock = threading.RLock()

    @property
    def current(self) -> JarvisState:
        return self._state

    def can_transition(self, target: JarvisState) -> bool:
        return target in TRANSITIONS[self._state]

    def transition(self, target: JarvisState, reason: str | None = None) -> None:
        with self._lock:
            previous = self._state
            if target not in TRANSITIONS[previous]:
                log.warning("Rejected transition %s -> %s", previous.name, target.name)
                raise InvalidTransition(f"{previous.name} -> {target.name}")
            self._state = target
            log.info(
                "State %s -> %s%s", previous.name, target.name, f" ({reason})" if reason else ""
            )
            self._bus.publish(StateChanged(previous, target, reason))

    def transition_from(
        self, expected: JarvisState, target: JarvisState, reason: str | None = None
    ) -> bool:
        """Atomically transition only if currently in `expected`. Returns whether it happened."""
        with self._lock:
            if self._state is not expected:
                return False
            self.transition(target, reason)
            return True
