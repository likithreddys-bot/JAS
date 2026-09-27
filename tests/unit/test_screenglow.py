"""The screen glow follows the screen tools, and never appears in the photograph."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.config.settings import PROJECT_ROOT
from app.core.events.events import ToolFinished, ToolStarted
from app.core.jarvis import Jarvis
from ui.screenglow import ScreenGlow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# Each ScreenGlow owns a QML engine. Letting Python collect one while Qt still holds its window
# crashes the next test that builds an engine, so they are kept alive for the whole session.
_KEEP: list = []


@pytest.fixture
def glow(app):
    core = Jarvis()
    overlay = ScreenGlow(core, PROJECT_ROOT / "ui" / "qml" / "ScreenGlow.qml")
    _KEEP.append((core, overlay))
    yield core, overlay, app
    overlay._active.clear()
    overlay._hidden_for_capture = False
    overlay._apply()


def watching(overlay) -> bool:
    return bool(overlay._window.property("watching"))


def test_the_glow_only_follows_tools_that_look_at_the_screen(glow):
    core, overlay, app = glow

    core.bus.publish(ToolStarted(1, "Opening Notepad", "open_application"))
    app.processEvents()
    assert not watching(overlay)

    core.bus.publish(ToolStarted(2, "Looking at your screen", "look_at_screen"))
    app.processEvents()
    assert watching(overlay)

    core.bus.publish(ToolFinished(2, "Looking at your screen", True, "", "look_at_screen"))
    app.processEvents()
    assert not watching(overlay)


def test_the_glow_stays_while_any_screen_tool_is_still_running(glow):
    core, overlay, app = glow

    core.bus.publish(ToolStarted(1, "Looking", "look_at_screen"))
    core.bus.publish(ToolStarted(2, "Clicking", "click_on_screen"))
    app.processEvents()
    assert watching(overlay)

    core.bus.publish(ToolFinished(1, "Looking", True, "", "look_at_screen"))
    app.processEvents()
    assert watching(overlay), "one tool finished but the other is still looking"

    core.bus.publish(ToolFinished(2, "Clicking", True, "", "click_on_screen"))
    app.processEvents()
    assert not watching(overlay)


def test_the_glow_is_not_in_the_photograph(glow):
    """JARVIS must not photograph its own glow; it goes away for the shot and comes back."""
    core, overlay, app = glow

    core.bus.publish(ToolStarted(1, "Looking", "look_at_screen"))
    app.processEvents()
    assert watching(overlay)

    overlay.hide_for_capture(True)
    app.processEvents()
    assert not watching(overlay) and not overlay._window.isVisible()

    overlay.hide_for_capture(False)
    app.processEvents()
    assert watching(overlay)
