"""The same backlog contract as Transcriber (test_transcriber.py), for the OpenVINO backend.

The phone's backpressure check (app/remote.py) doesn't know or care which backend answered it - it
just calls `.backlog`. Both must behave identically, or switching STT_BACKEND would silently change
how the phone handles a busy queue.
"""
import threading
import time

import numpy as np
import pytest

from app.voice.stt.openvino_transcriber import OpenVinoTranscriber


class SlowPipeline:
    """Stands in for openvino_genai.WhisperPipeline: blocks until told to finish, so a test can
    observe the backlog while a "transcription" is genuinely in progress."""

    def __init__(self):
        self.release = threading.Event()
        self.entered = threading.Event()

    def generate(self, samples, **kwargs):
        self.entered.set()
        self.release.wait(timeout=5)
        return type("Result", (), {"texts": ["hello"]})()


@pytest.fixture
def transcriber(tmp_path):
    t = OpenVinoTranscriber(tmp_path, device="GPU", language=None)
    t._pipeline = SlowPipeline()  # skip the real model load entirely
    return t


def test_backlog_is_zero_when_nothing_is_happening(transcriber):
    assert transcriber.backlog == 0


def test_backlog_rises_while_a_transcription_is_in_progress(transcriber):
    pipeline: SlowPipeline = transcriber._pipeline
    thread = threading.Thread(target=lambda: transcriber.transcribe(np.zeros(16000, dtype=np.int16)))
    thread.start()
    try:
        assert pipeline.entered.wait(timeout=2), "the transcription never started"
        assert transcriber.backlog == 1
    finally:
        pipeline.release.set()
        thread.join(timeout=2)
    assert transcriber.backlog == 0


def test_backlog_counts_callers_still_queued_behind_the_lock(transcriber):
    pipeline: SlowPipeline = transcriber._pipeline
    first = threading.Thread(target=lambda: transcriber.transcribe(np.zeros(16000, dtype=np.int16)))
    first.start()
    assert pipeline.entered.wait(timeout=2)

    second = threading.Thread(target=lambda: transcriber.transcribe(np.zeros(16000, dtype=np.int16)))
    second.start()
    try:
        deadline = time.monotonic() + 2
        while transcriber.backlog < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert transcriber.backlog == 2, "one running, one queued behind the lock"
    finally:
        pipeline.release.set()
        first.join(timeout=2)
        second.join(timeout=2)
    assert transcriber.backlog == 0


def test_the_text_is_joined_from_all_returned_segments(transcriber):
    transcriber._pipeline.generate = lambda samples, **kw: type(
        "Result", (), {"texts": ["hello ", " there"]})()
    assert transcriber.transcribe(np.zeros(16000, dtype=np.int16)) == "hello there"


def test_a_missing_export_gives_a_clear_error_not_a_crash(tmp_path):
    t = OpenVinoTranscriber(tmp_path / "nothing-exported-here", device="GPU")
    with pytest.raises(RuntimeError, match="export_whisper_openvino"):
        t.ensure_loaded()


def test_vocabulary_becomes_hotwords_for_every_window():
    t = OpenVinoTranscriber(__import__("pathlib").Path("."), device="GPU")
    t.set_vocabulary("Sreenidhi, Arzoo, Stefee.")
    assert t._hotwords == "Sreenidhi, Arzoo, Stefee"

    t.set_vocabulary("")
    assert t._hotwords is None
