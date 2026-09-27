"""Background wake-word listener.

Keeps the microphone open unless JARVIS is paused, runs detection only in STANDBY,
and reports microphone failures (retrying until the mic comes back).
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

import numpy as np

from app.core.events.bus import EventBus
from app.core.events.events import (
    MicrophoneRecovered,
    MicrophoneUnavailable,
    StateChanged,
    WakeWordDetected,
)
from app.core.state.states import BUSY_STATES, JarvisState
from app.voice.audio.microphone import Microphone, MicrophoneError
from app.voice.wake_word.detector import WakeWordDetector

log = logging.getLogger("jarvis.voice.wake_word")

RETRY_SECONDS = 5.0
READ_TIMEOUT = 0.5
STALL_READS = 4  # consecutive empty reads (~2 s) => stream considered dead


class WakeWordService:
    def __init__(
        self,
        bus: EventBus,
        microphone: Microphone,
        detector: WakeWordDetector,
        initial_state: JarvisState,
        listen_sink: Callable[[np.ndarray], None] | None = None,
        busy_sink: Callable[[np.ndarray], None] | None = None,
    ) -> None:
        self._bus = bus
        self._mic = microphone
        self._detector = detector
        self._listen_sink = listen_sink
        self._busy_sink = busy_sink  # hears "stop" while JAS is talking or working
        self._state = initial_state
        self._wake = threading.Event()  # interrupts sleeps when state changes or on stop
        self._stopping = False
        self._reset_pending = False  # detector is only touched on the listener thread
        self._thread = threading.Thread(target=self._run, name="wake-word", daemon=True)
        bus.subscribe(StateChanged, self._on_state)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        self._thread.join(timeout=3)
        self._mic.close()

    def _on_state(self, event: StateChanged) -> None:
        self._state = event.current
        if event.current in (JarvisState.STANDBY, JarvisState.RESTING):
            self._reset_pending = True  # forget audio buffered before we became ready
        self._wake.set()

    def _run(self) -> None:
        mic_failed = False
        empty_reads = 0
        while not self._stopping:
            if self._state is JarvisState.SLEEPING:
                self._mic.close()  # paused: microphone fully released
                self._wait(None)
                continue

            if not self._mic.is_open:
                self._mic.close()
                try:
                    self._mic.open()
                except MicrophoneError as exc:
                    if not mic_failed:
                        log.error("%s", exc)
                        self._bus.publish(MicrophoneUnavailable(str(exc)))
                        mic_failed = True
                    self._wait(RETRY_SECONDS)
                    continue
                self._detector.reset()
                empty_reads = 0
                if mic_failed:
                    mic_failed = False
                    self._bus.publish(MicrophoneRecovered())

            frame = self._mic.read(READ_TIMEOUT)
            if frame is None:
                empty_reads += 1
                if empty_reads >= STALL_READS:
                    log.warning("Microphone stopped delivering audio; reopening")
                    self._mic.close()
                    empty_reads = 0
                continue
            empty_reads = 0

            if self._state is JarvisState.LISTENING and self._listen_sink:
                self._listen_sink(frame)
                continue
            if self._state not in (JarvisState.STANDBY, JarvisState.RESTING) and self._state not in BUSY_STATES:
                continue  # e.g. LISTENING: the user is talking to us, not calling us
            if self._state in BUSY_STATES and self._busy_sink:
                self._busy_sink(frame)
            if self._reset_pending:
                self._reset_pending = False
                self._detector.reset()
            score = self._detector.process(frame)
            if score is not None:
                log.info("Wake word detected (score %.2f)", score)
                self._bus.publish(WakeWordDetected(score))

    def _wait(self, timeout: float | None) -> None:
        self._wake.wait(timeout)
        self._wake.clear()
