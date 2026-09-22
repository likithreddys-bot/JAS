"""Bridge between the JARVIS core and QML.

Core events may be published from any thread. They are re-emitted through a Qt
signal, which Qt delivers on the UI thread (queued connection across threads).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from app.core.events.events import (
    AssistantReply,
    AudioLevel,
    StateChanged,
    ToolFinished,
    ToolStarted,
    TranscriptReady,
)
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState
from ui.theme import STATE_COLORS, STATE_LABELS

LINGER_MS = 8000  # keep the last reply and steps visible for a moment after finishing


class UiBridge(QObject):
    stateChanged = Signal()
    captionChanged = Signal()
    levelChanged = Signal()
    stepsChanged = Signal()
    menuRequested = Signal()
    _incoming = Signal(object)

    def __init__(self, core: Jarvis) -> None:
        super().__init__()
        self._core = core
        self._state = core.state.current
        self._caption = ""
        self._level = 0.0
        self._steps: list[dict] = []
        self._linger = QTimer(self, singleShot=True, interval=LINGER_MS)
        self._linger.timeout.connect(self._clear)
        self._incoming.connect(self._apply)
        for event_type in (StateChanged, TranscriptReady, AssistantReply, AudioLevel, ToolStarted, ToolFinished):
            core.bus.subscribe(event_type, self._incoming.emit)

    def _apply(self, event: object) -> None:
        if isinstance(event, AudioLevel):
            self._level = event.level
            self.levelChanged.emit()
        elif isinstance(event, TranscriptReady):
            self._set_caption(f"“{event.text}”" if event.text else "")
        elif isinstance(event, AssistantReply):
            self._set_caption(event.text)
        elif isinstance(event, ToolStarted):
            self._steps = self._steps + [{"id": event.step_id, "label": event.label, "status": "running"}]
            self.stepsChanged.emit()
        elif isinstance(event, ToolFinished):
            status = "done" if event.ok else "failed"
            self._steps = [dict(s, status=status) if s["id"] == event.step_id else s for s in self._steps]
            self.stepsChanged.emit()
        elif isinstance(event, StateChanged):
            self._state = event.current
            self._linger.stop()
            if event.current is JarvisState.ERROR:
                self._set_caption(event.reason or "")
            elif event.current in (JarvisState.WAKE_DETECTED, JarvisState.SLEEPING):
                self._clear()
            elif event.current is JarvisState.RESTING:
                self._clear()
                self._set_caption("Say \u201cwake up, Jarvis\u201d")
            elif event.current is JarvisState.STANDBY:
                self._linger.start()
            self._level = 0.0
            self.levelChanged.emit()
            self.stateChanged.emit()

    def _clear(self) -> None:
        self._set_caption("")
        self._steps = []
        self.stepsChanged.emit()

    def _set_caption(self, text: str) -> None:
        self._caption = text
        self.captionChanged.emit()

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state.value

    @Property(str, notify=stateChanged)
    def stateColor(self) -> str:
        return STATE_COLORS[self._state]

    @Property(str, notify=stateChanged)
    def stateLabel(self) -> str:
        return STATE_LABELS[self._state]

    @Property(str, notify=captionChanged)
    def caption(self) -> str:
        """Error reason, what the user said, or JARVIS's reply — whichever is current."""
        return self._caption

    @Property("QVariantList", notify=stepsChanged)
    def steps(self) -> list[dict]:
        """Tool steps of the current task: {label, status: running|done|failed}."""
        return self._steps

    @Property(float, notify=levelChanged)
    def level(self) -> float:
        return self._level

    @Property(bool, notify=stateChanged)
    def paused(self) -> bool:
        return self._core.paused

    @Slot()
    def togglePause(self) -> None:
        self._core.toggle_pause()

    @Slot()
    def requestMenu(self) -> None:
        self.menuRequested.emit()
