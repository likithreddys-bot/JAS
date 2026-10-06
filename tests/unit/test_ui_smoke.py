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
from ui.theme import STATE_BODY, STATE_COLORS, STATE_LABELS, STATE_LOOKS


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_theme_covers_every_state():
    assert set(STATE_COLORS) == set(S) == set(STATE_LABELS) == set(STATE_LOOKS)


def test_no_state_is_blue():
    """VEM's palette has no blue: for every state colour, blue is not the strongest channel."""
    for state, colour in STATE_COLORS.items():
        r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        assert b < max(r, g), f"{state.value} is bluish: {colour}"


def test_every_look_renders(app):
    """GlassOrb.qml must have a look for each name the theme uses, and render it without warnings."""
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "qml" / "GlassOrb.qml")))
    orb = component.create()
    assert orb is not None, component.errorString()

    for look in set(STATE_LOOKS.values()):
        orb.setProperty("look", look)
        app.processEvents()
        entry = orb.property("looks").property(look)  # the table entry itself, not the calm fallback
        assert entry.isObject() and entry.property("glow").toNumber() > 0, f"GlassOrb.qml has no look for {look!r}"
        assert orb.property("current").property("glow").toNumber() == entry.property("glow").toNumber()
    assert warnings == []


@pytest.mark.parametrize("cursor, expected", [
    ((500, 500), (0.0, 0.0)),            # the mouse is on the face
    ((1020, 500), (1.0, 0.0)),           # far right — eyes fully across
    ((500, -20), (0.0, -1.0)),           # 520 px above — the limit of the travel
    ((760, 500), (0.5, 0.0)),            # half way to the limit
])
def test_the_light_leans_towards_the_mouse(cursor, expected):
    x, y = gaze_direction(cursor, (500, 500), reach=520.0)
    assert (round(x, 3), round(y, 3)) == expected


def test_the_light_stops_following_the_mouse_while_resting(app):
    core = Jarvis()
    bridge = UiBridge(core)
    bridge.watchFrom(500, 500)
    assert bridge._gaze_timer.isActive()

    core.start()
    core.state.transition(S.RESTING)
    app.processEvents()
    assert bridge.look == "asleep"
    assert not bridge._gaze_timer.isActive()  # a paused orb doesn't need the 20 Hz timer


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
    assert {"Hide VEM", "Pause VEM", "Exit"} <= set(actions)

    actions["Pause VEM"].trigger()
    app.processEvents()
    assert core.paused
    assert "Resume VEM" in [a.text() for a in tray.contextMenu().actions()]

    actions["Hide VEM"].trigger()
    app.processEvents()
    assert not window.isVisible()
    assert "Show VEM" in [a.text() for a in tray.contextMenu().actions()]

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
    orb_bridge = UiBridge(core)  # keep a reference: QML reads it while the window builds
    engine.rootContext().setContextProperty("bridge", orb_bridge)
    engine.load(QUrl.fromLocalFile(str(PROJECT_ROOT / "ui" / "qml" / "Dashboard.qml")))
    app.processEvents()

    assert engine.rootObjects(), "Dashboard.qml failed to load"
    window = engine.rootObjects()[0]
    window.show()  # rendering offscreen surfaces binding errors too
    app.processEvents()
    window.hide()
    assert warnings == []


def test_sun_while_ready_and_moon_while_asleep(app):
    """The orb is a sun when JARVIS is ready and a moon when it sleeps; everything else is neither."""
    core = Jarvis()
    bridge = UiBridge(core)
    core.start()
    app.processEvents()
    assert bridge.sky == "sun"

    core.pause()
    app.processEvents()
    assert bridge.sky == "moon"

    core.resume()
    core.state.transition(S.RESTING)
    app.processEvents()
    assert bridge.sky == "moon"

    core.state.transition(S.WAKE_DETECTED)
    core.state.transition(S.LISTENING)
    app.processEvents()
    assert bridge.sky == "", "listening is neither sun nor moon"

    assert set(STATE_BODY) == set(S), "every state needs a body in the sky"
    assert bridge.body == "earth", "listening is Earth"


def test_no_blue_anywhere_in_the_desktop_phone_and_android_sources():
    """VEM is black and gold. No hex colour in the UI sources may have blue as its strongest channel.

    QML and Android write 8-digit colours as ARGB, so the alpha pair comes first and is skipped.
    """
    import re

    roots = [PROJECT_ROOT / "ui", PROJECT_ROOT / "android" / "app" / "src" / "main"]
    suffixes = {".qml", ".py", ".html", ".js", ".kt", ".xml"}
    offenders = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in suffixes or "__pycache__" in path.parts:
                continue
            for match in re.finditer(r"#([0-9A-Fa-f]{8}|[0-9A-Fa-f]{6})\b", path.read_text(encoding="utf-8")):
                digits = match.group(1)[-6:]
                r, g, b = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
                if b > max(r, g):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: #{match.group(1)}")
    assert offenders == []
