"""JARVIS core: owns the event bus and state machine, exposes lifecycle controls."""
from __future__ import annotations

import logging

from app.core.events.bus import EventBus
from app.core.events.events import MicrophoneRecovered, MicrophoneUnavailable, WakeWordDetected
from app.core.state.machine import StateMachine
from app.core.state.states import JarvisState

log = logging.getLogger("jarvis.core")


class Jarvis:
    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus or EventBus()
        self.state = StateMachine(self.bus)
        self.bus.subscribe(WakeWordDetected, self._on_wake_word)
        self.bus.subscribe(MicrophoneUnavailable, self._on_mic_unavailable)
        self.bus.subscribe(MicrophoneRecovered, self._on_mic_recovered)

    def start(self) -> None:
        log.info("JARVIS starting")
        self.state.transition(JarvisState.STANDBY)

    @property
    def paused(self) -> bool:
        return self.state.current is JarvisState.SLEEPING

    def pause(self) -> None:
        if self.paused:
            return
        if self.state.current not in (JarvisState.STANDBY, JarvisState.ERROR):
            # Later phases cancel the running task here before standing down.
            self.state.transition(JarvisState.STANDBY, "paused by user")
        self.state.transition(JarvisState.SLEEPING, "paused by user")

    def resume(self) -> None:
        if self.paused:
            self.state.transition(JarvisState.STANDBY, "resumed by user")

    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    def _on_wake_word(self, event: WakeWordDetected) -> None:
        self.state.transition_from(JarvisState.STANDBY, JarvisState.WAKE_DETECTED)

    def _on_mic_unavailable(self, event: MicrophoneUnavailable) -> None:
        if self.state.current not in (JarvisState.ERROR, JarvisState.SLEEPING):
            self.state.transition(JarvisState.ERROR, event.reason)

    def _on_mic_recovered(self, event: MicrophoneRecovered) -> None:
        self.state.transition_from(JarvisState.ERROR, JarvisState.STANDBY, "microphone recovered")
