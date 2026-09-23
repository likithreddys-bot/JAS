"""In-memory activity timeline for the dashboard: what JARVIS heard, did and said."""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

from app.core.events.bus import EventBus
from app.core.events.events import (
    AssistantReply,
    MicrophoneUnavailable,
    StateChanged,
    ToolFinished,
    TranscriptReady,
    WakeWordDetected,
)
from app.core.state.states import JarvisState

MAX_ENTRIES = 200


class ActivityLog:
    def __init__(self, bus: EventBus) -> None:
        self._entries: deque[dict] = deque(maxlen=MAX_ENTRIES)
        self._lock = threading.Lock()
        self._last_reply = ""
        self.requests_today = 0
        self.actions_today = 0
        for event_type in (WakeWordDetected, TranscriptReady, AssistantReply, ToolFinished, StateChanged,
                           MicrophoneUnavailable):
            bus.subscribe(event_type, self._on_event)

    def entries(self) -> list[dict]:
        with self._lock:
            return list(reversed(self._entries))  # newest first

    def _add(self, icon: str, text: str) -> None:
        with self._lock:
            self._entries.append({"time": datetime.now().strftime("%I:%M %p").lstrip("0"), "icon": icon, "text": text})

    def _on_event(self, event: object) -> None:
        if isinstance(event, WakeWordDetected):
            self._add("\U0001f3a4", "Wake word heard")
        elif isinstance(event, TranscriptReady) and event.text:
            self.requests_today += 1
            self._add("\U0001f5e3", f"“{event.text}”")
        elif isinstance(event, AssistantReply):
            # Replies arrive sentence by sentence and grow: update the entry instead of repeating it.
            with self._lock:
                growing = (self._entries and self._last_reply and event.text.startswith(self._last_reply)
                           and self._entries[-1]["text"] == self._last_reply)
                if growing:
                    self._entries[-1] = dict(self._entries[-1], text=event.text)
                self._last_reply = event.text
            if not growing:
                self._add("\U0001f916", event.text)
        elif isinstance(event, ToolFinished):
            self.actions_today += 1
            self._add("✓" if event.ok else "✕", event.label + (f" — {event.error}" if event.error else ""))
        elif isinstance(event, MicrophoneUnavailable):
            self._add("⚠", event.reason)
        elif isinstance(event, StateChanged):
            if event.current is JarvisState.RESTING:
                self._add("\U0001f319", "Went offline (resting)")
            elif event.current is JarvisState.SLEEPING:
                self._add("⏸", "Paused")
            elif event.current is JarvisState.ERROR:
                self._add("⚠", event.reason or "Something went wrong")
