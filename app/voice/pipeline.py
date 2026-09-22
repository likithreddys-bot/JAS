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

from app.core.events.events import AssistantReply, AudioLevel, StateChanged, TranscriptReady
from app.core.jarvis import Jarvis
from app.brain.sentences import sentences
from app.core.state.states import JarvisState as S
from app.voice.listen.recorder import UtteranceRecorder

log = logging.getLogger("jarvis.voice.pipeline")

ACK_PHRASE = "Yes?"
NOT_UNDERSTOOD = "Sorry, I didn't catch that."
FAILURE_PHRASE = "Sorry, something went wrong."
# Handled locally, without the LLM: end the turn quietly.
CANCEL_PHRASES = {"cancel", "never mind", "nevermind", "stop", "nothing", "forget it"}
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
        max_listen_seconds: float = 15.0,
    ) -> None:
        self._core = core
        self._speaker = speaker
        self._stt = transcriber
        self._recorder = recorder
        self._respond = respond
        self._max_wait = max_listen_seconds + LISTEN_WAIT_SLACK
        self._turns: queue.Queue[None] = queue.Queue()
        core.bus.subscribe(StateChanged, self._on_state)
        threading.Thread(target=self._worker, name="voice-pipeline", daemon=True).start()

    def feed(self, frame: np.ndarray) -> None:
        """Microphone frame while LISTENING (called on the microphone thread)."""
        self._recorder.feed(frame)
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        self._core.bus.publish(AudioLevel(min(rms / 4000.0, 1.0)))

    def _on_state(self, event: StateChanged) -> None:
        if event.current is S.WAKE_DETECTED:
            self._turns.put(None)
        elif event.current is S.SLEEPING:
            self._speaker.stop()
            self._recorder.cancel()

    def _worker(self) -> None:
        while True:
            self._turns.get()
            try:
                self._turn()
            except Exception as exc:
                log.exception("Voice turn failed")
                self._fail(str(exc) or type(exc).__name__)
                try:
                    self._speaker.speak(FAILURE_PHRASE)
                except Exception:
                    log.exception("Could not speak the failure message")

    def _turn(self) -> None:
        state = self._core.state
        # Load speech-to-text while we say "Yes?" and the user talks, hiding the load time.
        threading.Thread(target=self._preload_stt, name="stt-preload", daemon=True).start()

        self._speaker.speak(ACK_PHRASE)
        self._recorder.begin()
        if not state.transition_from(S.WAKE_DETECTED, S.LISTENING):
            self._recorder.cancel()
            return

        audio = self._recorder.wait(self._max_wait)
        if audio is None:
            state.transition_from(S.LISTENING, S.STANDBY, "no speech heard")
            return
        if not state.transition_from(S.LISTENING, S.TRANSCRIBING):
            return

        text = self._stt.transcribe(audio)
        log.info("Heard: %r", text)
        self._core.bus.publish(TranscriptReady(text))

        if _normalize(text) in CANCEL_PHRASES:
            state.transition_from(S.TRANSCRIBING, S.STANDBY, "cancelled by user")
            return
        if not text:
            if state.transition_from(S.TRANSCRIBING, S.RESPONDING):
                self._core.bus.publish(AssistantReply(NOT_UNDERSTOOD))
                self._speaker.speak(NOT_UNDERSTOOD)
                state.transition_from(S.RESPONDING, S.STANDBY)
            return
        if not state.transition_from(S.TRANSCRIBING, S.THINKING):
            return

        spoken = ""
        for sentence in sentences(self._respond(text)):
            if not spoken and not state.transition_from(S.THINKING, S.RESPONDING):
                return
            if state.current is not S.RESPONDING:
                return  # paused / cancelled mid-reply
            spoken = f"{spoken} {sentence}".strip()
            self._core.bus.publish(AssistantReply(spoken))
            if not self._speaker.speak(sentence):
                return
        if not spoken:
            raise RuntimeError("Empty reply")
        state.transition_from(S.RESPONDING, S.STANDBY)

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
