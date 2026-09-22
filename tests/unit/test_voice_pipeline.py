import threading
import time

import numpy as np

from app.core.events.events import AssistantReply, StateChanged, TranscriptReady
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.voice.listen.recorder import FRAME_SECONDS, UtteranceRecorder
from app.voice.pipeline import NOT_UNDERSTOOD, VoicePipeline, echo_reply

SPEECH = np.full(1280, 1, dtype=np.int16)
SILENCE = np.zeros(1280, dtype=np.int16)


def is_speech(frame):
    return 1.0 if frame[0] else 0.0


def make_recorder(**kw):
    return UtteranceRecorder(is_speech, end_silence=0.4, start_timeout=0.8, max_duration=3.0, **kw)


# --- recorder --------------------------------------------------------------

def test_recorder_ends_after_silence_and_keeps_pre_roll():
    r = make_recorder()
    r.begin()
    for f in [SILENCE] * 2 + [SPEECH] * 5 + [SILENCE] * 10:
        r.feed(f)
    audio = r.wait(0.1)
    silence_frames = round(0.4 / FRAME_SECONDS)
    assert audio is not None
    assert len(audio) == 1280 * (2 + 5 + silence_frames)


def test_recorder_times_out_without_speech():
    r = make_recorder()
    r.begin()
    for _ in range(20):
        r.feed(SILENCE)
    assert r.wait(0.1) is None


def test_recorder_caps_long_speech():
    r = make_recorder()
    r.begin()
    for _ in range(100):
        r.feed(SPEECH)
    audio = r.wait(0.1)
    assert audio is not None and len(audio) <= 1280 * round(3.0 / FRAME_SECONDS) + 1280


def test_recorder_ignores_frames_when_not_started():
    r = make_recorder()
    r.feed(SPEECH)  # no begin()
    r.begin()
    assert r.wait(0.05) is None  # nothing captured, wait timed out


# --- pipeline --------------------------------------------------------------

class FakeSpeaker:
    def __init__(self):
        self.said = []
        self.stopped = threading.Event()

    def speak(self, text):
        self.said.append(text)
        return True

    def stop(self):
        self.stopped.set()


class FakeTranscriber:
    def __init__(self, text):
        self.text = text
        self.loaded = threading.Event()

    def ensure_loaded(self):
        self.loaded.set()

    def transcribe(self, audio):
        return self.text


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def setup(text="how are you"):
    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber(text)
    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=echo_reply, max_listen_seconds=3)
    states, events = [], []
    core.bus.subscribe(StateChanged, lambda e: states.append(e.current))
    core.bus.subscribe(TranscriptReady, events.append)
    core.bus.subscribe(AssistantReply, events.append)
    core.start()
    return core, pipeline, speaker, stt, states, events


def speak_into(pipeline, frames):
    for f in frames:
        pipeline.feed(f)


def test_full_turn_ack_listen_transcribe_reply():
    core, pipeline, speaker, stt, states, events = setup()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 5 + [SILENCE] * 10)
    assert wait_for(lambda: len(states) == 7)  # wait for the final StateChanged event itself

    assert speaker.said == ["Yes?", "You said: how are you"]
    assert stt.loaded.is_set()
    assert states == [S.STANDBY, S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING, S.RESPONDING, S.STANDBY]
    assert [e.text for e in events] == ["how are you", "You said: how are you"]


def test_no_speech_returns_to_standby_silently():
    core, pipeline, speaker, _, states, _ = setup()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SILENCE] * 20)
    assert wait_for(lambda: core.state.current is S.STANDBY)
    assert speaker.said == ["Yes?"]
    assert S.TRANSCRIBING not in states


def test_empty_transcript_says_sorry():
    core, pipeline, speaker, *_ = setup(text="")
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: speaker.said[-1:] == [NOT_UNDERSTOOD] and core.state.current is S.STANDBY)


def test_pause_while_listening_cancels_turn():
    core, pipeline, speaker, *_ = setup()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    core.pause()
    assert speaker.stopped.is_set()
    time.sleep(0.2)
    assert core.state.current is S.SLEEPING
    assert speaker.said == ["Yes?"]


def test_failure_shows_error_then_recovers(monkeypatch):
    monkeypatch.setattr("app.voice.pipeline.ERROR_DISPLAY_SECONDS", 0.1)
    core, pipeline, speaker, stt, *_ = setup()
    stt.transcribe = lambda audio: (_ for _ in ()).throw(RuntimeError("model missing"))
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: core.state.current is S.ERROR)
    assert wait_for(lambda: core.state.current is S.STANDBY)


def test_streamed_reply_is_spoken_sentence_by_sentence():
    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("how are you")
    captions = []

    def respond(text):
        yield "I'm doing really well, thank you. "
        yield "How can I help you today?"

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=respond, max_listen_seconds=3)
    core.bus.subscribe(AssistantReply, lambda e: captions.append(e.text))
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: len(speaker.said) == 3 and core.state.current is S.STANDBY)
    assert speaker.said[1:] == ["I'm doing really well, thank you.", "How can I help you today?"]
    assert captions[-1] == "I'm doing really well, thank you. How can I help you today?"


def test_cancel_phrase_ends_turn_without_llm():
    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("Never mind.")
    called = []
    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=lambda t: called.append(t) or iter(()), max_listen_seconds=3)
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: core.state.current is S.STANDBY)
    time.sleep(0.1)
    assert called == [] and speaker.said == ["Yes?"]


def test_brain_failure_is_shown_and_spoken(monkeypatch):
    monkeypatch.setattr("app.voice.pipeline.ERROR_DISPLAY_SECONDS", 0.1)
    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("what time is it")

    def respond(text):
        raise RuntimeError("Can't reach Claude. Check the internet connection.")
        yield  # pragma: no cover

    reasons = []
    core.bus.subscribe(StateChanged, lambda e: e.current is S.ERROR and reasons.append(e.reason))
    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=respond, max_listen_seconds=3)
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: reasons == ["Can't reach Claude. Check the internet connection."])
    assert wait_for(lambda: speaker.said[-1] == "Sorry, something went wrong.")
    assert wait_for(lambda: core.state.current is S.STANDBY)
