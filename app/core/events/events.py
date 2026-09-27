"""Event types published on the EventBus."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.state.states import JarvisState


@dataclass(frozen=True)
class StateChanged:
    previous: JarvisState
    current: JarvisState
    reason: str | None = None


@dataclass(frozen=True)
class WakeWordDetected:
    score: float


@dataclass(frozen=True)
class MicrophoneUnavailable:
    reason: str


@dataclass(frozen=True)
class MicrophoneRecovered:
    pass


@dataclass(frozen=True)
class AudioLevel:
    """Microphone loudness 0..1 while listening (drives the audio-reactive orb)."""
    level: float


@dataclass(frozen=True)
class TranscriptReady:
    text: str


@dataclass(frozen=True)
class AssistantReply:
    text: str


@dataclass(frozen=True)
class ToolStarted:
    step_id: int
    label: str
    tool: str = ""  # the tool's name, so the UI can react to what kind of work it is


@dataclass(frozen=True)
class ToolFinished:
    step_id: int
    label: str
    ok: bool
    error: str = ""
    tool: str = ""


@dataclass(frozen=True)
class TaskInterrupted:
    """The user said the wake word (or paused) while JARVIS was busy: stop everything now."""
    reason: str
