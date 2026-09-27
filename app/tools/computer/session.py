"""Locking the Windows session, and checking that it really locked.

Windows refuses synthetic Win+L (it is a protected sequence), so pressing the keys does
nothing while looking like it worked. `LockWorkStation` is the real call.
"""
from __future__ import annotations

import ctypes
import getpass
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


class _UserInfo3(ctypes.Structure):
    """USER_INFO_3, for the one field that matters: how many times the password was got wrong."""
    _fields_ = [("name", wintypes.LPWSTR), ("password", wintypes.LPWSTR),
                ("password_age", wintypes.DWORD), ("priv", wintypes.DWORD),
                ("home_dir", wintypes.LPWSTR), ("comment", wintypes.LPWSTR),
                ("flags", wintypes.DWORD), ("script_path", wintypes.LPWSTR),
                ("auth_flags", wintypes.DWORD), ("full_name", wintypes.LPWSTR),
                ("usr_comment", wintypes.LPWSTR), ("parms", wintypes.LPWSTR),
                ("workstations", wintypes.LPWSTR), ("last_logon", wintypes.DWORD),
                ("last_logoff", wintypes.DWORD), ("acct_expires", wintypes.DWORD),
                ("max_storage", wintypes.DWORD), ("units_per_week", wintypes.DWORD),
                ("logon_hours", ctypes.POINTER(wintypes.BYTE)), ("bad_pw_count", wintypes.DWORD),
                ("num_logons", wintypes.DWORD), ("logon_server", wintypes.LPWSTR),
                ("country_code", wintypes.DWORD), ("code_page", wintypes.DWORD),
                ("user_id", wintypes.DWORD), ("primary_group_id", wintypes.DWORD),
                ("profile", wintypes.LPWSTR), ("home_dir_drive", wintypes.LPWSTR),
                ("password_expired", wintypes.DWORD)]


def bad_password_count() -> int | None:
    """How many times this account's password has been got wrong. None if Windows won't say.

    Readable for your own account without administrator rights, unlike the Security event log.
    """
    netapi = ctypes.WinDLL("netapi32")
    buffer = ctypes.POINTER(_UserInfo3)()
    if netapi.NetUserGetInfo(None, getpass.getuser(), 3, ctypes.byref(buffer)) != 0:
        return None
    try:
        return int(buffer.contents.bad_pw_count)
    finally:
        netapi.NetApiBufferFree(buffer)
