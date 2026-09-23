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
from ui.bridge import UiBridge, gaze_direction
from ui.theme import STATE_COLORS, STATE_FACES, STATE_LABELS


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_theme_covers_every_state():
    assert set(STATE_COLORS) == set(S) == set(STATE_LABELS) == set(STATE_FACES)


def test_every_expression_renders(app):
    """Face.qml must have a mood for each name the theme uses, and render it without warnings."""
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "qml" / "Face.qml")))
    face = component.create()
    assert face is not None, component.errorString()

    for expression in set(STATE_FACES.values()):
        face.setProperty("expression", expression)
        app.processEvents()
        assert face.property("mood") is not None, f"Face.qml has no mood for {expression!r}"
    assert warnings == []


@pytest.mark.parametrize("cursor, expected", [
    ((500, 500), (0.0, 0.0)),            # the mouse is on the face
    ((1020, 500), (1.0, 0.0)),           # far right — eyes fully across
    ((500, -20), (0.0, -1.0)),           # 520 px above — the limit of the travel
    ((760, 500), (0.5, 0.0)),            # half way to the limit
])
def test_eyes_look_towards_the_mouse(cursor, expected):
    x, y = gaze_direction(cursor, (500, 500), reach=520.0)
    assert (round(x, 3), round(y, 3)) == expected


def test_eyes_stop_following_the_mouse_while_resting(app):
    core = Jarvis()
    bridge = UiBridge(core)
    bridge.watchFrom(500, 500)
    assert bridge._eyes.isActive()

    core.start()
    core.state.transition(S.RESTING)
    app.processEvents()
    assert bridge.expression == "asleep"
    assert not bridge._eyes.isActive()  # closed eyes don't need the 20 Hz timer


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


def test_dashboard_loads_without_qml_warnings(app, tmp_path):
    from app.config.settings import Settings
    from app.core.events.events import TranscriptReady
    from app.memory.store import MemoryStore
    from ui.activity import ActivityLog
    from ui.dashboard import DashboardBridge

    core = Jarvis()
    settings = Settings(_env_file=None)
    settings.model_config["env_file"] = tmp_path / ".env"
    memory = MemoryStore(tmp_path / "memory.db")
    memory.add_todo("finish the BERT model")
    bridge = DashboardBridge(core, memory, ActivityLog(core.bus), settings, lambda: ["Standup at 10:00"], lambda: True)
    core.start()
    core.bus.publish(TranscriptReady("open notepad"))

    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.rootContext().setContextProperty("dashboard", bridge)
    engine.rootContext().setContextProperty("bridge", UiBridge(core))
    engine.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "qml" / "Dashboard.qml")))
    app.processEvents()

    assert engine.rootObjects(), "Dashboard.qml failed to load"
    window = engine.rootObjects()[0]
    window.show()  # rendering offscreen surfaces binding errors too
    app.processEvents()
    window.hide()
    assert warnings == []
