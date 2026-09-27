"""How high the speaker's voice is, so JAS can answer in a voice that matches.

This measures **pitch**, nothing more. Voices do not divide neatly, and plenty of people sit near
the boundary or cross it, so the result is a hint and the wrong answer is only a wrong voice. It is
deliberately sticky: one ambiguous sentence should never flip the voice mid-conversation, and the
setting can be turned off entirely (VOICE_MATCHES_SPEAKER=false).
"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger("jarvis.voice")

SAMPLE_RATE = 16000
MIN_HZ, MAX_HZ = 70, 320        # the range of ordinary speech; anything outside is noise
BOUNDARY_HZ = 165.0             # above this a voice usually reads as higher-pitched
MARGIN_HZ = 18.0                # a band around the boundary where we simply don't decide
MIN_VOICED_FRAMES = 8           # ignore a stray syllable: roughly a quarter second of voiced speech


def frame_pitch(frame: np.ndarray) -> float:
    """Fundamental frequency of one frame in Hz, or 0 if it isn't voiced."""
    signal = frame.astype(np.float64)
    signal -= signal.mean()
    energy = np.sqrt(np.mean(signal ** 2))
    if energy < 250:  # too quiet to be speech
        return 0.0

    # Autocorrelation: a voiced frame repeats itself one pitch period later.
    correlation = np.correlate(signal, signal, mode="full")[len(signal) - 1:]
    lo, hi = SAMPLE_RATE // MAX_HZ, SAMPLE_RATE // MIN_HZ
    if hi >= len(correlation):
        return 0.0
    window = correlation[lo:hi]
    if not len(window) or correlation[0] <= 0:
        return 0.0
    peak = int(np.argmax(window)) + lo
    if correlation[peak] / correlation[0] < 0.3:  # no convincing repeat: unvoiced or noise
        return 0.0
    return SAMPLE_RATE / peak


def median_pitch(audio: np.ndarray, frame_size: int = 1024) -> float:
    """Median pitch across the voiced parts of an utterance, or 0 if there aren't enough."""
    voiced = [p for i in range(0, len(audio) - frame_size, frame_size)
              if (p := frame_pitch(audio[i:i + frame_size])) > 0]
    if len(voiced) < MIN_VOICED_FRAMES:
        return 0.0
    return float(np.median(voiced))


def voice_for(audio: np.ndarray, current: str | None = None) -> str | None:
    """"higher", "lower", or `current` when the utterance is too short or too close to call."""
    pitch = median_pitch(audio)
    if pitch <= 0:
        return current
    if pitch > BOUNDARY_HZ + MARGIN_HZ:
        return "higher"
    if pitch < BOUNDARY_HZ - MARGIN_HZ:
        return "lower"
    return current  # inside the uncertain band: keep whatever voice is already in use
