"""Locking the Windows session, and checking that it really locked.

Windows refuses synthetic Win+L (it is a protected sequence), so pressing the keys does
nothing while looking like it worked. `LockWorkStation` is the real call.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

DESKTOP_SWITCHDESKTOP = 0x0100
user32.OpenInputDesktop.restype = wintypes.HANDLE


def is_locked() -> bool:
    """True when the session is locked: the input desktop belongs to Winlogon, not to us."""
    desktop = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not desktop:
        return True
    user32.CloseDesktop(desktop)
    return False


def lock(timeout: float = 5.0) -> bool:
    """Lock the session. Returns True only once the lock screen is actually up."""
    if not user32.LockWorkStation():
        raise OSError(f"Windows refused to lock the session (error {ctypes.get_last_error()})")
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if is_locked():
            return True
        time.sleep(0.1)
    return False
