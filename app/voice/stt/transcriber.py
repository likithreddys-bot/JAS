"""Speech-to-text with faster-whisper (local, CPU, int8).

The model is loaded on demand and released after a period of inactivity to keep idle RAM low.
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


class Transcriber:
    def __init__(self, model_size: str, models_dir: Path, language: str | None) -> None:
        self._model_size = model_size
        self._models_dir = models_dir
        self._language = language or None  # None = auto-detect
        self._model = None
        self._lock = threading.Lock()
        self._unload_timer: threading.Timer | None = None

    def ensure_loaded(self) -> None:
        with self._lock:
            self._load_locked()

    def transcribe(self, audio: np.ndarray) -> str:
        with self._lock:
            self._load_locked()
            started = time.perf_counter()
            segments, _ = self._model.transcribe(
                audio.astype(np.float32) / 32768.0,
                language=self._language,
                beam_size=1,
                condition_on_previous_text=False,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            log.info(
                "Transcribed %.1f s of audio in %.2f s",
                len(audio) / 16000,
                time.perf_counter() - started,
            )
            self._schedule_unload()
            return text

    def _load_locked(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        started = time.perf_counter()
        # Prefer a manually downloaded copy in <models_dir>/<size>/ (HF downloads can stall).
        local = self._models_dir / self._model_size
        source = str(local) if (local / "model.bin").exists() else self._model_size
        try:
            self._model = WhisperModel(
                source,
                device="cpu",
                compute_type="int8",
                download_root=str(self._models_dir),
            )
        except Exception as exc:
            raise RuntimeError("Speech model not ready (still downloading or damaged)") from exc
        log.info("Whisper %r loaded in %.1f s", self._model_size, time.perf_counter() - started)
        self._schedule_unload()

    def _schedule_unload(self) -> None:
        if self._unload_timer:
            self._unload_timer.cancel()
        self._unload_timer = threading.Timer(IDLE_UNLOAD_SECONDS, self._unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _unload(self) -> None:
        with self._lock:
            if self._model is not None:
                self._model = None
                gc.collect()
                log.info("Whisper unloaded after %d s idle", IDLE_UNLOAD_SECONDS)
