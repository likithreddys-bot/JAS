import pytest

from app.tools.base import Risk
from app.tools.screen import RISKY_TARGET, screen_tools, to_cursor_position


@pytest.mark.parametrize("point, region, monitor, cursor, expected", [
    ((500, 500), (0, 0, 1920, 1080), (0, 0, 1920, 1080), (1920, 1080), (960, 540)),  # whole screen, no scaling
    ((0, 0), (0, 0, 1920, 1080), (0, 0, 1920, 1080), (1920, 1080), (0, 0)),
    ((1000, 1000), (0, 0, 1920, 1080), (0, 0, 1920, 1080), (1920, 1080), (1920, 1080)),
    ((250, 750), (0, 0, 1600, 1000), (0, 0, 1600, 1000), (1280, 800), (960, 200)),  # 125% display scaling
    ((500, 500), (600, 200, 400, 600), (0, 0, 1920, 1080), (1920, 1080), (800, 500)),  # inside a window
])
def test_model_coordinates_become_mouse_positions(point, region, monitor, cursor, expected):
    assert to_cursor_position(point, region, monitor, cursor) == expected


@pytest.mark.parametrize("target, risky", [
    ("the blue Send button", True), ("Delete this file", True), ("Pay now", True), ("Sign out", True),
    ("the search box", False), ("the first result", False), ("the X in the top right", False),
])
def test_risky_targets_need_confirmation(target, risky):
    assert bool(RISKY_TARGET.search(target)) is risky


class FakeVision:
    def __init__(self, result):
        self.result = result
        self.asked = []

    def locate(self, image, target):
        self.asked.append(target)
        return self.result


@pytest.fixture
def clicking(monkeypatch):
    """screen tools with the screen, mouse and windows faked out."""
    import app.tools.screen as screen

    clicks = []
    monkeypatch.setattr(screen, "capture_screen_jpeg", lambda region=None: b"fake-jpeg")
    monkeypatch.setattr(screen, "screen_size", lambda: (0, 0, 1920, 1080))
    monkeypatch.setattr(screen.pyautogui, "size", lambda: (1920, 1080))
    monkeypatch.setattr(screen.pyautogui, "moveTo", lambda x, y, duration=0: clicks.append(("move", x, y)))
    monkeypatch.setattr(screen.pyautogui, "click", lambda: clicks.append(("click",)))
    monkeypatch.setattr(screen.pyautogui, "doubleClick", lambda: clicks.append(("double",)))
    monkeypatch.setattr(screen.pyautogui, "rightClick", lambda: clicks.append(("right",)))
    monkeypatch.setattr(screen.windows, "foreground_window", lambda: None)
    return clicks


def test_clicking_looks_inside_the_active_window(clicking, monkeypatch):
    """The active window is photographed, so buttons are bigger and coordinates are relative to it."""
    import app.tools.screen as screen

    window = screen.windows.Window(1, "Calculator", "calc")
    monkeypatch.setattr(screen.windows, "foreground_window", lambda: window)
    monkeypatch.setattr(screen.windows, "rect", lambda w: (600, 200, 400, 600))
    vision = FakeVision({"found": True, "point": (500, 500), "label": "the 7 button"})
    tools = {t.name: t for t in screen_tools(lambda img, q: "", vision.locate)}
    result = tools["click_on_screen"].run(target="the 7 button")
    assert result.data["in"] == "the Calculator window"
    assert result.data["position"] == {"x": 800, "y": 500}  # centre of the window, not of the screen
    assert clicking == [("move", 800, 500), ("click",)]

    tools["click_on_screen"].run(target="the taskbar clock", whole_screen=True)
    assert clicking[-2] == ("move", 960, 540)  # whole screen: centre of the monitor


def test_nothing_is_clicked_when_another_window_jumps_in_front(clicking, monkeypatch):
    """Vision takes seconds; clicking a stale position would hit whatever is in front now."""
    import app.tools.screen as screen

    calculator = screen.windows.Window(1, "Calculator", "calc")
    code = screen.windows.Window(2, "Visual Studio Code", "code")
    seen = [calculator, code]  # foreground when we look, then after vision answered
    monkeypatch.setattr(screen.windows, "foreground_window", lambda: seen.pop(0) if seen else code)
    monkeypatch.setattr(screen.windows, "rect", lambda w: (600, 200, 400, 600))
    vision = FakeVision({"found": True, "point": (500, 500), "label": "the 7 button"})
    tools = {t.name: t for t in screen_tools(lambda img, q: "", vision.locate)}
    result = tools["click_on_screen"].run(target="the 7 button")
    assert not result.ok and "Visual Studio Code came to the front" in result.error
    assert clicking == []


def test_clicking_moves_the_mouse_to_what_vision_found(clicking):
    vision = FakeVision({"found": True, "point": (250, 500), "label": "the blue Send button, top right"})
    tools = {t.name: t for t in screen_tools(lambda img, q: "", vision.locate)}
    result = tools["click_on_screen"].run(target="the Send button")
    assert result.ok and result.data["clicked"].startswith("the blue Send button")
    assert result.data["position"] == {"x": 960, "y": 270}
    assert clicking == [("move", 960, 270), ("click",)]
    assert vision.asked == ["the Send button"]


def test_double_and_right_click(clicking):
    vision = FakeVision({"found": True, "point": (100, 100), "label": "the file icon"})
    tools = {t.name: t for t in screen_tools(lambda img, q: "", vision.locate)}
    tools["click_on_screen"].run(target="the file icon", double=True)
    tools["click_on_screen"].run(target="the file icon", right_click=True)
    assert [c[0] for c in clicking] == ["move", "double", "move", "right"]


def test_nothing_is_clicked_when_vision_cannot_see_it(clicking):
    vision = FakeVision({"found": False, "point": (0, 0), "label": "no Send button is visible"})
    tools = {t.name: t for t in screen_tools(lambda img, q: "", vision.locate)}
    result = tools["click_on_screen"].run(target="the Send button")
    assert not result.ok and "no Send button is visible" in result.error
    assert clicking == []


def test_find_on_screen_reports_without_clicking(clicking):
    vision = FakeVision({"found": True, "point": (500, 500), "label": "the search box in the middle"})
    tools = {t.name: t for t in screen_tools(lambda img, q: "", vision.locate)}
    result = tools["find_on_screen"].run(target="the search box")
    assert result.ok and result.data["position"] == {"x": 960, "y": 540}
    assert clicking == []


def test_click_risk_levels(clicking):
    tools = {t.name: t for t in screen_tools(lambda img, q: "", FakeVision({}).locate)}
    click = tools["click_on_screen"]
    assert click.risk_for({"target": "the Send button"}) is Risk.MEDIUM
    assert click.risk_for({"target": "the search box"}) is Risk.LOW
    assert click.confirm_question(target="the Send button") == "Should I click the Send button?"


def test_orb_is_hidden_while_the_screen_is_captured(clicking, monkeypatch):
    import contextlib

    import app.tools.screen as screen

    events = []

    @contextlib.contextmanager
    def hide_ui():
        events.append("hidden")
        yield
        events.append("shown")

    monkeypatch.setattr(screen, "capture_screen_jpeg", lambda region=None: events.append("captured") or b"jpeg")
    tools = {t.name: t for t in screen_tools(
        lambda img, q: "", lambda img, target: {"found": True, "point": (10, 10), "label": "x"}, hide_ui)}
    tools["click_on_screen"].run(target="x")
    # the orb is hidden only for the screenshot itself, not for the (slow) vision call
    assert events == ["hidden", "captured", "shown"]
