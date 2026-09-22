"""Top-level window helpers on the Win32 API (ctypes, no extra dependencies)."""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass
from difflib import SequenceMatcher

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_CLOSE = 0x0010
SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
VK_MENU, KEYEVENTF_KEYUP = 0x12, 0x0002

_EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetForegroundWindow.restype = wintypes.HWND


@dataclass(frozen=True)
class Window:
    hwnd: int
    title: str
    process: str  # executable name without .exe, e.g. "chrome"

    @property
    def app_name(self) -> str:
        return self.title.rsplit(" - ", 1)[-1] if " - " in self.title else self.title


def list_windows() -> list[Window]:
    """Visible, titled application windows (what you'd see in Alt+Tab), front-most first."""
    own_pid = os.getpid()
    found: list[Window] = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, GW_OWNER):
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != own_pid and buffer.value not in ("Program Manager", "Windows Input Experience"):
            found.append(Window(hwnd, buffer.value, _process_name(pid.value)))
        return True

    user32.EnumWindows(_EnumProc(callback), 0)
    return found


def foreground_window() -> Window | None:
    hwnd = user32.GetForegroundWindow()
    return next((w for w in list_windows() if w.hwnd == hwnd), None)


def find_window(query: str) -> Window | None:
    """Best match by title or process name (e.g. "chrome", "notepad", "whatsapp")."""
    query = query.lower().strip()
    best, best_score = None, 0.0
    for window in list_windows():
        title, process = window.title.lower(), window.process.lower()
        if query in (process, title):
            score = 1.0
        elif query in title or query in process:
            score = 0.9
        else:
            score = max(SequenceMatcher(None, query, process).ratio(), SequenceMatcher(None, query, title).ratio())
        if score > best_score:
            best, best_score = window, score
    return best if best_score >= 0.6 else None


def focus(window: Window) -> bool:
    if user32.IsIconic(window.hwnd):
        user32.ShowWindow(window.hwnd, SW_RESTORE)
    # Windows only lets the foreground process change focus; a synthetic Alt press lifts that lock.
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(window.hwnd)
    return _wait(lambda: user32.GetForegroundWindow() == window.hwnd, 2.0)


def show(window: Window, command: int) -> None:
    user32.ShowWindow(window.hwnd, command)


def is_minimized(window: Window) -> bool:
    return bool(user32.IsIconic(window.hwnd))


def is_maximized(window: Window) -> bool:
    return bool(user32.IsZoomed(window.hwnd))


def request_close(window: Window, timeout: float = 3.0) -> bool:
    """Politely ask the window to close (the app may prompt to save). True if it closed."""
    user32.PostMessageW(window.hwnd, WM_CLOSE, 0, 0)
    return _wait(lambda: not user32.IsWindow(window.hwnd) or not user32.IsWindowVisible(window.hwnd), timeout)


def _wait(condition, timeout: float) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.1)
    return condition()


def _process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(512)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return os.path.splitext(os.path.basename(buffer.value))[0]
        return ""
    finally:
        kernel32.CloseHandle(handle)
