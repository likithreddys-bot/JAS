"""Saying "stop" while JAS is talking or working actually stops it.

The wake word already interrupts, but only if you say "Jarvis". People say "stop". So while JAS is
busy, the microphone keeps running through a second recorder; when a short utterance lands it is
transcribed and, if it is a stop phrase, the task is cancelled.

JAS's own voice comes back through the microphone, so speech alone is never treated as a stop —
only a transcript that actually says stop is. Hearing itself simply transcribes to its own words
and is ignored, which makes false cancels harmless instead of maddening.
"""
from __future__ import annotations

import logging
import re
import threading

import numpy as np

from app.core.jarvis import Jarvis
from app.core.state.states import BUSY_STATES
from app.voice.listen.recorder import UtteranceRecorder

log = logging.getLogger("jarvis.voice")

# Short, unambiguous ways of saying "that's enough".
STOP_PHRASES = re.compile(
    r"^(?:jas|jarvis|jazz|hey|ok|okay|no|now)?[,.\s]*"
    r"(?:stop|stop it|stop that|stop stop|cancel|cancel it|shut up|be quiet|quiet|enough|"
    r"that's enough|thats enough|never ?mind|forget it|abort|leave it|wait wait)"
    r"[,.!\s]*(?:jas|jarvis|jazz|please|now|it)?[.!\s]*$", re.I)
MAX_STOP_SECONDS = 4.0  # a stop is short; anything longer is the user talking about something else


def is_stop(text: str) -> bool:
    return bool(text) and bool(STOP_PHRASES.match(text.strip()))


class BargeIn:
    """Listens only while JAS is busy, and only for being told to stop."""

    def __init__(self, core: Jarvis, transcriber, recorder: UtteranceRecorder) -> None:
        self._core = core
        self._stt = transcriber
        self._recorder = recorder
        self._armed = threading.Event()
        self._listening = False
        threading.Thread(target=self._run, name="barge-in", daemon=True).start()

    def feed(self, frame: np.ndarray) -> None:
        """A microphone frame arriving while JAS is busy."""
        if self._listening:
            self._recorder.feed(frame)
        self._armed.set()

    def _run(self) -> None:
        while True:
            self._armed.wait()
            self._armed.clear()
            if self._core.state.current not in BUSY_STATES:
                continue
            self._listen_once()

    def _listen_once(self) -> None:
        self._recorder.begin()
        self._listening = True
        try:
            audio = self._recorder.wait(MAX_STOP_SECONDS + 2.0)
        finally:
            self._listening = False
        if audio is None or self._core.state.current not in BUSY_STATES:
            return
        if len(audio) > MAX_STOP_SECONDS * 16000:
            return  # too long to be "stop"
        try:
            heard = self._stt.transcribe(audio)
        except Exception:
            log.exception("Could not check for a stop word")
            return
        if is_stop(heard):
            log.info("Heard %r while busy: stopping", heard.strip())
            self._core.interrupt("stopped by user")
        elif heard.strip():
            log.debug("Ignoring %r while busy", heard.strip()[:60])
