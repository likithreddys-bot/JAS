"""Picks the speech-to-text backend: CPU (faster-whisper) or OpenVINO (this machine's Intel GPU),
by config - see STT_BACKEND in app/config/settings.py for the measurements behind the default.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("jarvis.voice.stt")


def make_transcriber(backend: str, device: str, model_size: str, models_dir: Path,
                     language: str | None, vocabulary: str = "") -> Any:
    """Returns a Transcriber or OpenVinoTranscriber - callers only need `transcribe`, `backlog`,
    `set_vocabulary` and `ensure_loaded`, which both provide identically.

    Falls back to the CPU backend if "openvino" was asked for but the model has not been exported
    yet (scripts/export_whisper_openvino.py), rather than refusing to start at all.
    """
    from app.voice.stt.transcriber import Transcriber

    if backend == "openvino":
        ov_dir = models_dir / "whisper-openvino" / model_size
        if (ov_dir / "openvino_encoder_model.xml").exists():
            from app.voice.stt.openvino_transcriber import OpenVinoTranscriber
            log.info("Using OpenVINO speech recognition on %s", device)
            return OpenVinoTranscriber(ov_dir, device=device, language=language, vocabulary=vocabulary)
        log.warning(
            "STT_BACKEND=openvino but no exported model at %s - run "
            "scripts/export_whisper_openvino.py; using the CPU backend for now", ov_dir,
        )

    return Transcriber(model_size, models_dir / "whisper", language, vocabulary)
