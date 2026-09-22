"""Loads the real QML with the real bridge (offscreen) and checks it reacts to state changes."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from app.config.settings import PROJECT_ROOT
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from ui.bridge import UiBridge
from ui.theme import STATE_COLORS, STATE_LABELS


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_theme_covers_every_state():
    assert set(STATE_COLORS) == set(S) == set(STATE_LABELS)


def test_orb_loads_without_qml_warnings_and_follows_state(app):
    core = Jarvis()
    bridge = UiBridge(core)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "qml" / "Orb.qml")))

    assert engine.rootObjects(), "Orb.qml failed to load"
    core.start()
    app.processEvents()
    assert bridge.state == "standby"

    core.pause()
    app.processEvents()
    assert bridge.stateLabel == "Paused"
    assert bridge.stateColor == STATE_COLORS[S.SLEEPING]

    core.resume()
    core.state.transition(S.ERROR, "test failure")
    app.processEvents()
    assert bridge.caption == "test failure"
    assert warnings == []


def test_tray_menu_actions_drive_core_and_window(app):
    from ui.tray import Tray

    core = Jarvis()
    bridge = UiBridge(core)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "qml" / "Orb.qml")))
    window = engine.rootObjects()[0]
    tray = Tray(bridge, window)
    core.start()
    app.processEvents()

    actions = {a.text(): a for a in tray.contextMenu().actions()}
    assert {"Hide JARVIS", "Pause JARVIS", "Exit"} <= set(actions)

    actions["Pause JARVIS"].trigger()
    app.processEvents()
    assert core.paused
    assert "Resume JARVIS" in [a.text() for a in tray.contextMenu().actions()]

    actions["Hide JARVIS"].trigger()
    app.processEvents()
    assert not window.isVisible()
    assert "Show JARVIS" in [a.text() for a in tray.contextMenu().actions()]

    bridge.requestMenu()  # right-click on the orb opens the same menu
    app.processEvents()
    assert tray.contextMenu().isVisible()
    tray.contextMenu().close()


def test_orb_shows_live_tool_steps(app):
    from app.core.events.events import ToolFinished, ToolStarted

    core = Jarvis()
    bridge = UiBridge(core)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "qml" / "Orb.qml")))
    window = engine.rootObjects()[0]
    core.start()
    base_height = window.height()

    core.bus.publish(ToolStarted(1, "Opening Notepad"))
    core.bus.publish(ToolFinished(1, "Opening Notepad", True))
    core.bus.publish(ToolStarted(2, "Typing hello"))
    app.processEvents()
    assert [(s["label"], s["status"]) for s in bridge.steps] == [("Opening Notepad", "done"), ("Typing hello", "running")]
    assert window.height() > base_height  # grew to fit the checklist
    assert warnings == []

    core.state.transition(S.WAKE_DETECTED)  # a new request clears the old steps
    app.processEvents()
    assert bridge.steps == []
