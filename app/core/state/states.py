"""JARVIS states and the legal transitions between them."""
from __future__ import annotations

from enum import Enum


class JarvisState(Enum):
    STARTING = "starting"
    STANDBY = "standby"
    WAKE_DETECTED = "wake_detected"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    RESPONDING = "responding"
    ERROR = "error"
    SLEEPING = "sleeping"


S = JarvisState

# ERROR is reachable from every state and is added below. Every active state can
# fall back to STANDBY (cancel / timeout).
TRANSITIONS: dict[JarvisState, frozenset[JarvisState]] = {
    S.STARTING: frozenset({S.STANDBY}),
    S.STANDBY: frozenset({S.WAKE_DETECTED, S.SLEEPING}),
    S.WAKE_DETECTED: frozenset({S.LISTENING, S.STANDBY}),
    S.LISTENING: frozenset({S.TRANSCRIBING, S.STANDBY}),
    S.TRANSCRIBING: frozenset({S.THINKING, S.RESPONDING, S.STANDBY}),
    S.THINKING: frozenset({S.PLANNING, S.EXECUTING, S.RESPONDING, S.STANDBY}),
    S.PLANNING: frozenset({S.EXECUTING, S.RESPONDING, S.STANDBY}),
    S.EXECUTING: frozenset({S.OBSERVING, S.RESPONDING, S.STANDBY}),
    S.OBSERVING: frozenset({S.THINKING, S.PLANNING, S.EXECUTING, S.RESPONDING, S.STANDBY}),
    S.RESPONDING: frozenset({S.EXECUTING, S.LISTENING, S.STANDBY}),
    S.ERROR: frozenset({S.STANDBY, S.SLEEPING}),
    S.SLEEPING: frozenset({S.STANDBY}),
}
TRANSITIONS = {
    state: targets | ({S.ERROR} if state is not S.ERROR else frozenset())
    for state, targets in TRANSITIONS.items()
}
