"""Visual language: one colour, label and facial expression per state, shared by the orb and the tray."""
from __future__ import annotations

from app.core.state.states import JarvisState

S = JarvisState

# Every state is a body in the sky. The colour is that body's, so the orb and the panel behind it
# change together and you can read the state from across the room.
STATE_COLORS: dict[JarvisState, str] = {
    S.STARTING: "#C9B79C",      # Mercury, just arriving
    S.STANDBY: "#FFC46B",       # the Sun, awake and warm
    S.WAKE_DETECTED: "#F5D9A0",  # Venus, bright the moment it is called
    S.LISTENING: "#46C7B0",     # Earth, alive and listening
    S.TRANSCRIBING: "#5A7FE0",  # Neptune, deep water, making sense of it
    S.THINKING: "#E0A96D",      # Jupiter, the big mind
    S.PLANNING: "#E0A96D",      # Jupiter
    S.EXECUTING: "#E8703A",     # Mars, at work
    S.OBSERVING: "#9FE3E8",     # Uranus, cool and watching
    S.RESPONDING: "#E8D9A8",    # Saturn, speaking with its rings out
    S.ERROR: "#FF5C6C",         # no body: an error should not look pretty
    S.SLEEPING: "#93A0BA",      # the Moon, paused
    S.RESTING: "#A9BEE4",       # the Moon, offline for the night
}

STATE_BODY: dict[JarvisState, str] = {
    S.STARTING: "mercury",
    S.STANDBY: "sun",
    S.WAKE_DETECTED: "venus",
    S.LISTENING: "earth",
    S.TRANSCRIBING: "neptune",
    S.THINKING: "jupiter",
    S.PLANNING: "jupiter",
    S.EXECUTING: "mars",
    S.OBSERVING: "uranus",
    S.RESPONDING: "saturn",
    S.ERROR: "",
    S.SLEEPING: "moon",
    S.RESTING: "moon",
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
