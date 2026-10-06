"""Render the desktop UI offscreen, with the real QML and the real bridge, to PNG files.

For checking the look without a Windows desktop: one picture of the orb window per state, and one of
each dashboard tab. The orb is drawn on a dark desktop-like backdrop so its glass edge is visible.

Usage:  python3 scripts/render_ui.py OUT_DIR [state ...]
        (no states = all of them). Needs PySide6. Uses Qt's software renderer, so what you see is
        what Qt draws, not what a particular GPU would do (animation speed in particular differs).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402
import shiboken6  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.events.events import (  # noqa: E402
    AssistantReply, AudioLevel, StateChanged, ToolFinished, ToolStarted, TranscriptReady,
)
from app.core.jarvis import Jarvis  # noqa: E402
from app.core.state.states import JarvisState  # noqa: E402
from ui.bridge import UiBridge  # noqa: E402


def pump(app: QApplication, ms: int) -> None:
    """Let animations run for `ms` milliseconds of wall time."""
    end = QTimer()
    end.setSingleShot(True)
    loop_done = []
    end.timeout.connect(lambda: loop_done.append(1))
    end.start(ms)
    while not loop_done:
        app.processEvents()


def snapshot(window, path: Path, backdrop: str | None = "#1a1714") -> None:
    # QML's root Window arrives as a plain QWindow; the same object, seen as the QQuickWindow it is, can be grabbed.
    quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    image = quick.grabWindow()
    if backdrop:
        canvas = QImage(image.size(), QImage.Format.Format_ARGB32)
        canvas.fill(QColor(backdrop))
        painter = QPainter(canvas)
        painter.drawImage(0, 0, image)
        painter.end()
        image = canvas
    image.save(str(path))


class FakeDashboard(QObject):
    """The same properties DashboardBridge gives the dashboard QML, filled with plausible data."""

    changed = Signal()
    savedMessage = Signal(str)

    @Property("QVariantMap", notify=changed)
    def status(self):
        return {"state": "Ready", "color": "#E8BE76", "uptime": "42m", "requests": 14, "actions": 31, "facts": 52,
                "todos": 3, "reminders": ["Tue 9:30 AM — stand-up with Arjun", "Wed 6:00 PM — pay the electricity bill"],
                "meetings": ["10:00  Quarterly review", "14:30  Vendor call"],
                "services": [{"name": "AI brain (gemini)", "ok": True}, {"name": "Google Calendar & Gmail", "ok": True},
                             {"name": "Microphone", "ok": True}, {"name": "Wake word (openwakeword)", "ok": False}],
                "cpu": "2%", "ram": "612 MB"}

    @Property("QVariantList", notify=changed)
    def activity(self):
        return [{"time": "09:41", "icon": "🎙", "text": "“email the Q3 attrition report to Arjun”"},
                {"time": "09:41", "icon": "⚙", "text": "Found Q3_Attrition_Report.xlsx"},
                {"time": "09:42", "icon": "✓", "text": "Sent it to Arjun Rao. He has it."},
                {"time": "09:50", "icon": "⏰", "text": "Reminder: stand-up in 10 minutes"}]

    @Property("QVariantList", notify=changed)
    def settingsList(self):
        return [{"key": "USER_NAME", "label": "Your name", "hint": "How it addresses you", "value": "Likki"},
                {"key": "HOME_CITY", "label": "Home city", "hint": "Used for the morning weather", "value": "Hyderabad"},
                {"key": "TTS_SPEED", "label": "Voice speed", "hint": "1.0 is normal", "value": "1.0"}]

    @Slot()
    def refresh(self): ...

    @Slot(str)
    def ask(self, text): ...

    @Slot("QVariantMap")
    def save(self, edits): ...

    @Slot()
    def restart(self): ...

    @Slot()
    def openLogs(self): ...


def main() -> None:
    out = Path(sys.argv[1])
    wanted = sys.argv[2:]
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    core = Jarvis()
    bridge = UiBridge(core, "VEM")
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(ROOT / "ui" / "qml" / "Orb.qml")))
    window = engine.rootObjects()[0]
    core.start()
    pump(app, 400)

    states = [s for s in JarvisState if not wanted or s.value in wanted or "all" in wanted]
    previous = core.state.current
    for state in states:
        # Publish the change directly: the real state machine only allows some moves, and a picture
        # of every state is the point here.
        reason = "Couldn't open the Q3 report: the file was moved" if state is JarvisState.ERROR else None
        core._paused = state is JarvisState.SLEEPING  # only for the picture; Jarvis.pause() would also wake things
        core.bus.publish(StateChanged(previous, state, reason))
        previous = state
        if state is JarvisState.LISTENING:
            core.bus.publish(TranscriptReady("email the Q3 report to Arjun"))
            core.bus.publish(AudioLevel(0.6))
        if state is JarvisState.RESPONDING:
            core.bus.publish(AssistantReply("Done! It's sent. Arjun has it."))
        if state is JarvisState.EXECUTING:
            core.bus.publish(ToolStarted(1, "Find Q3_Attrition_Report.xlsx"))
            core.bus.publish(ToolFinished(1, "Find Q3_Attrition_Report.xlsx", True))
            core.bus.publish(ToolStarted(2, "Email it to Arjun Rao"))
        pump(app, 1300)
        snapshot(window, out / f"orb-{state.value}.png")
        print("wrote", out / f"orb-{state.value}.png")

    if "dashboard" in wanted or "all" in wanted:
        engine2 = QQmlApplicationEngine()
        stub = FakeDashboard()
        engine2.rootContext().setContextProperty("bridge", bridge)
        engine2.rootContext().setContextProperty("dashboard", stub)
        engine2.load(QUrl.fromLocalFile(str(ROOT / "ui" / "qml" / "Dashboard.qml")))
        dash = engine2.rootObjects()[0]
        dash.setProperty("visible", True)
        for tab, name in enumerate(["overview", "activity", "settings"]):
            dash.setProperty("tab", tab)
            pump(app, 700)
            snapshot(dash, out / f"dashboard-{name}.png", backdrop=None)
            print("wrote", out / f"dashboard-{name}.png")
        dash.hide()
    window.hide()


if __name__ == "__main__":
    main()
