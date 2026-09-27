"""JARVIS core: owns the event bus and state machine, exposes lifecycle controls."""
from __future__ import annotations

import logging
import threading

from app.core.events.bus import EventBus
from app.core.events.events import (
    MicrophoneRecovered,
    MicrophoneUnavailable,
    TaskInterrupted,
    WakeWordDetected,
)
from app.core.state.machine import StateMachine
from app.core.state.states import BUSY_STATES, JarvisState

log = logging.getLogger("jarvis.core")


class Jarvis:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus or EventBus()
        self.state = StateMachine(self.bus)
        # Set when the user interrupts; checked by the executor and pipeline between steps.
        self.cancelled = threading.Event()
        self.rest_requested = False  # rest once the current reply has been spoken
        self.announcement: str | None = None  # something JARVIS starts saying by itself
        self.quiet = False  # the reply is going somewhere other than this laptop's speakers
        self.typed_request: str | None = None  # a request typed in the dashboard instead of spoken
        self.bus.subscribe(WakeWordDetected, self._on_wake_word)
        self.bus.subscribe(MicrophoneUnavailable, self._on_mic_unavailable)
        self.bus.subscribe(MicrophoneRecovered, self._on_mic_recovered)

    def start(self, resting: bool = False) -> None:
        log.info("JARVIS starting")
        self.state.transition(JarvisState.STANDBY)
        if resting:
            self.rest("started")

    def rest(self, reason: str = "going offline") -> bool:
        """Go quiet: only the wake word is listened for, and it wakes JARVIS with a briefing."""
        return self.state.transition_from(JarvisState.STANDBY, JarvisState.RESTING, reason)

    def activate(self, reason: str = "hotkey") -> bool:
        """Start listening without the wake word (global hotkey)."""
        for state in (JarvisState.STANDBY, JarvisState.RESTING):
            if self.state.transition_from(state, JarvisState.WAKE_DETECTED, reason):
                return True
        return False

    def ask_text(self, text: str, answer_here: bool = True) -> bool:
        """Handle a typed request (dashboard, phone) as if it had been spoken.

        `answer_here` False means the reply belongs somewhere else - the phone that asked - so the
        laptop stays quiet rather than talking to an empty room.
        """
        if not text.strip():
            return False
        self.typed_request = text.strip()
        self.quiet = not answer_here
        return self.activate("typed")

    def announce(self, text: str) -> bool:
        """Start speaking on JARVIS's own initiative (e.g. a break reminder). Only when idle."""
        if self.state.current is not JarvisState.STANDBY:
            return False
        self.announcement = text
        return self.state.transition_from(JarvisState.STANDBY, JarvisState.WAKE_DETECTED, "announcement")

    @property
    def paused(self) -> bool:
        return self.state.current is JarvisState.SLEEPING

    def pause(self) -> None:
        if self.paused:
            return
        if self.state.current not in (JarvisState.STANDBY, JarvisState.ERROR):
            self.interrupt("paused by user")
        self.state.transition(JarvisState.SLEEPING, "paused by user")

    def resume(self) -> None:
        if self.paused:
            self.state.transition(JarvisState.STANDBY, "resumed by user")

    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    def interrupt(self, reason: str) -> None:
        """Stop whatever JARVIS is doing: cancel the task, stop speaking, return to standby."""
        log.info("Interrupted: %s", reason)
        self.cancelled.set()
        self.bus.publish(TaskInterrupted(reason))
        current = self.state.current
        if current in BUSY_STATES or current in (JarvisState.WAKE_DETECTED, JarvisState.LISTENING):
            self.state.transition_from(current, JarvisState.STANDBY, reason)

    def _on_wake_word(self, event: WakeWordDetected) -> None:
        if self.state.transition_from(JarvisState.STANDBY, JarvisState.WAKE_DETECTED):
            return
        if self.state.transition_from(JarvisState.RESTING, JarvisState.WAKE_DETECTED, "waking up"):
            return
        if self.state.current in BUSY_STATES:  # "Jarvis, stop!" while it's working or talking
            self.interrupt("stopped by user")

    def _on_mic_unavailable(self, event: MicrophoneUnavailable) -> None:
        if self.state.current not in (JarvisState.ERROR, JarvisState.SLEEPING):
            self.state.transition(JarvisState.ERROR, event.reason)

    def _on_mic_recovered(self, event: MicrophoneRecovered) -> None:
        self.state.transition_from(JarvisState.ERROR, JarvisState.STANDBY, "microphone recovered")
