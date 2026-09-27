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


def load_openwakeword(model_name: str, threshold: float, models_dir: Path | None = None) -> WakeWordDetector:
    """Load an openWakeWord model.

    `model_name` is either a pre-trained name ("hey_jarvis", downloaded once on first use) or the
    file name of a model shipped with JARVIS in `models_dir` ("jarvis_v1.onnx"), which is how the
    single-word "Jarvis" is supported — openWakeWord has no pre-trained model for it.
    """
    import openwakeword
    from openwakeword.model import Model
    from openwakeword.utils import download_models

    built_in = Path(openwakeword.__file__).parent / "resources" / "models"
    if model_name.endswith(".onnx"):
        path = (models_dir or Path()) / model_name
        if not path.exists():
            raise FileNotFoundError(f"Wake-word model {path} is missing")
        if not (built_in / "melspectrogram.onnx").exists():
            download_models(model_names=[])  # the shared feature extractors every model needs
        wake_models = [str(path)]
    else:
        if not any(built_in.glob(f"{model_name}*.onnx")):
            log.info("Downloading wake-word model %r (one time)", model_name)
            download_models(model_names=[model_name])
        wake_models = [model_name]

    model = Model(wakeword_models=wake_models, inference_framework="onnx")
    key = next(iter(model.models))
    log.info("Wake-word model %r loaded (threshold %.2f)", key, threshold)
    return WakeWordDetector(
        predict=lambda frame: float(model.predict(frame)[key]),
        reset=model.reset,
        threshold=threshold,
    )


class PorcupineDetector:
    """Picovoice Porcupine keyword spotting (e.g. the built-in "jarvis"); same interface as WakeWordDetector.

    Porcupine consumes fixed 512-sample frames, so our 1280-sample mic frames are re-chunked.
    """

    def __init__(self, engine) -> None:
        self._engine = engine
        self._frame_length = engine.frame_length
        self._buffer = np.zeros(0, dtype=np.int16)

    def process(self, frame: np.ndarray) -> float | None:
        self._buffer = np.concatenate([self._buffer, frame])
        fired = False
        while len(self._buffer) >= self._frame_length:
            chunk, self._buffer = self._buffer[: self._frame_length], self._buffer[self._frame_length :]
            if self._engine.process(chunk.tolist()) >= 0:
                fired = True
        return 1.0 if fired else None  # Porcupine gives a yes/no, not a score

    def reset(self) -> None:
        self._buffer = np.zeros(0, dtype=np.int16)


def load_porcupine(access_key: str, keyword: str, sensitivity: float) -> PorcupineDetector:
    import pvporcupine

    if not access_key:
        raise ValueError("No PICOVOICE_ACCESS_KEY in .env")
    try:
        engine = pvporcupine.create(access_key=access_key, keywords=[keyword], sensitivities=[sensitivity])
    except pvporcupine.PorcupineActivationLimitError as exc:
        raise ValueError("Picovoice key has reached its device limit") from exc
    except pvporcupine.PorcupineActivationError as exc:
        raise ValueError("Picovoice AccessKey was rejected") from exc
    log.info("Porcupine wake word %r loaded (sensitivity %.2f)", keyword, sensitivity)
    return PorcupineDetector(engine)
