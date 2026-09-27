"""The glow around the screen while JARVIS is looking at it.

Privacy rule from JARVIS.md: the screen is only ever captured on request, and the user must be able
to see when it happens. This is that signal — a soft border around the whole screen, like the one a
video call shows while you are sharing.
"""
from __future__ import annotations

import ctypes
import logging

from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl, Slot
from PySide6.QtQml import QQmlApplicationEngine

from app.core.events.events import ToolFinished, ToolStarted
from app.core.jarvis import Jarvis

log = logging.getLogger("jarvis.ui")

# The tools that photograph the screen. Anything else leaves the glow alone.
SCREEN_TOOLS = frozenset({"look_at_screen", "click_on_screen", "find_on_screen", "take_screenshot"})

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000


class ScreenGlow(QObject):
    """Owns the overlay window and follows tool events. Lives on the UI thread."""

    def __init__(self, core: Jarvis, qml_path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = QQmlApplicationEngine()
        self._engine.load(QUrl.fromLocalFile(str(qml_path)))
        roots = self._engine.rootObjects()
        if not roots:
            raise RuntimeError(f"{qml_path} failed to load")
        self._window = roots[0]
        self._active: set[int] = set()
        self._hidden_for_capture = False
        core.bus.subscribe(ToolStarted, lambda e: self._on_tool(e.tool, e.step_id, True))
        core.bus.subscribe(ToolFinished, lambda e: self._on_tool(e.tool, e.step_id, False))

    def _on_tool(self, tool: str, step_id: int, started: bool) -> None:
        if tool not in SCREEN_TOOLS:
            return
        (self._active.add if started else self._active.discard)(step_id)
        self._apply_queued()

    def _apply_queued(self) -> None:
        # Tool events arrive on the agent thread; windows may only be touched on the UI thread.
        QMetaObject.invokeMethod(self, "_apply", Qt.QueuedConnection)

    @Slot()
    def _apply(self) -> None:
        watching = bool(self._active) and not self._hidden_for_capture
        if watching and not self._window.isVisible():
            self._cover_the_screen()
            self._window.show()
            _make_click_through(int(self._window.winId()))
        self._window.setProperty("watching", watching)
        if not watching and self._window.isVisible():
            self._window.hide()

    def _cover_the_screen(self) -> None:
        screen = self._window.screen()
        if screen is not None:
            area = screen.geometry()
            self._window.setGeometry(area.x(), area.y(), area.width(), area.height())

    def hide_for_capture(self, hidden: bool) -> None:
        """The glow must not appear in the photograph JARVIS is about to take."""
        self._hidden_for_capture = hidden
        self._apply_queued()


def _make_click_through(hwnd: int) -> None:
    """Mouse clicks pass straight through the overlay to whatever is underneath."""
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetWindowLongW.restype = ctypes.c_long
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE)
    except Exception:
        log.exception("Could not make the screen glow click-through")
