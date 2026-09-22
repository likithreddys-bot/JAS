"""Captures one spoken utterance, ending when the speaker stops talking (VAD-based).

`feed()` is called from the microphone thread; `wait()` from the pipeline thread.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Callable

import numpy as np

from app.voice.audio.microphone import FRAME_SAMPLES, SAMPLE_RATE

FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE
PRE_ROLL_FRAMES = 3  # keep ~240 ms before speech starts so the first word isn't clipped


class UtteranceRecorder:
    def __init__(
        self,
        speech_prob: Callable[[np.ndarray], float],
        reset_vad: Callable[[], None] = lambda: None,
        speech_threshold: float = 0.5,
        end_silence: float = 0.8,
        start_timeout: float = 5.0,
        max_duration: float = 15.0,
    ) -> None:
        self._speech_prob = speech_prob
        self._reset_vad = reset_vad
        self._threshold = speech_threshold
        self._end_silence = end_silence
        self._start_timeout = start_timeout
        self._max_duration = max_duration
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._active = False
        self._result: np.ndarray | None = None

    def begin(self, start_timeout: float | None = None) -> None:
        """Start capturing. `start_timeout` overrides how long to wait for speech to begin."""
        with self._lock:
            self._current_start_timeout = self._start_timeout if start_timeout is None else start_timeout
            self._reset_vad()
            self._frames: list[np.ndarray] = []
            self._pre_roll: deque[np.ndarray] = deque(maxlen=PRE_ROLL_FRAMES)
            self._started = False
            self._silence = 0.0
            self._elapsed = 0.0
            self._result = None
            self._done.clear()
            self._active = True

    def feed(self, frame: np.ndarray) -> None:
        with self._lock:
            if not self._active:
                return
            self._elapsed += FRAME_SECONDS
            is_speech = self._speech_prob(frame) >= self._threshold
            if self._started:
                self._frames.append(frame)
                self._silence = 0.0 if is_speech else self._silence + FRAME_SECONDS
                if self._silence >= self._end_silence or self._elapsed >= self._max_duration:
                    self._finish(np.concatenate(self._frames))
            elif is_speech:
                self._started = True
                self._frames = [*self._pre_roll, frame]
            else:
                self._pre_roll.append(frame)
                if self._elapsed >= self._current_start_timeout:
                    self._finish(None)

    def wait(self, timeout: float) -> np.ndarray | None:
        """Block until the utterance ends. None = nothing said (timeout) or cancelled."""
        self._done.wait(timeout)
        self.cancel()
        return self._result

    def cancel(self) -> None:
        with self._lock:
            self._active = False
            self._done.set()

    def _finish(self, audio: np.ndarray | None) -> None:
        self._result = audio
        self._active = False
        self._done.set()
