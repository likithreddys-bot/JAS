import pytest
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


def _turn_waiting_for_confirmation(answer):
    """Run a turn whose responder asks a yes/no question; return (pipeline, speaker, result box)."""
    core = Jarvis()
    speaker = FakeSpeaker()
    answers = iter(["close chrome", answer])
    stt = FakeTranscriber("")
    stt.transcribe = lambda audio: next(answers)
    box = {}
    holder = {}

    def respond(text):
        box["confirmed"] = holder["pipeline"].ask_yes_no("Should I close Chrome?")
        yield "Okay, closing it." if box["confirmed"] else "Okay, I won't."

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=respond, max_listen_seconds=3)
    holder["pipeline"] = pipeline
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)  # the request
    assert wait_for(lambda: speaker.said[-1:] == ["Should I close Chrome?"] and core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)  # the answer
    assert wait_for(lambda: core.state.current is S.STANDBY and "confirmed" in box)
    return speaker, box


def test_voice_confirmation_yes():
    speaker, box = _turn_waiting_for_confirmation("Yes, please.")
    assert box["confirmed"] is True and speaker.said[-1] == "Okay, closing it."


def test_voice_confirmation_no_or_unclear_means_no():
    for answer in ("No.", "No, yes, I mean no", "hmm"):
        speaker, box = _turn_waiting_for_confirmation(answer)
        assert box["confirmed"] is False and speaker.said[-1] == "Okay, I won't."


def test_follow_up_without_wake_word_then_silence_ends_conversation():
    core = Jarvis()
    speaker = FakeSpeaker()
    heard = iter(["what's the capital of Japan", "and its population"])
    stt = FakeTranscriber("")
    stt.transcribe = lambda audio: next(heard)
    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=echo_reply,
                             max_listen_seconds=3, follow_up_seconds=0.6)
    states = []
    core.bus.subscribe(StateChanged, lambda e: states.append(e.current))
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    # answered, then listening again for a follow-up — no wake word
    assert wait_for(lambda: len(speaker.said) == 2 and core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: len(speaker.said) == 3 and core.state.current is S.LISTENING)
    speak_into(pipeline, [SILENCE] * 10)  # nothing more to say
    assert wait_for(lambda: core.state.current is S.STANDBY)
    assert speaker.said == ["Yes?", "You said: what's the capital of Japan", "You said: and its population"]
    assert states.count(S.WAKE_DETECTED) == 1


def test_noise_during_follow_up_ends_quietly():
    core = Jarvis()
    speaker = FakeSpeaker()
    heard = iter(["hello", ""])  # second "utterance" was just noise
    stt = FakeTranscriber("")
    stt.transcribe = lambda audio: next(heard)
    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=echo_reply,
                             max_listen_seconds=3, follow_up_seconds=0.6)
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: len(speaker.said) == 2 and core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 2 + [SILENCE] * 10)
    assert wait_for(lambda: core.state.current is S.STANDBY)
    assert NOT_UNDERSTOOD not in speaker.said  # no "Sorry, I didn't catch that" for noise


def test_wake_word_while_thinking_stops_the_task():
    from app.core.events.events import WakeWordDetected
    from app.voice.pipeline import STOPPED_PHRASE

    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("write me a long essay")
    release = threading.Event()

    def slow_respond(text):
        release.wait(3)  # the LLM is still thinking...
        yield "This should never be spoken."

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=slow_respond, max_listen_seconds=3)
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: core.state.current is S.THINKING)

    core.bus.publish(WakeWordDetected(0.9))  # "Jarvis, stop!"
    assert core.state.current is S.STANDBY
    release.set()
    assert wait_for(lambda: speaker.said[-1:] == [STOPPED_PHRASE])
    assert "This should never be spoken." not in speaker.said


def test_wake_word_while_speaking_cuts_speech():
    from app.core.events.events import WakeWordDetected

    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("tell me a story")
    started = threading.Event()

    def long_speak(text):
        speaker.said.append(text)
        if text.startswith("Once"):
            started.set()
            return not speaker.stopped.wait(3)  # interrupted -> False
        return True

    speaker.speak = long_speak
    pipeline = VoicePipeline(core, speaker, stt, make_recorder(),
                             respond=lambda t: iter(["Once upon a time there was a king.", "He had a dragon."]),
                             max_listen_seconds=3)
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert started.wait(3)
    core.bus.publish(WakeWordDetected(0.9))
    assert speaker.stopped.is_set()
    assert wait_for(lambda: speaker.said[-1] == "Okay, stopped.")
    assert "He had a dragon." not in speaker.said


def test_instant_media_command_skips_the_llm():
    from app.voice import quick

    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("Stop the song")
    llm_calls, tool_calls = [], []

    def run_tool(name, args):
        tool_calls.append((name, args))
        return {"ok": True, "title": "Paaro"}

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=lambda t: llm_calls.append(t) or iter(()),
                             quick=lambda text: quick.run(text, run_tool), max_listen_seconds=3)
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: speaker.said[-1:] == ["Paused."] and core.state.current is S.STANDBY)
    assert tool_calls == [("media_control", {"action": "pause"})] and llm_calls == []


def test_go_offline_then_wake_up_gives_briefing_takes_todos_and_starts_the_day():
    from app.core.events.events import WakeWordDetected
    from app.voice import quick

    core = Jarvis()
    speaker = FakeSpeaker()
    heard = iter(["go offline", "finish the BERT model and call Rahul"])
    stt = FakeTranscriber("")
    stt.transcribe = lambda audio: next(heard)
    prompts = []

    def run_tool(name, args):
        if name == "go_offline":
            core.rest_requested = True
        return {"ok": True}

    def respond(prompt):
        prompts.append(prompt)
        yield "Added both to your list."

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=respond,
                             quick=lambda text: quick.run(text, run_tool), max_listen_seconds=3, follow_up_seconds=0.6,
                             briefing=lambda: ("Hey, hi Likki! What's on your to-do list for today?", True),
                             after_briefing=lambda: "Enjoy your day, Likki.")
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)  # "go offline"
    assert wait_for(lambda: core.state.current is S.RESTING)
    assert speaker.said[-1].startswith("Going offline")

    core.bus.publish(WakeWordDetected(0.9))  # "wake up, Jarvis"
    assert wait_for(lambda: speaker.said[-1] == "Hey, hi Likki! What's on your to-do list for today?")
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)  # the to-do list
    assert wait_for(lambda: core.state.current is S.STANDBY)
    assert "finish the BERT model and call Rahul" in prompts[0] and "add_todo" in prompts[0]
    assert speaker.said[-2:] == ["Added both to your list.", "Enjoy your day, Likki."]


def test_break_reminder_is_spoken_and_the_answer_handled():
    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("okay let's continue")
    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=lambda t: iter(["Great, let's keep going."]),
                             max_listen_seconds=3, follow_up_seconds=0.6)
    core.start()
    assert core.announce("Likki, your screen time is high. Take a break, or shall we continue?")
    assert wait_for(lambda: core.state.current is S.LISTENING)
    assert speaker.said == ["Likki, your screen time is high. Take a break, or shall we continue?"]  # no "Yes?"
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: speaker.said[-1] == "Great, let's keep going.")


def test_real_transcriber_builds_and_updates_its_vocabulary(tmp_path):
    from app.voice.stt.transcriber import Transcriber

    stt = Transcriber("small", tmp_path, "en")  # no model is loaded until first use
    assert stt._hint is None
    stt.set_vocabulary("Jarvis, Likki")
    assert stt._hint == "Jarvis, Likki."


@pytest.mark.parametrize("text, unfinished", [
    ("Play some.", True), ("Open YouTube music and", True), ("Skip the video. Add the", True),
    ("Search for", True), ("Uhm...", True), ("So there is a Python question on my screen, and", True),
    ("Open Notepad please.", False), ("Explain this.", False), ("Turn it on.", False),
    ("What's the weather?", False), ("Play Sahiba.", False),
])
def test_unfinished_sentence_detection(text, unfinished):
    from app.voice.pipeline import _UNFINISHED

    assert bool(_UNFINISHED.search(text)) is unfinished


def test_pausing_to_think_does_not_cut_the_user_off():
    core = Jarvis()
    speaker = FakeSpeaker()
    parts = iter(["Play some.", "nice Hindi song."])
    stt = FakeTranscriber("")
    stt.transcribe = lambda audio: next(parts)
    requests = []

    def respond(text):
        requests.append(text)
        yield "Playing a Hindi song."

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=respond, max_listen_seconds=3)
    heard = []
    core.bus.subscribe(TranscriptReady, lambda e: heard.append(e.text))
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)  # "Play some." ... (thinking)
    assert wait_for(lambda: heard == ["Play some."] and core.state.current is S.LISTENING)  # listening again
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)  # "nice Hindi song."
    assert wait_for(lambda: requests == ["Play some nice Hindi song."])


def test_says_on_it_when_work_starts():
    from app.core.events.events import ToolStarted
    from app.voice.pipeline import WORKING_PHRASE

    core = Jarvis()
    speaker, stt = FakeSpeaker(), FakeTranscriber("open notepad")

    def respond(text):
        core.bus.publish(ToolStarted(1, "Opening notepad"))  # what the executor does before a tool
        core.bus.publish(ToolStarted(2, "Typing"))
        yield "Done, Notepad is open."

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(), respond=respond, max_listen_seconds=3)
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    assert wait_for(lambda: core.state.current is S.LISTENING)
    speak_into(pipeline, [SPEECH] * 3 + [SILENCE] * 10)
    assert wait_for(lambda: core.state.current is S.STANDBY)
    assert speaker.said == ["Yes?", WORKING_PHRASE, "Done, Notepad is open."]  # "On it." once, before the work


def test_waking_from_rest_a_second_time_greets_instead_of_briefing_again():
    """The full briefing (weather, meetings, to-dos, music) is once a day, not every wake."""
    from app.core.events.events import WakeWordDetected
    from app.voice import quick

    core = Jarvis()
    speaker = FakeSpeaker()
    stt = FakeTranscriber("")
    stt.transcribe = lambda audio: "what's the time"
    started_the_day = []

    pipeline = VoicePipeline(core, speaker, stt, make_recorder(),
                             respond=lambda prompt: iter(["It's half past four."]),
                             quick=lambda text: None, max_listen_seconds=3, follow_up_seconds=0.6,
                             briefing=lambda: ("Welcome back, Likki.", False),
                             after_briefing=lambda: started_the_day.append(True) or "Enjoy your day.")
    core.start()
    core.rest()
    assert wait_for(lambda: core.state.current is S.RESTING)

    core.bus.publish(WakeWordDetected(0.9))
    assert wait_for(lambda: speaker.said[-1:] == ["Welcome back, Likki."])
    # It listens for a command instead of asking for a to-do list, and plays no morning video.
    assert wait_for(lambda: core.state.current is S.LISTENING)
    assert started_the_day == []


def test_the_briefing_is_remembered_for_the_day(tmp_path):
    from app.memory.store import MemoryStore

    memory = MemoryStore(tmp_path / "memory.db")
    assert memory.note("last_briefing") is None
    memory.set_note("last_briefing", "2026-09-23")
    assert memory.note("last_briefing") == "2026-09-23"
    memory.set_note("last_briefing", "2026-09-24")  # overwrites, never duplicates
    assert memory.note("last_briefing") == "2026-09-24"
