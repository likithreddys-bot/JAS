"""Pitch measurement, which decides whether JAS answers in a higher or lower voice."""
import numpy as np
import pytest

from app.voice.pitch import BOUNDARY_HZ, SAMPLE_RATE, frame_pitch, median_pitch, voice_for


def tone(hz: float, seconds: float = 1.0, amplitude: int = 6000) -> np.ndarray:
    """A voice-like tone: a fundamental plus the harmonics real speech carries."""
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    wave = sum(amplitude / (n + 1) * np.sin(2 * np.pi * hz * (n + 1) * t) for n in range(5))
    return wave.astype(np.int16)


@pytest.mark.parametrize("hz", [100, 130, 165, 200, 240])
def test_pitch_is_measured_within_a_few_hz(hz):
    assert abs(frame_pitch(tone(hz, 0.2)[:1024]) - hz) < hz * 0.06
    assert abs(median_pitch(tone(hz)) - hz) < hz * 0.06


def test_silence_and_noise_have_no_pitch():
    assert frame_pitch(np.zeros(1024, dtype=np.int16)) == 0.0
    assert median_pitch(np.zeros(SAMPLE_RATE, dtype=np.int16)) == 0.0
    rng = np.random.default_rng(7)
    assert median_pitch((rng.normal(0, 3000, SAMPLE_RATE)).astype(np.int16)) == 0.0


def test_a_low_voice_and_a_high_voice_pick_different_voices():
    assert voice_for(tone(110)) == "lower"
    assert voice_for(tone(215)) == "higher"


def test_an_ambiguous_voice_keeps_whatever_is_already_in_use():
    """Near the boundary JAS must not flip about mid-conversation."""
    borderline = tone(BOUNDARY_HZ)
    assert voice_for(borderline, current="lower") == "lower"
    assert voice_for(borderline, current="higher") == "higher"


def test_too_little_speech_changes_nothing():
    assert voice_for(tone(220, seconds=0.05), current="lower") == "lower"
    assert voice_for(np.zeros(SAMPLE_RATE, dtype=np.int16), current="higher") == "higher"
