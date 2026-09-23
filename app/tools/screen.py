"""Screen understanding and vision-guided mouse: look at the screen, find things, click them.

The screen is captured only when the user asks (the orb shows "Looking at your screen" and
hides itself for the shot). Clicks on risky-looking buttons ask the user first.
"""
from __future__ import annotations

import contextlib
import io
import logging
import re
import time
from typing import Callable

import mss
import pyautogui
from PIL import Image

from app.tools.base import Risk, Tool, ToolResult
from app.tools.computer import windows

log = logging.getLogger("jarvis.agent")

MAX_WIDTH = 1600  # enough to read text, small enough to upload quickly
RISKY_TARGET = re.compile(
    r"\b(buy|pay|purchase|order|checkout|delete|remove|send|submit|post|publish|confirm|transfer|"
    r"subscribe|unsubscribe|sign ?out|log ?out|book|reserve|install|uninstall|format|shut ?down)\b", re.I)
pyautogui.FAILSAFE = False  # JARVIS moves the mouse deliberately; the corner is not an abort signal


def screen_size() -> tuple[int, int, int, int]:
    """Primary monitor as (left, top, width, height) in the pixels mss captures."""
    with mss.mss() as screen:
        monitor = screen.monitors[1]
    return monitor["left"], monitor["top"], monitor["width"], monitor["height"]


def capture_screen_jpeg(region: tuple[int, int, int, int] | None = None) -> bytes:
    """JPEG of the primary monitor, or of `region` (left, top, width, height)."""
    with mss.mss() as screen:
        area = screen.monitors[1]
        if region:
            left, top, width, height = region
            area = {"left": max(left, area["left"]), "top": max(top, area["top"]),
                    "width": min(width, area["width"]), "height": min(height, area["height"])}
        shot = screen.grab(area)
    image = Image.frombytes("RGB", shot.size, shot.rgb)
    if image.width > MAX_WIDTH:
        image = image.resize((MAX_WIDTH, round(image.height * MAX_WIDTH / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def to_cursor_position(point: tuple[int, int], region: tuple[int, int, int, int],
                       monitor: tuple[int, int, int, int], cursor_size: tuple[int, int]) -> tuple[int, int]:
    """Model coordinates (y, x in 0-1000) inside `region` -> mouse position, allowing for display scaling."""
    y, x = point
    left, top, width, height = region
    scale_x, scale_y = cursor_size[0] / monitor[2], cursor_size[1] / monitor[3]
    return (round((left + x / 1000 * width) * scale_x), round((top + y / 1000 * height) * scale_y))


def screen_tools(
    ask_vision: Callable[[bytes, str], str],
    locate: Callable[[bytes, str], dict],
    hide_ui: Callable[[], contextlib.AbstractContextManager] | None = None,
) -> list[Tool]:
    def _capture(region: tuple[int, int, int, int] | None = None) -> bytes:
        with (hide_ui() if hide_ui else contextlib.nullcontext()):
            return capture_screen_jpeg(region)

    def _region(whole_screen: bool) -> tuple[tuple[int, int, int, int], str, windows.Window | None]:
        """Where to look: the active window (sharper, buttons are bigger) or the whole screen."""
        monitor = screen_size()
        if whole_screen:
            return monitor, "the screen", None
        window = windows.foreground_window()
        box = windows.rect(window) if window else None
        if not box or box[2] < 200 or box[3] < 150:
            return monitor, "the screen", None
        return box, f"the {window.title} window", window

    def look_at_screen(question: str = "What is on the screen?") -> ToolResult:
        try:
            answer = ask_vision(_capture(), question)
        except Exception as exc:
            return ToolResult(False, error=str(exc))
        return ToolResult(True, {"screen": answer})

    def _find(target: str, whole_screen: bool = False
              ) -> tuple[dict, tuple[int, int], str, windows.Window | None] | ToolResult:
        region, where, window = _region(whole_screen)
        try:
            found = locate(_capture(region), target)
        except Exception as exc:
            return ToolResult(False, error=str(exc))
        if not found["found"]:
            return ToolResult(False, error=f"I can't see {target!r} in {where}: {found['label']}")
        return found, to_cursor_position(found["point"], region, screen_size(), pyautogui.size()), where, window

    def find_on_screen(target: str, whole_screen: bool = False) -> ToolResult:
        result = _find(target, whole_screen)
        if isinstance(result, ToolResult):
            return result
        found, (x, y), where, _ = result
        return ToolResult(True, {"found": found["label"], "in": where, "position": {"x": x, "y": y}})

    def click_on_screen(target: str, double: bool = False, right_click: bool = False,
                        whole_screen: bool = False) -> ToolResult:
        result = _find(target, whole_screen)
        if isinstance(result, ToolResult):
            return result
        found, (x, y), where, looked_at = result
        before = windows.foreground_window()
        # Vision takes seconds; if another window jumped in front meanwhile, the position is stale.
        if looked_at and (not before or before.hwnd != looked_at.hwnd):
            return ToolResult(False, error=f"{before.title if before else 'Another window'} came to the front while "
                                          f"I was looking at {where}, so I didn't click. Ask me again.")
        log.info("Clicking %r at (%d, %d): %s", target, x, y, found["label"])
        pyautogui.moveTo(x, y, duration=0.25)
        time.sleep(0.1)
        (pyautogui.rightClick if right_click else pyautogui.doubleClick if double else pyautogui.click)()
        time.sleep(0.6)
        after = windows.foreground_window()
        return ToolResult(True, {
            "clicked": found["label"],
            "in": where,
            "position": {"x": x, "y": y},
            "active_window": after.title if after else None,
            "window_changed": bool(before and after and before.hwnd != after.hwnd),
        })

    def scroll_screen(direction: str = "down", amount: int = 3) -> ToolResult:
        window = windows.foreground_window()
        pyautogui.scroll((120 if direction == "up" else -120) * max(1, min(amount, 10)))
        time.sleep(0.3)
        return ToolResult(True, {"scrolled": direction, "in_window": window.title if window else None})

    def click_risk(target: str, double: bool = False, right_click: bool = False, whole_screen: bool = False) -> Risk:
        return Risk.MEDIUM if RISKY_TARGET.search(target) else Risk.LOW

    target_param = {"type": "string", "description": "What to click, in plain words: 'the blue Send button', "
                                                     "'the search box', 'the X in the top right'"}
    return [
        Tool("look_at_screen",
             "Look at the user's screen right now and answer a question about it: what's open, read text, "
             "explain an error, describe an image. Call it again for follow-up questions about the screen.",
             {"type": "object", "properties": {"question": {"type": "string", "description": "What the user wants to know"}}},
             look_at_screen, lambda question="": "\U0001f441 Looking at your screen"),
        Tool("click_on_screen",
             "Click something you can see on the screen, in any app or web page: buttons, links, fields, menu items. "
             "Describe it as a person would. Use this when there's no better tool (apps and the user's own Chrome).",
             {"type": "object", "properties": {
                 "target": target_param, "double": {"type": "boolean"}, "right_click": {"type": "boolean"},
                 "whole_screen": {"type": "boolean", "description": "true for the taskbar, desktop or another window; "
                                                                    "by default JARVIS looks in the active window"}},
              "required": ["target"]},
             click_on_screen, lambda target, double=False, right_click=False, whole_screen=False: f"Clicking {target}",
             risk=click_risk,
             confirm_question=lambda target, double=False, right_click=False, whole_screen=False:
                 f"Should I click {target}?"),
        Tool("find_on_screen", "Check whether something is visible (without clicking it).",
             {"type": "object", "properties": {"target": target_param, "whole_screen": {"type": "boolean"}},
              "required": ["target"]},
             find_on_screen, lambda target, whole_screen=False: f"Looking for {target}"),
        Tool("scroll_screen", "Scroll the window under the mouse up or down.",
             {"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down"]},
                                               "amount": {"type": "integer", "description": "1-10, default 3"}}},
             scroll_screen, lambda direction="down", amount=3: f"Scrolling {direction}"),
    ]
