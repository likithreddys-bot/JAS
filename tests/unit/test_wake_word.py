import threading
import time

import numpy as np

from app.core.events.events import (
    MicrophoneRecovered,
    MicrophoneUnavailable,
    StateChanged,
    WakeWordDetected,
)
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.voice.audio.microphone import MicrophoneError
from app.voice.wake_word.detector import WakeWordDetector
from app.voice.wake_word.service import WakeWordService

FRAME = np.zeros(1280, dtype=np.int16)


def detector_with(scores, threshold=0.5, cooldown=3):
    it = iter(scores)
    resets = []
    d = WakeWordDetector(lambda f: next(it), lambda: resets.append(1), threshold, cooldown)
    return d, resets


# --- detector -------------------------------------------------------------

def test_fires_once_above_threshold_then_cools_down():
    d, resets = detector_with([0.1, 0.9, 0.9, 0.9, 0.9, 0.9])
    fired = [d.process(FRAME) for _ in range(6)]
    assert fired == [None, 0.9, None, None, None, 0.9]
    assert len(resets) == 2


def test_below_threshold_never_fires():
    d, _ = detector_with([0.49] * 10)
    assert all(d.process(FRAME) is None for _ in range(10))


# --- service with a fake microphone --------------------------------------

class FakeMic:
    def __init__(self, fail_times=0):
        self.fail_times = fail_times
        self.opened = 0
        self.closed = 0
        self._open = False
        self.frames = 0

    @property
    def is_open(self):
        return self._open

    def open(self):
        if self.fail_times:
            self.fail_times -= 1
            raise MicrophoneError("No microphone found")
        self._open = True
        self.opened += 1

    def close(self):
        if self._open:
            self.closed += 1
        self._open = False

    def read(self, timeout):
        time.sleep(0.005)
        self.frames += 1
        return FRAME


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def run_service(core, mic, scores):
    it = iter(scores)
    d = WakeWordDetector(lambda f: next(it, 0.0), lambda: None, 0.5, cooldown_frames=1000)
    svc = WakeWordService(core.bus, mic, d, core.state.current)
    svc.start()
    return svc


def test_wake_word_moves_core_to_wake_detected():
    core = Jarvis()
    core.start()
    seen = []
    core.bus.subscribe(StateChanged, lambda e: seen.append(e.current))
    svc = run_service(core, FakeMic(), [0.0] * 5 + [0.95])
    try:
        assert wait_for(lambda: S.WAKE_DETECTED in seen)
    finally:
        svc.stop()


def test_no_detection_outside_standby():
    core = Jarvis()
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    core.state.transition(S.LISTENING)
    wakes = []
    core.bus.subscribe(WakeWordDetected, wakes.append)
    mic = FakeMic()
    svc = run_service(core, mic, [0.99] * 1000)
    try:
        assert wait_for(lambda: mic.frames > 20)
        assert wakes == []
    finally:
        svc.stop()


def test_pause_closes_microphone_and_resume_reopens():
    core = Jarvis()
    core.start()
    mic = FakeMic()
    svc = run_service(core, mic, [])
    try:
        assert wait_for(lambda: mic.is_open)
        core.pause()
        assert wait_for(lambda: not mic.is_open)
        core.resume()
        assert wait_for(lambda: mic.is_open and mic.opened == 2)
    finally:
        svc.stop()


def test_missing_microphone_reports_error_then_recovers(monkeypatch):
    monkeypatch.setattr("app.voice.wake_word.service.RETRY_SECONDS", 0.05)
    core = Jarvis()
    core.start()
    events = []
    core.bus.subscribe(MicrophoneUnavailable, events.append)
    core.bus.subscribe(MicrophoneRecovered, events.append)
    mic = FakeMic(fail_times=3)
    svc = run_service(core, mic, [])
    try:
        assert wait_for(lambda: any(isinstance(e, MicrophoneRecovered) for e in events))
        assert isinstance(events[0], MicrophoneUnavailable)  # reported once, not per retry
        assert sum(isinstance(e, MicrophoneUnavailable) for e in events) == 1
        assert core.state.current is S.STANDBY
    finally:
        svc.stop()


def test_mic_error_shows_reason_in_error_state():
    core = Jarvis()
    core.start()
    core.bus.publish(MicrophoneUnavailable("No microphone found"))
    assert core.state.current is S.ERROR
    core.bus.publish(MicrophoneRecovered())
    assert core.state.current is S.STANDBY


class FakePorcupine:
    frame_length = 512

    def __init__(self, fire_at_chunk=None):
        self.chunks = 0
        self.fire_at = fire_at_chunk

    def process(self, pcm):
        assert len(pcm) == 512
        self.chunks += 1
        return 0 if self.chunks == self.fire_at else -1


def test_porcupine_adapter_rechunks_mic_frames():
    from app.voice.wake_word.detector import PorcupineDetector

    engine = FakePorcupine(fire_at_chunk=5)
    d = PorcupineDetector(engine)
    results = [d.process(np.zeros(1280, dtype=np.int16)) for _ in range(3)]  # 3840 samples = 7 chunks + 256 left
    assert engine.chunks == 7
    assert results == [None, 1.0, None]  # chunk 5 arrives during the 2nd mic frame


def test_porcupine_without_key_is_a_clear_error():
    import pytest

    from app.voice.wake_word.detector import load_porcupine

    with pytest.raises(ValueError, match="PICOVOICE_ACCESS_KEY"):
        load_porcupine("", "jarvis", 0.5)


def test_wake_word_is_heard_while_busy_and_interrupts():
    from app.core.events.events import TaskInterrupted

    core = Jarvis()
    core.start()
    for s in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING, S.EXECUTING):
        core.state.transition(s)
    interrupts = []
    core.bus.subscribe(TaskInterrupted, interrupts.append)
    svc = run_service(core, FakeMic(), [0.0] * 3 + [0.95])
    try:
        assert wait_for(lambda: interrupts and core.state.current is S.STANDBY)
        assert interrupts[0].reason == "stopped by user" and core.cancelled.is_set()
    finally:
        svc.stop()
