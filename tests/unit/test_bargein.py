"""Saying "stop" while JAS is busy cancels the task; anything else is ignored."""
import threading
import time

import numpy as np
import pytest

from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.voice.bargein import BargeIn, is_stop
from app.voice.listen.recorder import UtteranceRecorder

SPEECH = np.full(1280, 1, dtype=np.int16)
SILENCE = np.zeros(1280, dtype=np.int16)


@pytest.mark.parametrize("said", [
    "stop", "Stop.", "stop it", "stop that", "cancel", "shut up", "be quiet",
    "enough", "that's enough", "never mind", "forget it", "JAS stop", "stop Jarvis", "abort",
])
def test_these_mean_stop(said):
    assert is_stop(said)


@pytest.mark.parametrize("said", [
    "", "stop the music and play the next one",     # a real request, not a barge-in
    "I was going to stop by later",
    "Opening Notepad for you now.",                  # JAS hearing its own voice
    "the meeting is at four", "what's the time",
])
def test_these_do_not(said):
    assert not is_stop(said)


class FakeTranscriber:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        return self.text


def busy_core():
    core = Jarvis()
    core.start()
    for state in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING, S.RESPONDING):
        core.state.transition(state)
    return core


def recorder():
    return UtteranceRecorder(lambda frame: 1.0 if frame[0] else 0.0,
                             end_silence=0.2, start_timeout=0.5, max_duration=2.0)


def speak_into(barge, frames):
    for f in frames:
        barge.feed(f)
        time.sleep(0.002)


def wait_for(cond, timeout=4.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_saying_stop_while_answering_cancels_it():
    core = busy_core()
    stt = FakeTranscriber("Stop.")
    barge = BargeIn(core, stt, recorder())
    speak_into(barge, [SPEECH] * 4 + [SILENCE] * 12)
    assert wait_for(lambda: core.cancelled.is_set()), "saying stop did not cancel the task"
    assert wait_for(lambda: core.state.current is S.STANDBY)


def test_jas_hearing_its_own_voice_is_ignored():
    """Its own speech comes back through the microphone; that must never cancel anything."""
    core = busy_core()
    stt = FakeTranscriber("Opening Notepad for you now.")
    barge = BargeIn(core, stt, recorder())
    speak_into(barge, [SPEECH] * 4 + [SILENCE] * 12)
    assert wait_for(lambda: stt.calls > 0), "it should still check what it heard"
    time.sleep(0.3)
    assert not core.cancelled.is_set()
    assert core.state.current is S.RESPONDING


def test_nothing_is_transcribed_when_jas_is_idle():
    """Listening for a stop word only happens while JAS is busy, never in standby."""
    core = Jarvis()
    core.start()
    stt = FakeTranscriber("stop")
    barge = BargeIn(core, stt, recorder())
    speak_into(barge, [SPEECH] * 4 + [SILENCE] * 12)
    time.sleep(0.4)
    assert stt.calls == 0 and not core.cancelled.is_set()
