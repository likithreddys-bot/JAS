"""Visual language: one colour, label and facial expression per state, shared by the orb and the tray."""
from __future__ import annotations

from app.core.state.states import JarvisState

S = JarvisState

STATE_COLORS: dict[JarvisState, str] = {
    S.STARTING: "#7FA7FF",
    S.STANDBY: "#4F8CFF",
    S.WAKE_DETECTED: "#6FE3B4",
    S.LISTENING: "#3DDC97",
    S.TRANSCRIBING: "#4DD0C8",
    S.THINKING: "#F5B84B",
    S.PLANNING: "#F5B84B",
    S.EXECUTING: "#FF8A4C",
    S.OBSERVING: "#FF8A4C",
    S.RESPONDING: "#A879FF",
    S.ERROR: "#FF5C6C",
    S.SLEEPING: "#5B6275",
    S.RESTING: "#4F4FB0",
}

# How the face sits in each state. Face.qml turns each mood into lid, brow and pupil positions.
STATE_FACES: dict[JarvisState, str] = {
    S.STARTING: "waking",
    S.STANDBY: "calm",
    S.WAKE_DETECTED: "alert",
    S.LISTENING: "listening",
    S.TRANSCRIBING: "thinking",
    S.THINKING: "thinking",
    S.PLANNING: "thinking",
    S.EXECUTING: "focused",
    S.OBSERVING: "focused",
    S.RESPONDING: "warm",
    S.ERROR: "concerned",
    S.SLEEPING: "asleep",
    S.RESTING: "asleep",
}

STATE_LABELS: dict[JarvisState, str] = {
    S.STARTING: "Starting",
    S.STANDBY: "Ready",
    S.WAKE_DETECTED: "Yes?",
    S.LISTENING: "Listening",
    S.TRANSCRIBING: "Understanding",
    S.THINKING: "Thinking",
    S.PLANNING: "Planning",
    S.EXECUTING: "Working",
    S.OBSERVING: "Checking",
    S.RESPONDING: "Speaking",
    S.ERROR: "Something went wrong",
    S.SLEEPING: "Paused",
    S.RESTING: "Resting",
}
