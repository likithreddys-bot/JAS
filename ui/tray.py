"""System tray icon. Its colour mirrors the current state, so status is visible even when the orb is hidden."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPen, QPixmap, QRadialGradient, QWindow
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ui.bridge import UiBridge


def orb_icon(color: str, size: int = 64) -> QIcon:
    """The orb in miniature: smoked glass with the state's light inside it and a bright rim."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    base = QColor(color)
    disc = QRectF(size * 0.07, size * 0.07, size * 0.86, size * 0.86)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#17130F"))  # the glass
    painter.drawEllipse(disc)
    light = QRadialGradient(size * 0.48, size * 0.56, size * 0.42)  # the light inside, low and centred
    light.setColorAt(0.0, base.lighter(135))
    light.setColorAt(0.55, base)
    light.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
    painter.setBrush(light)
    painter.drawEllipse(disc)
    rim = QColor(base.lighter(150))
    rim.setAlpha(230)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(rim, max(1.5, size * 0.06)))  # light caught at the edge, so it reads at 16 px
    painter.drawEllipse(disc)
    painter.end()
    return QIcon(pixmap)


class Tray(QSystemTrayIcon):
    def __init__(self, bridge: UiBridge, window: QWindow, dashboard: QWindow | None = None) -> None:
        super().__init__()
        self._bridge = bridge
        self._window = window
        self._dashboard = dashboard
        self._name = bridge.assistantName

        menu = QMenu()
        title = menu.addAction(self._name)
        title.setEnabled(False)
        menu.addSeparator()
        self._show_action = QAction(menu)
        self._show_action.triggered.connect(self._toggle_window)
        self._pause_action = QAction(menu)
        self._pause_action.triggered.connect(bridge.togglePause)
        menu.addAction(self._show_action)
        menu.addAction(self._pause_action)
        if dashboard is not None:
            menu.addAction("Dashboard", self._show_dashboard)
        menu.addSeparator()
        menu.addAction("Exit", QApplication.quit)
        self._menu = menu  # keep a reference; the tray does not own the menu
        self.setContextMenu(menu)

        self._hide_hint_shown = False
        self.activated.connect(self._on_activated)
        bridge.menuRequested.connect(lambda: menu.popup(QCursor.pos()))
        window.visibleChanged.connect(self._refresh)
        bridge.stateChanged.connect(self._refresh)
        bridge.stateChanged.connect(self._on_state)
        self._refresh()

    def _refresh(self) -> None:
        self.setIcon(orb_icon(self._bridge.stateColor))
        self.setToolTip(f"{self._name} — {self._bridge.stateLabel}")
        self._show_action.setText(f"Hide {self._name}" if self._window.isVisible() else f"Show {self._name}")
        self._pause_action.setText(f"Resume {self._name}" if self._bridge.paused else f"Pause {self._name}")

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
            if not self._hide_hint_shown:
                # Windows 11 tucks new tray icons behind the ^ overflow, so say where it went.
                self.showMessage(
                    f"{self._name} is still running",
                    f"Click the {self._name} icon near the clock (under ^), or start it again, to show it.",
                    orb_icon(self._bridge.stateColor),
                    5000,
                )
                self._hide_hint_shown = True
        else:
            self.show_window()

    def _show_dashboard(self) -> None:
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.requestActivate()

    def show_window(self) -> None:
        # No activation: the orb must not steal keyboard focus from the user's app.
        self._window.show()
        self._window.raise_()

    def _on_state(self) -> None:
        if self._bridge.state == "wake_detected" and not self._window.isVisible():
            self.show_window()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason is QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()
