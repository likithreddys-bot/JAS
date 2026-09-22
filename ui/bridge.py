"""Bridge between the JARVIS core and QML.

Core events may be published from any thread. They are re-emitted through a Qt
signal, which Qt delivers on the UI thread (queued connection across threads).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from app.core.events.events import AssistantReply, AudioLevel, StateChanged, TranscriptReady
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState
from ui.theme import STATE_COLORS, STATE_LABELS


class UiBridge(QObject):
    stateChanged = Signal()
    captionChanged = Signal()
    levelChanged = Signal()
    menuRequested = Signal()
    _incoming = Signal(object)

    def __init__(self, core: Jarvis) -> None:
        super().__init__()
        self._core = core
        self._state = core.state.current
        self._caption = ""
        self._level = 0.0
        self._incoming.connect(self._apply)
        for event_type in (StateChanged, TranscriptReady, AssistantReply, AudioLevel):
            core.bus.subscribe(event_type, self._incoming.emit)

    def _apply(self, event: object) -> None:
        if isinstance(event, AudioLevel):
            self._level = event.level
            self.levelChanged.emit()
        elif isinstance(event, TranscriptReady):
            self._set_caption(f"“{event.text}”" if event.text else "")
        elif isinstance(event, AssistantReply):
            self._set_caption(event.text)
        elif isinstance(event, StateChanged):
            self._state = event.current
            if event.current is JarvisState.ERROR:
                self._set_caption(event.reason or "")
            elif event.current in (JarvisState.STANDBY, JarvisState.WAKE_DETECTED, JarvisState.SLEEPING):
                self._set_caption("")
            self._level = 0.0
            self.levelChanged.emit()
            self.stateChanged.emit()

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
