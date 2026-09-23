"""Global keyboard shortcut (default Ctrl+Space) that wakes JARVIS from anywhere in Windows."""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

log = logging.getLogger("jarvis.ui")

WM_HOTKEY = 0x0312
HOTKEY_ID = 0xB0B  # any id unique within this process
MODIFIERS = {"ctrl": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}
KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "insert": 0x2D,
        **{f"f{n}": 0x6F + n for n in range(1, 13)},
        **{c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz0123456789"}}


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, on_pressed: Callable[[], None]) -> None:
        super().__init__()
        self._on_pressed = on_pressed

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self._on_pressed()
        return False, 0


def parse_shortcut(shortcut: str) -> tuple[int, int]:
    """"ctrl+space" -> (modifier flags, virtual key code)."""
    parts = [p.strip().lower() for p in shortcut.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError("empty shortcut")
    modifiers = 0
    for part in parts[:-1]:
        if part not in MODIFIERS:
            raise ValueError(f"unknown modifier {part!r}")
        modifiers |= MODIFIERS[part]
    key = parts[-1]
    if key not in KEYS:
        raise ValueError(f"unknown key {key!r}")
    return modifiers, KEYS[key]


def register(shortcut: str, on_pressed: Callable[[], None]) -> _HotkeyFilter | None:
    """Register the shortcut system-wide. Returns None (and logs) if it's taken or invalid."""
    try:
        modifiers, key = parse_shortcut(shortcut)
    except ValueError as exc:
        log.warning("Bad HOTKEY setting %r: %s", shortcut, exc)
        return None
    if not ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, modifiers, key):
        log.warning("Couldn't register %s (another app may be using it)", shortcut)
        return None
    handler = _HotkeyFilter(on_pressed)
    QCoreApplication.instance().installNativeEventFilter(handler)
    log.info("Global shortcut %s is active", shortcut)
    return handler
