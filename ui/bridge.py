"""Bridge between the assistant core and QML.

Core events may be published from any thread. They are re-emitted through a Qt
signal, which Qt delivers on the UI thread (queued connection across threads).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QCursor

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
from ui.theme import STATE_BODY, STATE_COLORS, STATE_LABELS, STATE_LOOKS

LINGER_MS = 8000  # keep the last reply and steps visible for a moment after finishing
GAZE_MS = 50  # how often the orb checks where the mouse is
GAZE_REACH = 380.0  # px from the orb at which the light inside leans as far as it goes


def gaze_direction(cursor: tuple[int, int], centre: tuple[int, int],
                   reach: float = GAZE_REACH) -> tuple[float, float]:
    """Which way the light inside the orb should lean, as x/y in -1..1. Close to the orb it barely moves."""
    dx, dy = cursor[0] - centre[0], cursor[1] - centre[1]
    distance = math.hypot(dx, dy)
    if distance < 1.0:
        return 0.0, 0.0
    pull = min(1.0, distance / reach)
    return dx / distance * pull, dy / distance * pull


class UiBridge(QObject):
    stateChanged = Signal()
    captionChanged = Signal()
    levelChanged = Signal()
    stepsChanged = Signal()
    gazeChanged = Signal()
    menuRequested = Signal()
    _incoming = Signal(object)

    def __init__(self, core: Jarvis, assistant_name: str = "VEM", wake_phrase: str = "Jarvis") -> None:
        super().__init__()
        self._core = core
        self._name = assistant_name
        self._wake_phrase = wake_phrase
        self._state = core.state.current
        self._caption = ""
        self._level = 0.0
        self._steps: list[dict] = []
        self._centre: tuple[int, int] | None = None
        self._gaze = (0.0, 0.0)
        self._linger = QTimer(self, singleShot=True, interval=LINGER_MS)
        self._linger.timeout.connect(self._clear)
        self._gaze_timer = QTimer(self, interval=GAZE_MS)
        self._gaze_timer.timeout.connect(self._look)
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
            self._watch(STATE_LOOKS[event.current] != "asleep")  # a paused orb doesn't need to follow the mouse

    def _watch(self, on: bool) -> None:
        if on and self._centre:
            self._gaze_timer.start()
        elif not on:
            self._gaze_timer.stop()

    def _look(self) -> None:
        position = QCursor.pos()
        gaze = gaze_direction((position.x(), position.y()), self._centre)
        if abs(gaze[0] - self._gaze[0]) + abs(gaze[1] - self._gaze[1]) > 0.004:  # skip repaints nobody would see
            self._gaze = gaze
            self.gazeChanged.emit()

    def _clear(self) -> None:
        self._set_caption("")
        self._steps = []
        self.stepsChanged.emit()

    def _set_caption(self, text: str) -> None:
        self._caption = text
        self.captionChanged.emit()

    @Property(str, constant=True)
    def assistantName(self) -> str:
        return self._name

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state.value

    @Property(str, notify=stateChanged)
    def stateColor(self) -> str:
        return STATE_COLORS[self._state]

    @Property(str, notify=stateChanged)
    def stateLabel(self) -> str:
        return STATE_LABELS[self._state]

    @Property(str, notify=stateChanged)
    def look(self) -> str:
        """Which look the orb wears: calm, alert, listening, thinking, focused, warm, concerned, asleep."""
        return STATE_LOOKS[self._state]

    @Property(str, notify=stateChanged)
    def body(self) -> str:
        """The old planet name for this state. Only old phone builds read it; the orb no longer draws it."""
        return STATE_BODY.get(self._state, "")

    @Property(str, notify=stateChanged)
    def sky(self) -> str:
        """"sun" or "moon" for the two states that used to have their own sky; kept for the tests that pin them."""
        return self.body if self.body in ("sun", "moon") else ""

    @Property(float, notify=gazeChanged)
    def gazeX(self) -> float:
        return self._gaze[0]

    @Property(float, notify=gazeChanged)
    def gazeY(self) -> float:
        return self._gaze[1]

    @Slot(int, int)
    def watchFrom(self, x: int, y: int) -> None:
        """The orb tells us where it is on screen, so the light inside can lean towards the mouse."""
        self._centre = (x, y)
        self._watch(STATE_LOOKS[self._state] != "asleep")

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
