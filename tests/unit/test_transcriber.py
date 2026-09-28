"""The backlog counter that lets the phone refuse a clip rather than queue behind a growing pile.

There is one Whisper model, on CPU, shared by the wake-word pipeline, barge-in and every phone.
A real conversation nearby once queued this laptop 75 seconds deep: each clip transcribed a minute
after it was said, to a question nobody was still asking. `backlog` is how the phone's own request
handler knows to say "try again" immediately instead of joining that queue.
"""
import threading
import time

import numpy as np
import pytest

from app.voice.stt.transcriber import Transcriber


class SlowModel:
    """Stands in for WhisperModel: blocks until told to finish, so a test can observe the backlog
    while a "transcription" is genuinely in progress rather than guessing at timing with sleeps."""

    def __init__(self):
        self.release = threading.Event()
        self.entered = threading.Event()

    def transcribe(self, audio, **kwargs):
        self.entered.set()
        self.release.wait(timeout=5)
        segment = type("Segment", (), {"text": "hello"})()
        return [segment], None


@pytest.fixture
def transcriber(tmp_path):
    t = Transcriber("small", tmp_path, language=None)
    t._model = SlowModel()  # skip the real, heavy model load entirely
    return t


def test_backlog_is_zero_when_nothing_is_happening(transcriber):
    assert transcriber.backlog == 0


def test_backlog_rises_while_a_transcription_is_in_progress(transcriber):
    model: SlowModel = transcriber._model
    thread = threading.Thread(target=lambda: transcriber.transcribe(np.zeros(16000, dtype=np.int16)))
    thread.start()
    try:
        assert model.entered.wait(timeout=2), "the transcription never started"
        assert transcriber.backlog == 1
    finally:
        model.release.set()
        thread.join(timeout=2)
    assert transcriber.backlog == 0, "must drop back to zero once the call returns"


def test_backlog_counts_callers_still_queued_behind_the_lock(transcriber):
    """A second caller is blocked on the lock, not yet in the model - it must still count, because
    it is exactly this caller the phone's backpressure exists to protect."""
    model: SlowModel = transcriber._model
    first = threading.Thread(target=lambda: transcriber.transcribe(np.zeros(16000, dtype=np.int16)))
    first.start()
    assert model.entered.wait(timeout=2)

    second = threading.Thread(target=lambda: transcriber.transcribe(np.zeros(16000, dtype=np.int16)))
    second.start()
    try:
        deadline = time.monotonic() + 2
        while transcriber.backlog < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert transcriber.backlog == 2, "one running, one queued behind the lock"
    finally:
        model.release.set()
        first.join(timeout=2)
        second.join(timeout=2)
    assert transcriber.backlog == 0
