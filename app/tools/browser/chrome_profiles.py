"""The user's own Chrome profiles: list them, match a spoken name, open one (optionally at a URL).

Chrome (136+) refuses automation on the user's real profiles, so these windows are opened
but never controlled; JARVIS's automated browsing uses its own profile (session.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from app.tools.computer import windows

USER_DATA = Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))
CHROME_CANDIDATES = [
    Path(os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")),
    Path(os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
]


@dataclass(frozen=True)
class Profile:
    directory: str  # e.g. "Profile 2"
    name: str  # what Chrome shows, e.g. "Alex"
    email: str


def chrome_exe() -> Path | None:
    return next((p for p in CHROME_CANDIDATES if p.exists()), None)


def list_profiles(user_data: Path = USER_DATA) -> tuple[list[Profile], str | None]:
    """All profiles and the directory of the last-used one."""
    state = json.loads((user_data / "Local State").read_text(encoding="utf-8"))
    profile_state = state.get("profile", {})
    profiles = [
        Profile(directory, info.get("name", directory), info.get("user_name", ""))
        for directory, info in profile_state.get("info_cache", {}).items()
    ]
    return profiles, profile_state.get("last_used")


def find_profile(spoken: str, profiles: list[Profile]) -> Profile | None:
    query = spoken.lower().strip()
    exact_name = next((p for p in profiles if p.name.lower() == query), None)
    if exact_name:  # "Alex" must pick the profile named Alex, not alex@… of another profile
        return exact_name
    best, best_score = None, 0.0
    for profile in profiles:
        candidates = [profile.name.lower(), profile.email.lower(), profile.email.split("@")[0].lower()]
        if query in candidates:
            return profile
        score = max(
            [0.9 for c in candidates if c and (query in c or c in query)]
            + [SequenceMatcher(None, query, c).ratio() for c in candidates if c]
        )
        if score > best_score:
            best, best_score = profile, score
    return best if best_score >= 0.8 else None


def open_profile(profile: Profile, url: str | None, timeout: float = 10.0) -> windows.Window | None:
    """Open `url` as a new tab in `profile` (or a new window when there's no URL).

    Returns the Chrome window that came up or to the front, or None if nothing happened.
    """
    exe = chrome_exe()
    if exe is None:
        raise FileNotFoundError("Google Chrome is not installed")
    # Titles as well as handles: when Chrome is already open the URL becomes a *tab*, so no new
    # window appears and only the existing window's title changes. Reporting "no window appeared"
    # for a tab that opened fine was the most common browser failure in the logs.
    before = {w.hwnd: w.title for w in windows.list_windows()}
    args = [str(exe), f"--profile-directory={profile.directory}"] + ([url] if url else ["--new-window"])
    subprocess.Popen(args)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        time.sleep(0.3)
        current = [w for w in windows.list_windows() if w.process.lower() == "chrome"]
        new = [w for w in current if w.hwnd not in before]
        if new:
            return new[0]
        changed = [w for w in current if w.hwnd in before and before[w.hwnd] != w.title]
        if changed:
            return changed[0]  # an existing window took the new tab
        front = windows.foreground_window()
        if url and front and front.process.lower() == "chrome" and time.monotonic() > end - timeout + 1.0:
            return front
    # Chrome is running but nothing visibly moved: a tab in a background window still counts.
    chrome = [w for w in windows.list_windows() if w.process.lower() == "chrome"]
    return chrome[0] if (url and chrome) else None


def pick(spoken: str, default: str = "") -> tuple[Profile | None, str]:
    """Profile for a request: the one named, else the configured default, else the last used.

    Returns (profile, error message).
    """
    try:
        profiles, last_used = list_profiles()
    except FileNotFoundError:
        return None, "Couldn't find Chrome's profile list."
    if not profiles:
        return None, "Chrome has no profiles."
    wanted = spoken or default
    if wanted:
        profile = find_profile(wanted, profiles)
        if profile is None:
            return None, f"No Chrome profile matches {wanted!r}. Profiles: {', '.join(p.name for p in profiles)}."
        return profile, ""
    return next((p for p in profiles if p.directory == last_used), profiles[0]), ""


def normalize_url(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    return url
