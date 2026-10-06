"""How the assistant sounds in each mood.

Neither Kokoro nor Piper has an emotion control, so mood is carried by what they do have: pace and
loudness (the wording comes from the pipeline and the persona). Greeting and "done" are quick and
bright, confirming is slower so the details are heard, errors are calmer and quieter, never chirpy.
"""
from __future__ import annotations

# mood: (speed multiplier on top of TTS_SPEED, gain 0-1)
MOODS: dict[str, tuple[float, float]] = {
    "reply": (1.04, 0.95),
    "greeting": (1.10, 1.00),
    "working": (1.12, 1.00),
    "confirming": (0.93, 0.95),
    "done": (1.12, 1.00),
    "error": (0.95, 0.85),
    "warning": (0.86, 1.00),
}


def style(mood: str) -> tuple[float, float]:
    """Speed multiplier and gain for `mood`; unknown moods sound like an ordinary reply."""
    return MOODS.get(mood, MOODS["reply"])
