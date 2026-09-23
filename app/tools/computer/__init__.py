"""Computer-control tools: apps, windows, keyboard, screenshots.

Every tool verifies its effect and reports honestly; mouse control is intentionally
absent until JARVIS can see the screen (Phase 10).
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import mss
import mss.tools

from app.tools.base import Risk, Tool, ToolResult
from app.tools.computer import apps, keyboard, session, windows

SCREENSHOT_DIR = Path.home() / "Pictures" / "JARVIS"


def computer_tools(app_index: apps.AppIndex) -> list[Tool]:
    def open_application(name: str) -> ToolResult:
        app = app_index.find(name)
        if app is None:
            return ToolResult(False, error=f"No installed app matches {name!r}.")
        window = apps.launch(app)
        if window is None:
            return ToolResult(False, error=f"Started {app.name}, but no window appeared within 15 seconds.")
        return ToolResult(True, {"app": app.name, "window": window.title})

    def list_open_windows() -> ToolResult:
        front = windows.foreground_window()
        items = [{"title": w.title, "app": w.process} for w in windows.list_windows()[:20]]
        return ToolResult(True, {"windows": items, "active": front.title if front else None})

    def focus_window(name: str) -> ToolResult:
        window = windows.find_window(name)
        if window is None:
            return ToolResult(False, error=f"No open window matches {name!r}.")
        if not windows.focus(window):
            return ToolResult(False, error=f"Windows didn't let me bring {window.title!r} to the front.")
        return ToolResult(True, {"window": window.title})

    def window_action(name: str, action: str) -> ToolResult:
        window = windows.find_window(name)
        if window is None:
            return ToolResult(False, error=f"No open window matches {name!r}.")
        if action == "minimize":
            windows.show(window, windows.SW_MINIMIZE)
            ok = _wait(lambda: windows.is_minimized(window))
        elif action == "maximize":
            windows.show(window, windows.SW_MAXIMIZE)
            ok = _wait(lambda: windows.is_maximized(window))
        else:
            windows.show(window, windows.SW_RESTORE)
            ok = _wait(lambda: not windows.is_minimized(window) and not windows.is_maximized(window))
        if not ok:
            return ToolResult(False, error=f"Tried to {action} {window.title!r} but it didn't change.")
        return ToolResult(True, {"window": window.title, "action": action})

    def close_window(name: str) -> ToolResult:
        window = windows.find_window(name)
        if window is None:
            return ToolResult(False, error=f"No open window matches {name!r}.")
        if not windows.request_close(window):
            return ToolResult(False, error=f"{window.title!r} is still open. It may be asking to save changes.")
        return ToolResult(True, {"closed": window.title})

    def type_text(text: str) -> ToolResult:
        target = windows.foreground_window()
        if target is None:
            return ToolResult(False, error="No window is active to type into.")
        keyboard.enter_text(text)
        return ToolResult(True, {"typed_into": target.title, "characters": len(text)})

    def press_keys(keys: str) -> ToolResult:
        try:
            combo = keyboard.parse_combo(keys)
        except ValueError as exc:
            return ToolResult(False, error=f"{exc}. Use names like enter, ctrl+s, volumeup, playpause, nexttrack.")
        blocked = keyboard.undeliverable(combo)
        if blocked:
            return ToolResult(False, error=blocked)
        target = windows.foreground_window()
        keyboard.press(combo)
        return ToolResult(True, {"pressed": "+".join(combo), "active_window": target.title if target else None})

    def lock_pc() -> ToolResult:
        try:
            if session.lock():
                return ToolResult(True, {"locked": True})
        except OSError as exc:
            return ToolResult(False, error=str(exc))
        return ToolResult(False, error="Windows did not lock the session.")

    def take_screenshot() -> ToolResult:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / f"screenshot-{datetime.now():%Y%m%d-%H%M%S}.png"
        with mss.mss() as screen:
            shot = screen.grab(screen.monitors[0])  # all monitors
            mss.tools.to_png(shot.rgb, shot.size, output=str(path))
        return ToolResult(True, {"saved_to": str(path)})

    def keys_risk(keys: str) -> Risk:
        try:
            return Risk.MEDIUM if keyboard.is_dangerous(keyboard.parse_combo(keys)) else Risk.LOW
        except ValueError:
            return Risk.LOW  # invalid keys fail in press_keys without doing anything

    name_param = {"type": "object", "properties": {"name": {"type": "string", "description": "App or window name, e.g. 'notepad', 'chrome', 'whatsapp'"}}, "required": ["name"]}

    return [
        Tool("open_application", "Open an installed application by name (e.g. Notepad, VS Code, WhatsApp, Calculator, Settings). For Google Chrome use open_chrome instead.",
             name_param, open_application, lambda name: f"Opening {name}"),
        Tool("list_open_windows", "List the open application windows and which one is active.",
             {"type": "object", "properties": {}}, list_open_windows, lambda: "Checking open windows"),
        Tool("focus_window", "Bring an open window to the front (switch to it).",
             name_param, focus_window, lambda name: f"Switching to {name}"),
        Tool("window_action", "Minimize, maximize or restore an open window.",
             {"type": "object", "properties": {"name": name_param["properties"]["name"],
                                               "action": {"type": "string", "enum": ["minimize", "maximize", "restore"]}},
              "required": ["name", "action"]},
             window_action, lambda name, action: f"{action.capitalize()} {name}"),
        Tool("close_window", "Close an open window, like clicking its X (the app may ask to save).",
             name_param, close_window, lambda name: f"Closing {name}", risk=Risk.MEDIUM,
             confirm_question=lambda name: f"Should I close {name}?"),
        Tool("type_text", "Type text into the currently active window, as if typed on the keyboard. Line breaks in the text become Enter presses.",
             {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
             type_text, lambda text: f"Typing “{text if len(text) <= 30 else text[:30] + '…'}”"),
        Tool("press_keys", "Press a key or key combination in the active window, e.g. 'enter', 'ctrl+s', 'alt+tab', "
             "'volumeup', 'volumedown', 'volumemute', 'playpause', 'nexttrack'.",
             {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"]},
             press_keys, lambda keys: f"Pressing {keys}", risk=keys_risk,
             confirm_question=lambda keys: f"Pressing {keys} may close something or delete. Should I do it?"),
        Tool("lock_pc", "Lock the PC, so the lock screen comes up and a password is needed to get back in.",
             {"type": "object", "properties": {}}, lock_pc, lambda: "Locking your PC"),
        Tool("take_screenshot", "Save a screenshot of the whole screen to the Pictures\\JARVIS folder.",
             {"type": "object", "properties": {}}, take_screenshot, lambda: "Taking a screenshot"),
    ]


def _wait(condition, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.1)
    return False
