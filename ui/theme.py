"""Visual language: one colour, label and look per state, shared by the orb, the tray and the phone.

VEM's palette is the website's: black, champagne gold, and a little ember red and green-gold, with no
blue anywhere (website/src/core/states.ts has the same numbers). A state is read from the colour,
the brightness and how the rings of light move (ui/qml/GlassOrb.qml); there is no face.
"""
from __future__ import annotations

from app.core.state.states import JarvisState

S = JarvisState

# The accent each state washes the glass with. All are mixes of the website's tokens:
# gold #E8BE76, ivory #F7F1E6, ember #E2553F, green-gold #A8CF78, warm grey #A69C8D, black #080706.
STATE_COLORS: dict[JarvisState, str] = {
    S.STARTING: "#A69C8D",       # warm grey, just arriving
    S.STANDBY: "#E8BE76",        # gold, awake and warm
    S.WAKE_DETECTED: "#F1DDB0",  # pale gold, bright the moment it is called
    S.LISTENING: "#EDD09D",      # brighter gold, the rings ripple with your voice
    S.TRANSCRIBING: "#BB9960",   # dimmed gold, making sense of it
    S.THINKING: "#BB9960",       # dimmed gold, motes circling
    S.PLANNING: "#BB9960",
    S.EXECUTING: "#C2C877",      # green-gold, at work
    S.OBSERVING: "#C2C877",
    S.RESPONDING: "#E8BE76",     # gold, pulsing with its own voice
    S.ERROR: "#E2553F",          # ember: an error should not look pretty
    S.SLEEPING: "#A69C8D",       # warm grey, light nearly out
    S.RESTING: "#A69C8D",
}

# Only the old phone apps (the ones with a planet and eyes) still read this, from /state; the desktop
# window no longer draws planets. It can go once nobody runs a build from before VEM.
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

# Which look GlassOrb.qml draws in each state: how bright the light inside is, how fast the rings
# revolve, whether motes circle or an arc runs, whether it is paused down to a single dot.
STATE_LOOKS: dict[JarvisState, str] = {
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
