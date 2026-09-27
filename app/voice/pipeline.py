"""One voice turn: "Yes?" → listen until the user stops → transcribe → think → reply out loud.

Runs on its own worker thread, triggered when the core enters WAKE_DETECTED.
Every step checks the state it expects, so pausing mid-turn aborts cleanly.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
from typing import Callable, Iterable, Iterator, Protocol

import numpy as np

from app.core.events.events import (
    AssistantReply,
    AudioLevel,
    StateChanged,
    TaskInterrupted,
    ToolStarted,
    TranscriptReady,
)
from app.core.jarvis import Jarvis
from app.brain.sentences import sentences
from app.core.state.states import JarvisState as S
from app.tools.base import TaskCancelled
from app.voice import pitch
from app.voice.listen.recorder import UtteranceRecorder

log = logging.getLogger("jarvis.voice.pipeline")

ACK_PHRASE = "Yes?"
NOT_UNDERSTOOD = "Sorry, I didn't catch that."
FAILURE_PHRASE = "Sorry, something went wrong."
STOPPED_PHRASE = "Okay, stopped."
WORKING_PHRASE = "On it."
DID_IT = "Done."
NOTHING_TO_SAY = "Sorry, I didn't get that. Could you say it again?"  # said as soon as the first action starts, so the user isn't left in silence
CONTINUE_SECONDS = 3.0  # extra listening when the user seems mid-sentence
MAX_CONTINUATIONS = 3
# A sentence ending like this is probably unfinished ("play some...", "open the...", "uhm").
_UNFINISHED = re.compile(
    r"(?:\.\.\.|,)\s*$"  # trailing ellipsis or comma
    # words that never end a sentence, even if the transcriber put a full stop after them
    r"|\b(?:and|or|but|so|because|the|a|an|to|of|for|with|my|your|our|some|any|than|into|about|while|"
    r"uh|um|uhm|hmm|mm|like|also)\W*$"
    # words that often trail off mid-thought, but are fine once a sentence has actually ended
    r"|\b(?:then|if|when|from|in|on|at|that|this|these|those|is|are|was|were|will|would|can|could|"
    r"should|just|very|really)\s*$", re.I)
TODO_REQUEST = ("The user just told you their to-do list for today: \"{heard}\". Save each separate task "
                "with add_todo, then confirm in one short sentence.")
# Handled locally, without the LLM: end the turn quietly.
CANCEL_PHRASES = {"cancel", "never mind", "nevermind", "stop", "nothing", "forget it"}
YES_WORDS = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "go", "do", "please", "haan", "ha", "correct"}
ERROR_DISPLAY_SECONDS = 4.0
LISTEN_WAIT_SLACK = 2.0


class SpeakerLike(Protocol):
    def speak(self, text: str) -> bool: ...
    def stop(self) -> None: ...


class TranscriberLike(Protocol):
    def ensure_loaded(self) -> None: ...
    def transcribe(self, audio: np.ndarray) -> str: ...


class VoicePipeline:
    def __init__(
        self,
        core: Jarvis,
        speaker: SpeakerLike,
        transcriber: TranscriberLike,
        recorder: UtteranceRecorder,
        respond: Callable[[str], Iterable[str]],
        quick: Callable[[str], str | None] | None = None,
        on_exchange: Callable[[str, str], None] = lambda user, reply: None,
        briefing: Callable[[], tuple[str, bool]] | None = None,
        after_briefing: Callable[[], str] | None = None,
        max_listen_seconds: float = 15.0,
        follow_up_seconds: float = 0.0,
        match_voice: bool = True,
    ) -> None:
        self._core = core
        self._speaker = speaker
        self._stt = transcriber
        self._recorder = recorder
        self._respond = respond
        self._quick = quick  # instant commands (media/volume) that skip the LLM
        self._on_exchange = on_exchange  # e.g. log to long-term memory
        self._briefing = briefing  # woken from rest: (what to say, is this the first wake today?)
        self._after_briefing = after_briefing  # e.g. start morning music; returns a closing line
        self._max_wait = max_listen_seconds + LISTEN_WAIT_SLACK
        self._follow_up_seconds = follow_up_seconds
        self._match_voice = match_voice  # answer in a voice near the speaker's own pitch
        self._turns: queue.Queue[str] = queue.Queue()
        core.bus.subscribe(StateChanged, self._on_state)
        core.bus.subscribe(TaskInterrupted, self._on_interrupt)
        core.bus.subscribe(ToolStarted, self._on_tool_started)
        self._working_ack_armed = False
        self._did_something = False
        self._silent_stop = False
        threading.Thread(target=self._worker, name="voice-pipeline", daemon=True).start()

    def feed(self, frame: np.ndarray) -> None:
        """Microphone frame while LISTENING (called on the microphone thread)."""
        self._recorder.feed(frame)
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        self._core.bus.publish(AudioLevel(min(rms / 4000.0, 1.0)))

    def _on_state(self, event: StateChanged) -> None:
        if event.current is S.WAKE_DETECTED:
            if event.reason in ("typed", "announcement"):
                self._turns.put(event.reason)
            elif event.previous is S.RESTING and self._briefing and event.reason != "hotkey":
                self._turns.put("briefing")
            else:
                self._turns.put("request")
        elif event.current is S.SLEEPING:
            self._speaker.stop()
            self._recorder.cancel()

    def _on_tool_started(self, event: ToolStarted) -> None:
        self._did_something = True
        # Runs on the pipeline thread just before the first tool of a reply: a quick "On it."
        if self._working_ack_armed:
            self._working_ack_armed = False
            self._speak(WORKING_PHRASE)

    def _on_interrupt(self, event: TaskInterrupted) -> None:
        # Pausing is meant to be silent: announcing "Okay, stopped." to someone who just muted
        # JAS is the opposite of what they asked for.
        self._silent_stop = "pause" in event.reason.lower()
        self._speaker.stop()
        self._recorder.cancel()

    def _worker(self) -> None:
        while True:
            kind = self._turns.get()
            self._core.cancelled.clear()  # new request; any earlier one has fully unwound
            try:
                self._turn(kind)
            except TaskCancelled:
                log.info("Task cancelled by user")
            except Exception as exc:
                if self._core.cancelled.is_set():
                    log.info("Task stopped by user (%s)", type(exc).__name__)
                else:
                    log.exception("Voice turn failed")
                    self._fail(str(exc) or type(exc).__name__)
                    self._say(FAILURE_PHRASE)
            self._core.quiet = False
            if (self._core.cancelled.is_set() and self._core.state.current is S.STANDBY
                    and not self._silent_stop and not self._core.paused):
                self._say(STOPPED_PHRASE)
            self._silent_stop = False

    def _say(self, phrase: str) -> None:
        try:
            self._speak(phrase)
        except Exception:
            log.exception("Could not speak %r", phrase)

    def _speak(self, text: str) -> bool:
        """Say it out loud, unless this answer belongs to the phone that asked for it."""
        if self._core.quiet:
            return True
        return self._speaker.speak(text)

    def _turn(self, kind: str = "request") -> None:
        state = self._core.state
        # Load speech-to-text while we say "Yes?" and the user talks, hiding the load time.
        threading.Thread(target=self._preload_stt, name="stt-preload", daemon=True).start()

        if kind == "typed":
            text = self._core.typed_request or ""
            self._core.typed_request = None
            if not state.transition_from(S.WAKE_DETECTED, S.TRANSCRIBING):
                return
            self._answer(text, follow_up=False)
            if self._core.rest_requested:
                self._go_rest()
                return
            for current in (S.RESPONDING, S.OBSERVING, S.THINKING):
                if state.transition_from(current, S.STANDBY):
                    break
            return

        if kind == "request":
            self._speak(ACK_PHRASE)
            self._recorder.begin()
            if not state.transition_from(S.WAKE_DETECTED, S.LISTENING):
                self._recorder.cancel()
                return
            follow_up = False
        else:  # JARVIS speaks first: morning briefing, or an announcement such as a break reminder
            # The full briefing happens once a day; waking again later is just a greeting.
            text, first_today = self._briefing() if kind == "briefing" else ((self._core.announcement or ""), False)
            self._core.announcement = None
            if not text or not state.transition_from(S.WAKE_DETECTED, S.RESPONDING):
                state.transition_from(S.WAKE_DETECTED, S.STANDBY)
                return
            self._core.bus.publish(AssistantReply(text))
            if not self._speak(text):
                return
            if kind == "briefing" and first_today:
                self._briefing_todos()
                return
            if not self._listen_again(self._follow_up_seconds or 8.0):
                return
            follow_up = True

        while True:
            audio = self._recorder.wait(self._max_wait)
            if audio is None:
                state.transition_from(S.LISTENING, S.STANDBY, "no follow-up" if follow_up else "no speech heard")
                return
            if not state.transition_from(S.LISTENING, S.TRANSCRIBING):
                return
            self._match_the_speaker(audio)
            if not self._answer(self._transcribe_whole_thought(audio), follow_up):
                return
            if self._core.rest_requested:  # "go offline" was the request
                self._go_rest()
                return
            # Follow-up mode: keep listening briefly so the user can continue without the wake word.
            if not self._follow_up_seconds or not self._listen_again(self._follow_up_seconds):
                break
            follow_up = True
        for current in (S.RESPONDING, S.OBSERVING):
            if state.transition_from(current, S.STANDBY):
                break

    def _match_the_speaker(self, audio: np.ndarray) -> None:
        """Answer in whichever of the two voices is closer to the pitch of whoever just spoke."""
        if not self._match_voice or not hasattr(self._speaker, "use"):
            return
        try:
            kind = pitch.voice_for(audio, getattr(self._speaker, "_kind", "lower"))
        except Exception:
            log.exception("Could not measure the speaker's pitch")
            return
        if kind:
            self._speaker.use(kind)

    def _transcribe_whole_thought(self, audio: np.ndarray) -> str:
        """Transcribe; if it sounds unfinished (the user paused to think), keep listening and append."""
        state = self._core.state
        text = self._stt.transcribe(audio)
        for _ in range(MAX_CONTINUATIONS):
            if not text or not _UNFINISHED.search(text):
                break
            log.info("Sounds unfinished (%r); listening for more", text)
            self._core.bus.publish(TranscriptReady(text))
            self._recorder.begin(start_timeout=CONTINUE_SECONDS)
            if not state.transition_from(S.TRANSCRIBING, S.LISTENING):
                self._recorder.cancel()
                break
            more = self._recorder.wait(self._max_wait)
            if not state.transition_from(S.LISTENING, S.TRANSCRIBING) or more is None:
                break
            text = f"{text.rstrip('.… ')} {self._stt.transcribe(more)}".strip()
        return text

    def _listen_again(self, seconds: float) -> bool:
        """After speaking, listen for up to `seconds` for the user to answer (no wake word needed)."""
        if not self._enter_responding():
            return False
        self._recorder.begin(start_timeout=seconds)
        if not self._core.state.transition_from(S.RESPONDING, S.LISTENING):
            self._recorder.cancel()
            return False
        return True

    def _go_rest(self) -> None:
        self._core.rest_requested = False
        if self._enter_responding():
            self._core.state.transition_from(S.RESPONDING, S.RESTING, "going offline")

    def _briefing_todos(self) -> None:
        """After the morning briefing: take today's to-do list, then start the day (e.g. music)."""
        state = self._core.state
        if not self._listen_again(10.0):
            return
        audio = self._recorder.wait(self._max_wait)
        if not state.transition_from(S.LISTENING, S.TRANSCRIBING):
            return
        heard = self._stt.transcribe(audio).strip() if audio is not None else ""
        if heard:
            if not self._answer(heard, follow_up=False, prompt=TODO_REQUEST.format(heard=heard)):
                return
        elif not state.transition_from(S.TRANSCRIBING, S.THINKING):
            return
        closing = self._after_briefing() if self._after_briefing else ""
        if closing and self._enter_responding():
            self._core.bus.publish(AssistantReply(closing))
            self._speak(closing)
        for current in (S.RESPONDING, S.THINKING, S.OBSERVING):
            if state.transition_from(current, S.STANDBY):
                break

    def _answer(self, text: str, follow_up: bool, prompt: str | None = None) -> bool:
        """Handle one transcribed request. Returns True if a reply was spoken (conversation continues).

        `prompt` overrides what is sent to the LLM (the user's words are still shown and logged).
        """
        state = self._core.state
        log.info("Heard: %r", text)
        self._core.bus.publish(TranscriptReady(text))

        if not text:
            if follow_up:  # probably background noise after the reply; end quietly
                state.transition_from(S.TRANSCRIBING, S.STANDBY, "no follow-up")
            elif state.transition_from(S.TRANSCRIBING, S.RESPONDING):
                self._core.bus.publish(AssistantReply(NOT_UNDERSTOOD))
                self._speak(NOT_UNDERSTOOD)
                state.transition_from(S.RESPONDING, S.STANDBY)
            return False
        if not state.transition_from(S.TRANSCRIBING, S.THINKING):
            return False

        if self._quick:  # instant media/volume commands skip the LLM
            reply = self._quick(text)
            if reply is not None:
                if not self._enter_responding():
                    return False
                self._core.bus.publish(AssistantReply(reply))
                if not reply:  # e.g. locking the PC: do it and stay quiet
                    return True
                self._on_exchange(text, reply)
                return self._speak(reply)
        if _normalize(text) in CANCEL_PHRASES:
            for current in (S.THINKING, S.OBSERVING):
                if state.transition_from(current, S.STANDBY, "cancelled by user"):
                    break
            return False

        spoken = ""
        self._did_something = False
        self._working_ack_armed = True
        for sentence in sentences(self._respond(prompt or text)):
            self._working_ack_armed = False  # the reply itself is starting
            # Tools may have moved us to EXECUTING/OBSERVING between sentences.
            if not self._enter_responding():
                return False  # paused / cancelled mid-reply
            spoken = f"{spoken} {sentence}".strip()
            self._core.bus.publish(AssistantReply(spoken))
            if not self._speak(sentence):
                return False
        self._working_ack_armed = False
        if not spoken:
            # The model sometimes ends a turn after its tool calls without saying anything. The
            # work did happen, so an error state and "something went wrong" would be a lie.
            log.info("The model said nothing; acknowledging the work instead")
            spoken = DID_IT if self._did_something else NOTHING_TO_SAY
            if not self._enter_responding():
                return False
            self._core.bus.publish(AssistantReply(spoken))
            self._speak(spoken)
        self._on_exchange(text, spoken)
        return True

    def ask_yes_no(self, question: str) -> bool:
        """Ask by voice and listen for the answer (used to confirm risky actions). Silence = no."""
        state = self._core.state
        if not self._enter_responding():
            raise TaskCancelled()
        self._core.bus.publish(AssistantReply(question))
        self._speak(question)
        self._recorder.begin()
        if not state.transition_from(S.RESPONDING, S.LISTENING):
            self._recorder.cancel()
            raise TaskCancelled()
        audio = self._recorder.wait(self._max_wait)
        if not state.transition_from(S.LISTENING, S.TRANSCRIBING):
            raise TaskCancelled()
        answer = self._stt.transcribe(audio) if audio is not None else ""
        log.info("Confirmation %r -> %r", question, answer)
        self._core.bus.publish(TranscriptReady(answer))
        if not state.transition_from(S.TRANSCRIBING, S.THINKING):
            raise TaskCancelled()
        return bool(set(_normalize(answer).split()) & YES_WORDS) and "no" not in _normalize(answer).split()

    def _enter_responding(self) -> bool:
        state = self._core.state
        if state.current is S.RESPONDING:
            return True
        return any(state.transition_from(current, S.RESPONDING) for current in (S.THINKING, S.OBSERVING))

    def _preload_stt(self) -> None:
        try:
            self._stt.ensure_loaded()
        except Exception:
            log.warning("Speech-to-text preload failed", exc_info=True)  # reported when transcribing

    def _fail(self, reason: str) -> None:
        state = self._core.state
        if state.current in (S.ERROR, S.SLEEPING):
            return
        state.transition(S.ERROR, reason)
        timer = threading.Timer(ERROR_DISPLAY_SECONDS, state.transition_from, (S.ERROR, S.STANDBY))
        timer.daemon = True
        timer.start()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z ]", "", text.lower()).strip()


def echo_reply(text: str) -> Iterator[str]:
    """Responder used when no LLM is configured: repeat back what was heard."""
    yield f"You said: {text}"
