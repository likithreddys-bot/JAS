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
    """Speaks in one of two voices. The second is only loaded if it is ever asked for."""

    def __init__(self, voice: str, models_dir: Path, speed: float = 1.0,
                 higher_voice: str = "") -> None:
        from piper import SynthesisConfig

        self._models_dir = models_dir
        self._names = {"lower": voice, "higher": higher_voice or voice}
        self._voices: dict[str, object] = {}
        self._config = SynthesisConfig(length_scale=1.0 / speed)
        self._kind = "lower"
        self._stop = threading.Event()
        self._cache: dict[tuple[str, str], np.ndarray] = {}
        self._load("lower")

    def _load(self, kind: str):
        from piper import PiperVoice
        from piper.download_voices import download_voice

        if kind in self._voices:
            return self._voices[kind]
        name = self._names[kind]
        model_path = self._models_dir / f"{name}.onnx"
        if not model_path.exists():
            log.info("Downloading voice %r (one time)", name)
            self._models_dir.mkdir(parents=True, exist_ok=True)
            download_voice(name, self._models_dir)
        self._voices[kind] = PiperVoice.load(model_path)
        log.info("Voice %r loaded (%s)", name, kind)
        return self._voices[kind]

    @property
    def _voice(self):
        return self._voices[self._kind]

    @property
    def _rate(self) -> int:
        return self._voice.config.sample_rate

    def use(self, kind: str) -> None:
        """Switch between the "lower" and "higher" voice, loading the second on first use."""
        if kind not in self._names or kind == self._kind:
            return
        self._load(kind)
        self._kind = kind
        log.info("Answering in the %s voice (%s)", kind, self._names[kind])

    def prepare(self, *phrases: str) -> None:
        """Pre-render fixed phrases (e.g. "Yes?") so they play instantly. Also warms up the engine."""
        for phrase in phrases:
            self._cache[(self._kind, phrase)] = np.concatenate(
                [c.audio_int16_array for c in self._voice.synthesize(phrase, self._config)]
            )

    def render(self, text: str) -> bytes:
        """The same voice as a WAV, for sending somewhere else (the phone) instead of playing it."""
        import io
        import wave

        audio = np.concatenate([c.audio_int16_array for c in self._voice.synthesize(text, self._config)])
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(self._rate)
            out.writeframes(audio.tobytes())
        return buffer.getvalue()

    def speak(self, text: str) -> bool:
        """Speak `text`, blocking until done. Returns False if interrupted by `stop()`."""
        self._stop.clear()
        key = (self._kind, text)
        chunks = [self._cache[key]] if key in self._cache else (
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
