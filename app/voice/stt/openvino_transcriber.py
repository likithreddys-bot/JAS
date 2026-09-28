"""Speech-to-text with OpenVINO on the Intel NPU.

The CPU-only faster-whisper path (`transcriber.py`) was the whole reason "milliseconds" was never
true: a 1.6 s clip once took 47.7 s to transcribe under load, because one CPU was carrying the
wake-word pipeline, barge-in and every phone at once. This machine's chip (Core Ultra 5 115U) has a
dedicated NPU built for exactly this kind of work, and faster-whisper cannot use it - it only knows
CPU or an NVIDIA GPU. OpenVINO can.

Same public interface as `Transcriber`, deliberately: `transcribe()`, `backlog`, `set_vocabulary()`,
`ensure_loaded()`. Chosen by STT_BACKEND in settings, so it is a swap, not a rewrite of everything
that calls it - and the CPU path stays as a fallback if the NPU ever misbehaves in real use.

The model must be exported once with `scripts/export_whisper_openvino.py` before this can load -
OpenVINO needs its own IR format, converted from the original HuggingFace checkpoint (not from the
ctranslate2 files faster-whisper already has cached, which are a different format entirely).
"""
from __future__ import annotations

import gc
import logging
import threading
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("jarvis.voice.stt")

IDLE_UNLOAD_SECONDS = 300


class OpenVinoTranscriber:
    def __init__(self, model_dir: Path, device: str = "NPU", language: str | None = None,
                 vocabulary: str = "") -> None:
        self._model_dir = model_dir
        self._device = device
        self._language = language or None  # None = auto-detect
        self._pipeline = None
        self._lock = threading.Lock()
        self._unload_timer: threading.Timer | None = None
        self._pending = 0            # callers currently waiting for, or holding, the lock
        self._pending_lock = threading.Lock()  # protects the counter only; always uncontended
        self.set_vocabulary(vocabulary)

    @property
    def backlog(self) -> int:
        """How many callers are queued behind the lock right now, including whoever holds it.

        Mirrors `Transcriber.backlog` exactly - the phone's backpressure check doesn't know or
        care which backend answered it.
        """
        with self._pending_lock:
            return self._pending

    def set_vocabulary(self, vocabulary: str) -> None:
        # Passed as `hotwords`, which OpenVINO GenAI applies to every processing window - unlike
        # faster-whisper's `initial_prompt`, which only biases the first one.
        self._hotwords = vocabulary.strip().rstrip(".") or None

    def ensure_loaded(self) -> None:
        with self._lock:
            self._load_locked()

    def transcribe(self, audio: np.ndarray) -> str:
        with self._pending_lock:
            self._pending += 1
        try:
            with self._lock:
                self._load_locked()
                started = time.perf_counter()
                samples = (audio.astype(np.float32) / 32768.0).tolist()
                kwargs: dict = {}
                if self._hotwords:
                    kwargs["hotwords"] = self._hotwords
                if self._language:
                    kwargs["language"] = f"<|{self._language}|>"
                result = self._pipeline.generate(samples, **kwargs)
                text = " ".join(t.strip() for t in result.texts if t.strip()).strip()
                log.info(
                    "Transcribed %.1f s of audio in %.2f s (%s)",
                    len(audio) / 16000,
                    time.perf_counter() - started,
                    self._device,
                )
                self._schedule_unload()
                return text
        finally:
            with self._pending_lock:
                self._pending -= 1

    def _load_locked(self) -> None:
        if self._pipeline is not None:
            return
        import openvino_genai as ovg

        if not (self._model_dir / "openvino_encoder_model.xml").exists():
            raise RuntimeError(
                f"No OpenVINO Whisper model at {self._model_dir} - run "
                "scripts/export_whisper_openvino.py first"
            )
        started = time.perf_counter()
        try:
            self._pipeline = ovg.WhisperPipeline(str(self._model_dir), device=self._device)
        except Exception as exc:
            raise RuntimeError(f"Could not load the OpenVINO Whisper model on {self._device}") from exc
        log.info("OpenVINO Whisper loaded on %s in %.1f s", self._device, time.perf_counter() - started)
        self._schedule_unload()

    def _schedule_unload(self) -> None:
        if self._unload_timer:
            self._unload_timer.cancel()
        self._unload_timer = threading.Timer(IDLE_UNLOAD_SECONDS, self._unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _unload(self) -> None:
        with self._lock:
            if self._pipeline is not None:
                self._pipeline = None
                gc.collect()
                log.info("OpenVINO Whisper unloaded after %d s idle", IDLE_UNLOAD_SECONDS)
