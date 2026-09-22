"""Text-to-speech with Piper (local), played through the default output device.

Playback is written in short blocks so `stop()` interrupts within ~50 ms.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis.voice.tts")

BLOCK_SECONDS = 0.05
TAIL_SECONDS = 0.15  # trailing silence so the device doesn't clip the last syllable


class Speaker:
    def __init__(self, voice: str, models_dir: Path, speed: float = 1.0) -> None:
        from piper import PiperVoice, SynthesisConfig
        from piper.download_voices import download_voice

        model_path = models_dir / f"{voice}.onnx"
        if not model_path.exists():
            log.info("Downloading voice %r (one time)", voice)
            models_dir.mkdir(parents=True, exist_ok=True)
            download_voice(voice, models_dir)
        self._voice = PiperVoice.load(model_path)
        self._config = SynthesisConfig(length_scale=1.0 / speed)
        self._rate = self._voice.config.sample_rate
        self._stop = threading.Event()
        self._cache: dict[str, np.ndarray] = {}
        log.info("Voice %r loaded (%d Hz)", voice, self._rate)

    def prepare(self, *phrases: str) -> None:
        """Pre-render fixed phrases (e.g. "Yes?") so they play instantly. Also warms up the engine."""
        for phrase in phrases:
            self._cache[phrase] = np.concatenate(
                [c.audio_int16_array for c in self._voice.synthesize(phrase, self._config)]
            )

    def speak(self, text: str) -> bool:
        """Speak `text`, blocking until done. Returns False if interrupted by `stop()`."""
        self._stop.clear()
        chunks = [self._cache[text]] if text in self._cache else (
            c.audio_int16_array for c in self._voice.synthesize(text, self._config)
        )
        block = int(self._rate * BLOCK_SECONDS)
        with sd.OutputStream(samplerate=self._rate, channels=1, dtype="int16") as out:
            for audio in chunks:
                for i in range(0, len(audio), block):
                    if self._stop.is_set():
                        out.abort()
                        log.info("Speech interrupted")
                        return False
                    out.write(audio[i : i + block])
            out.write(np.zeros(int(self._rate * TAIL_SECONDS), dtype=np.int16))
        return True

    def stop(self) -> None:
        self._stop.set()
