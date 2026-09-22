"""Find and launch installed applications via the Start menu's app list.

Uses `Get-StartApps`, which covers classic programs and Store apps alike, and launches
through `shell:AppsFolder`, exactly like clicking the app in the Start menu.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.tools.computer import windows

log = logging.getLogger("jarvis.agent")

# How people say it -> how the Start menu names it.
ALIASES = {
    "chrome": "google chrome",
    "google": "google chrome",
    "browser": "google chrome",
    "vs code": "visual studio code",
    "vscode": "visual studio code",
    "code": "visual studio code",
    "explorer": "file explorer",
    "files": "file explorer",
    "file manager": "file explorer",
    "my computer": "file explorer",
    "cmd": "command prompt",
    "powershell": "windows powershell",
    "control panel": "control panel",
    "store": "microsoft store",
    "word": "word",
    "excel": "excel",
}
_NO_WINDOW = subprocess.CREATE_NO_WINDOW


@dataclass(frozen=True)
class App:
    name: str
    app_id: str


class AppIndex:
    def __init__(self) -> None:
        self._apps: list[App] = []
        self._lock = threading.Lock()

    def refresh(self) -> None:
        output = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW,
        ).stdout
        entries = json.loads(output or "[]")
        if isinstance(entries, dict):
            entries = [entries]
        with self._lock:
            self._apps = [App(e["Name"], e["AppID"]) for e in entries if e.get("Name") and e.get("AppID")]
        log.info("App index: %d apps", len(self._apps))

    def find(self, spoken: str) -> App | None:
        with self._lock:
            apps = list(self._apps)
        if not apps:
            self.refresh()
            with self._lock:
                apps = list(self._apps)
        query = _normalize(spoken)
        query = ALIASES.get(query, query)
        best, best_score = None, 0.0
        for app in apps:
            name = _normalize(app.name)
            if name == query:
                return app
            if name.startswith(query + " ") or query in name.split():
                score = 0.9 - 0.001 * len(name)  # whole-word match; prefer the shortest name
            else:
                # Tolerates speech-recognition slips ("calculater") but not different apps
                # ("photoshop" must not open "Photos").
                score = SequenceMatcher(None, query, name).ratio()
            if score > best_score:
                best, best_score = app, score
        return best if best_score >= 0.85 else None


def launch(app: App, timeout: float = 15.0) -> windows.Window | None:
    """Launch and wait until a window for it appears or comes to the front."""
    before = {w.hwnd for w in windows.list_windows()}
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app.app_id}"], creationflags=_NO_WINDOW)
    words = [w for w in _normalize(app.name).split() if len(w) > 2]
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        time.sleep(0.3)
        current = windows.list_windows()
        new = [w for w in current if w.hwnd not in before]
        if new:
            time.sleep(0.5)  # some apps show a short-lived window first; report the one that stays
            front = windows.foreground_window()
            if front and front.hwnd not in before:
                return front
            remaining = [w for w in windows.list_windows() if w.hwnd not in before]
            return remaining[0] if remaining else new[0]
        front = windows.foreground_window()
        if front and any(word in f"{front.title} {front.process}".lower() for word in words):
            return front  # single-instance app brought its existing window forward
    return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+ ]", " ", text.lower())).strip()
