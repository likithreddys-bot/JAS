"""Microphone input as a queue of fixed-size 16 kHz mono int16 frames.

Audio stays in memory only; nothing is written to disk.
"""
from __future__ import annotations

import logging
import queue

import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis.voice.mic")

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 1280  # 80 ms — the frame size openWakeWord expects


class MicrophoneError(Exception):
    pass


class Microphone:
    def __init__(self, device: str | int | None = None, max_queued_frames: int = 50) -> None:
        self._device = device
        self._frames: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_queued_frames)
        self._stream: sd.InputStream | None = None

    @property
    def is_open(self) -> bool:
        return self._stream is not None and self._stream.active

    def open(self) -> None:
        if self._stream is not None:
            return
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=FRAME_SAMPLES,
                device=self._device,
                callback=self._on_audio,
            )
            stream.start()
        except Exception as exc:  # PortAudio raises several types; all mean "no usable mic"
            raise MicrophoneError(_describe(exc)) from exc
        self._stream = stream
        log.info("Microphone opened (%s)", sd.query_devices(stream.device)["name"])

    def close(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            log.exception("Error while closing microphone")
        self._stream = None
        self._drain()
        log.info("Microphone closed")

    def read(self, timeout: float) -> np.ndarray | None:
        """Next frame, or None if none arrived within `timeout` seconds."""
        try:
            return self._frames.get(timeout=timeout)
        except queue.Empty:
            return None

    def _on_audio(self, indata: np.ndarray, frames: int, time, status: sd.CallbackFlags) -> None:
        if status:
            log.debug("Audio status: %s", status)
        try:
            self._frames.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass  # consumer is behind; dropping old audio is better than growing latency

    def _drain(self) -> None:
        while not self._frames.empty():
            self._frames.get_nowait()


def _describe(exc: Exception) -> str:
    try:
        sd.query_devices(kind="input")
    except Exception:
        return "No microphone found"
    return f"Microphone unavailable: {exc}"
