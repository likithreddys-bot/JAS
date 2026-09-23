"""Keyboard input into the foreground window.

Text is pasted via the clipboard (restored afterwards) or, as a fallback, sent as Unicode key
events; both work for any language. Key combos use PyAutoGUI names.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import pyautogui

pyautogui.PAUSE = 0.02

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
CHAR_DELAY = 0.012  # seconds between typed characters
SETTLE_DELAY = 0.2  # let a just-opened/just-focused app get ready for input
PASTE_SETTLE = 0.4
CF_UNICODETEXT = 13
TEXT_FORMATS = {1, 7, 13, 16}  # CF_TEXT, CF_OEMTEXT, CF_UNICODETEXT, CF_LOCALE
GMEM_MOVEABLE = 0x0002

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

# Friendly names the LLM may use -> PyAutoGUI key names.
KEY_ALIASES = {"control": "ctrl", "windows": "win", "escape": "esc", "return": "enter", "del": "delete",
               "page up": "pageup", "page down": "pagedown", "volume up": "volumeup",
               "volume down": "volumedown", "mute": "volumemute", "play": "playpause", "pause": "playpause",
               "next": "nexttrack", "previous": "prevtrack", "play pause": "playpause",
               "next track": "nexttrack", "previous track": "prevtrack", "prev track": "prevtrack",
               "stop": "stop", "space bar": "space", "spacebar": "space"}
# Combos that can destroy work or close things: need confirmation.
DANGEROUS_COMBOS = {("alt", "f4"), ("ctrl", "w"), ("ctrl", "shift", "w"), ("delete",), ("shift", "delete")}


class _KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _Input(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KeyboardInput), ("_pad", ctypes.c_byte * 32)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def type_unicode(text: str) -> None:
    raw = text.encode("utf-16-le")
    codes = [int.from_bytes(raw[i : i + 2], "little") for i in range(0, len(raw), 2)]  # UTF-16 code units
    time.sleep(SETTLE_DELAY)
    for code in codes:
        if code == 0x0A:  # newline -> Enter
            pair = [_key_event(0x0D, 0), _key_event(0x0D, KEYEVENTF_KEYUP)]
        else:
            pair = [_unicode_event(code, 0), _unicode_event(code, KEYEVENTF_KEYUP)]
        # One character per call with a short pause: apps like the new Notepad drop or
        # repeat characters when a whole string arrives in a single SendInput burst.
        user32.SendInput(2, (_Input * 2)(*pair), ctypes.sizeof(_Input))
        time.sleep(CHAR_DELAY)


def enter_text(text: str) -> None:
    """Enter text into the focused app by pasting it (fast and exact), then restore the clipboard.

    Key-by-key typing drops/repeats characters in apps like the new Notepad, so it is only
    used when the clipboard holds something other than text (e.g. an image) we must not lose.
    """
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")  # LLMs sometimes escape these
    if not _clipboard_is_text_or_empty():
        type_unicode(text)
        return
    previous = get_clipboard_text()
    set_clipboard_text(text.replace("\n", "\r\n"))
    time.sleep(SETTLE_DELAY)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(PASTE_SETTLE)  # the app reads the clipboard asynchronously
    if previous is not None:
        set_clipboard_text(previous)


def get_clipboard_text() -> str | None:
    if not _open_clipboard():
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text: str) -> None:
    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    pointer = kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not _open_clipboard():
        kernel32.GlobalFree(handle)
        raise OSError("clipboard is busy")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise OSError("could not set clipboard")
    finally:
        user32.CloseClipboard()


def _clipboard_is_text_or_empty() -> bool:
    if not _open_clipboard():
        return False
    try:
        formats, current = set(), 0
        while current := user32.EnumClipboardFormats(current):
            formats.add(current)
        return formats <= TEXT_FORMATS
    finally:
        user32.CloseClipboard()


def _open_clipboard() -> bool:
    for _ in range(10):  # another app may hold it briefly
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.05)
    return False


def parse_combo(keys: str) -> tuple[str, ...]:
    """"Ctrl + S" -> ("ctrl", "s"). Raises ValueError for unknown keys."""
    parts = []
    for raw in keys.lower().replace(" + ", "+").split("+"):
        # "media_play_pause", "Volume_Up", "media next track" -> our names
        spoken = " ".join(raw.replace("_", " ").replace("-", " ").split()).removeprefix("media ")
        key = KEY_ALIASES.get(spoken, spoken.replace(" ", ""))
        if key not in pyautogui.KEYBOARD_KEYS:
            raise ValueError(f"unknown key {raw.strip()!r}")
        parts.append(key)
    if not parts:
        raise ValueError("no keys given")
    return tuple(parts)


def is_dangerous(combo: tuple[str, ...]) -> bool:
    return combo in DANGEROUS_COMBOS


def undeliverable(combo: tuple[str, ...]) -> str | None:
    """Why Windows will ignore this combo from an application, or None if it will arrive.

    These are protected sequences: pressing them succeeds silently and does nothing at all.
    """
    keys = set(combo)
    if keys & {"win", "winleft", "winright"} and "l" in keys:
        return "Windows does not let applications press Win+L. Use lock_pc to lock the PC."
    if {"ctrl", "alt", "delete"} <= keys:
        return "Windows does not let applications press Ctrl+Alt+Delete."
    return None


def press(combo: tuple[str, ...]) -> None:
    pyautogui.hotkey(*combo)


def _unicode_event(code: int, flags: int) -> _Input:
    event = _Input(type=INPUT_KEYBOARD)
    event.ki = _KeyboardInput(0, code, KEYEVENTF_UNICODE | flags, 0, 0)
    return event


def _key_event(vk: int, flags: int) -> _Input:
    event = _Input(type=INPUT_KEYBOARD)
    event.ki = _KeyboardInput(vk, 0, flags, 0, 0)
    return event
