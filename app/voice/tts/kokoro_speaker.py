"""Text-to-speech with Kokoro (local, ONNX on CPU), played through the default output device.

Kokoro-82M sounds far more natural and lively than Piper. The half-precision model is used: measured
at 0.6 s to render 2.2 s of speech on a 4-core CPU, ~375 MB resident, 1.3 s to load (the full-precision
model is no faster and takes ~500 MB; the int8 one is smaller but slower than real time).

Same interface as `Speaker` (Piper), so the pipeline, the phone remote and barge-in need no change.
Playback is written in short blocks so `stop()` interrupts within ~50 ms.
"""
from __future__ import annotations

import logging
import threading
import urllib.request
from pathlib import Path

import numpy as np
import sounddevice as sd

from app.voice.tts.moods import style

log = logging.getLogger("jarvis.voice.tts")

BLOCK_SECONDS = 0.05
TAIL_SECONDS = 0.15
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILE = "kokoro-v1.0.fp16.onnx"
VOICES_FILE = "voices-v1.0.bin"


def ensure_model(models_dir: Path) -> tuple[Path, Path]:
    """The model and voice files, downloaded once (~200 MB) if they are not there yet."""
    models_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in (MODEL_FILE, VOICES_FILE):
        path = models_dir / name
        if not path.exists():
            log.info("Downloading Kokoro %s (one time)", name)
            part = path.with_suffix(path.suffix + ".part")
            urllib.request.urlretrieve(RELEASE + name, part)
            part.rename(path)
        paths.append(path)
    return paths[0], paths[1]


class KokoroSpeaker:
    """Speaks in one Kokoro voice (a second, for higher-pitched speakers, is optional)."""

    def __init__(self, voice: str, models_dir: Path, speed: float = 1.0, higher_voice: str = "",
                 lang: str = "en-us") -> None:
        from kokoro_onnx import Kokoro

        model, voices = ensure_model(models_dir)
        self._kokoro = Kokoro(str(model), str(voices))
        known = set(self._kokoro.get_voices())
        if voice not in known:
            raise ValueError(f"Kokoro has no voice {voice!r}")
        self._names = {"lower": voice, "higher": higher_voice if higher_voice in known else voice}
        self._kind = "lower"
        self._speed = speed
        self._lang = lang
        self._rate = 24000
        self._stop = threading.Event()
        self._cache: dict[tuple[str, str, str], np.ndarray] = {}
        log.info("Kokoro voice %r loaded", voice)

    def use(self, kind: str) -> None:
        if kind in self._names and kind != self._kind:
            self._kind = kind
            log.info("Answering in the %s voice (%s)", kind, self._names[kind])

    def _synth(self, text: str, mood: str) -> np.ndarray:
        """int16 audio for `text` in `mood`."""
        key = (self._kind, mood, text)
        if key in self._cache:
            return self._cache[key]
        speed, gain = style(mood)
        audio, self._rate = self._kokoro.create(text, voice=self._names[self._kind],
                                                speed=self._speed * speed, lang=self._lang)
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak > 0:
            audio = audio / peak * 0.9 * gain  # even loudness across sentences, then the mood's level
        return (np.clip(audio, -1, 1) * 32767).astype(np.int16)

    def prepare(self, *phrases: str | tuple[str, str]) -> None:
        """Pre-render fixed phrases so they play instantly. Each is text or (text, mood)."""
        for p in phrases:
            text, mood = (p, "reply") if isinstance(p, str) else p
            self._cache[(self._kind, mood, text)] = self._synth(text, mood)

    def render(self, text: str, mood: str = "reply") -> bytes:
        """The same voice as a WAV, for sending somewhere else (the phone) instead of playing it."""
        import io
        import wave

        audio = self._synth(text, mood)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(self._rate)
            out.writeframes(audio.tobytes())
        return buffer.getvalue()

    def speak(self, text: str, mood: str = "reply") -> bool:
        """Speak `text`, blocking until done. Returns False if interrupted by `stop()`."""
        self._stop.clear()
        audio = self._synth(text, mood)
        if self._stop.is_set():
            return False
        block = int(self._rate * BLOCK_SECONDS)
        with sd.OutputStream(samplerate=self._rate, channels=1, dtype="int16") as out:
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
