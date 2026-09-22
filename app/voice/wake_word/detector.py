"""Wake-word detection on top of openWakeWord, with thresholding and a cooldown."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import numpy as np

log = logging.getLogger("jarvis.voice.wake_word")

COOLDOWN_FRAMES = 25  # ~2 s at 80 ms/frame, so one utterance triggers once


class WakeWordDetector:
    def __init__(
        self,
        predict: Callable[[np.ndarray], float],
        reset: Callable[[], None],
        threshold: float,
        cooldown_frames: int = COOLDOWN_FRAMES,
    ) -> None:
        self._predict = predict
        self._reset = reset
        self._threshold = threshold
        self._cooldown_frames = cooldown_frames
        self._cooldown = 0

    def process(self, frame: np.ndarray) -> float | None:
        """Feed one frame. Returns the score if the wake word fired on this frame."""
        score = self._predict(frame)
        if self._cooldown:
            self._cooldown -= 1
            return None
        if score >= self._threshold:
            self._cooldown = self._cooldown_frames
            self._reset()
            return score
        return None

    def reset(self) -> None:
        self._cooldown = 0
        self._reset()


def load_openwakeword(model_name: str, threshold: float) -> WakeWordDetector:
    """Load a pre-trained openWakeWord model (downloaded once on first use)."""
    import openwakeword
    from openwakeword.model import Model
    from openwakeword.utils import download_models

    models_dir = Path(openwakeword.__file__).parent / "resources" / "models"
    if not any(models_dir.glob(f"{model_name}*.onnx")):
        log.info("Downloading wake-word model %r (one time)", model_name)
        download_models(model_names=[model_name])

    model = Model(wakeword_models=[model_name], inference_framework="onnx")
    key = next(iter(model.models))
    log.info("Wake-word model %r loaded (threshold %.2f)", key, threshold)
    return WakeWordDetector(
        predict=lambda frame: float(model.predict(frame)[key]),
        reset=model.reset,
        threshold=threshold,
    )
