"""Data behind the dashboard window: status, activity, settings, and the type-a-request box."""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

import psutil
from PySide6.QtCore import Property, QObject, Signal, Slot

from app.config import env_file
from app.config.settings import Settings
from app.core.jarvis import Jarvis
from app.memory.store import MemoryStore
from ui.activity import ActivityLog
from ui.theme import STATE_COLORS, STATE_LABELS

log = logging.getLogger("jarvis.ui")

MEETINGS_REFRESH_SECONDS = 120

# What the Settings tab offers, in order. (key, label, hint)
EDITABLE = [
    ("USER_NAME", "Your name", "How it addresses you"),
    ("HOME_CITY", "Home city", "Used for the morning weather"),
    ("CHROME_PROFILE", "Chrome profile", "Which profile websites and music open in (empty = last used)"),
    ("HOTKEY", "Shortcut", "Wake it from anywhere, e.g. ctrl+space"),
    ("WAKE_WORD_THRESHOLD", "Wake word sensitivity", "0–1. Lower catches more, but triggers more often"),
    ("LISTEN_END_SILENCE", "Pause before I answer", "Seconds of silence that end your sentence"),
    ("LISTEN_START_TIMEOUT", "Wait for you to start", "Seconds"),
    ("FOLLOW_UP_SECONDS", "Keep listening after a reply", "Seconds; 0 turns follow-ups off"),
    ("BREAK_REMINDER_MINUTES", "Break reminder", "Minutes of screen time; 0 turns it off"),
    ("MORNING_MUSIC", "Morning music", "Played after the morning briefing"),
    ("TTS_SPEED", "Voice speed", "1.0 is normal"),
    ("STT_VOCABULARY", "Words to expect", "Names it should spell correctly"),
    ("LLM_PROVIDER", "AI brain", "gemini or claude"),
    ("GEMINI_MODEL", "Gemini models", "Tried in order if one is busy"),
    ("GEMINI_THINKING", "Thinking depth", "minimal is fastest"),
    ("START_RESTING", "Start in rest mode", "true or false"),
]
RESTART_NEEDED = {"HOTKEY", "WAKE_WORD_THRESHOLD", "LLM_PROVIDER", "GEMINI_MODEL", "GEMINI_THINKING",
                  "LISTEN_END_SILENCE", "LISTEN_START_TIMEOUT", "TTS_SPEED", "START_RESTING", "CHROME_PROFILE"}


class DashboardBridge(QObject):
    changed = Signal()
    savedMessage = Signal(str)

    def __init__(
        self,
        core: Jarvis,
        memory: MemoryStore,
        activity: ActivityLog,
        settings: Settings,
        meetings: Callable[[], list[str]] | None = None,
        google_connected: Callable[[], bool] = lambda: False,
    ) -> None:
        super().__init__()
        self._core = core
        self._memory = memory
        self._activity = activity
        self._settings = settings
        self._meetings_source = meetings
        self._google_connected = google_connected
        self._started = time.time()
        self._process = psutil.Process()
        self._meetings: list[str] = []
        self._meetings_checked = 0.0
        self._status: dict = {}
        self.refresh()

    # --- properties for QML ---------------------------------------------------

    @Property("QVariantMap", notify=changed)
    def status(self) -> dict:
        return self._status

    @Property("QVariantList", notify=changed)
    def activity(self) -> list[dict]:
        return self._activity.entries()

    @Property("QVariantList", notify=changed)
    def settingsList(self) -> list[dict]:
        values = env_file.read_values(self._settings.model_config["env_file"])
        return [{"key": key, "label": label, "hint": hint,
                 "value": values.get(key, str(getattr(self._settings, key.lower(), "")))}
                for key, label, hint in EDITABLE]

    # --- actions ---------------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        state = self._core.state.current
        uptime = int(time.time() - self._started)
        self._status = {
            "state": STATE_LABELS[state],
            "color": STATE_COLORS[state],
            "uptime": f"{uptime // 3600}h {uptime % 3600 // 60}m" if uptime >= 3600 else f"{uptime // 60}m",
            "requests": self._activity.requests_today,
            "actions": self._activity.actions_today,
            "facts": len(self._memory.facts(limit=1000)),
            "todos": len(self._memory.open_todos()),
            "reminders": [f"{r['due']:%a %I:%M %p} — {r['text']}".replace(" 0", " ")
                          for r in self._memory.upcoming_reminders()[:3]],
            "meetings": self._meetings,
            "services": self._services(),
            "cpu": f"{self._process.cpu_percent() / max(psutil.cpu_count(), 1):.0f}%",
            "ram": f"{self._process.memory_info().rss / 1e6:.0f} MB",
        }
        self.changed.emit()
        if self._meetings_source and time.time() - self._meetings_checked > MEETINGS_REFRESH_SECONDS:
            self._meetings_checked = time.time()
            threading.Thread(target=self._load_meetings, name="dashboard-meetings", daemon=True).start()

    def _load_meetings(self) -> None:
        try:
            self._meetings = self._meetings_source()
        except Exception as exc:
            log.warning("Dashboard couldn't load meetings: %s", exc)
            self._meetings = []

    def _services(self) -> list[dict]:
        provider = self._settings.llm_provider.lower()
        key = self._settings.gemini_api_key if provider == "gemini" else self._settings.claude_api_key
        return [
            {"name": f"AI brain ({provider})", "ok": bool(key)},
            {"name": "Google Calendar & Gmail", "ok": self._google_connected()},
            {"name": "Microphone", "ok": self._core.state.current.value != "sleeping"},
            {"name": f"Wake word ({self._settings.wake_word_engine})", "ok": self._settings.wake_word_enabled},
        ]

    @Slot(str)
    def ask(self, text: str) -> None:
        """Send a typed request, as if it had been spoken."""
        if not self._core.ask_text(text):
            self.savedMessage.emit("The assistant is busy right now.")

    @Slot("QVariantMap")
    def save(self, changes: dict) -> None:
        try:
            changed = env_file.update_values(self._settings.model_config["env_file"], dict(changes))
        except OSError as exc:
            self.savedMessage.emit(f"Couldn't save: {exc}")
            return
        if not changed:
            self.savedMessage.emit("Nothing changed.")
            return
        needs_restart = sorted(set(changed) & RESTART_NEEDED)
        message = f"Saved {len(changed)} setting{'s' if len(changed) > 1 else ''}."
        if needs_restart:
            message += " Restart JARVIS to apply: " + ", ".join(needs_restart).lower().replace("_", " ") + "."
        log.info("Settings saved from dashboard: %s", ", ".join(changed))
        self.savedMessage.emit(message)

    @Slot()
    def openLogs(self) -> None:
        os.startfile(self._settings.log_dir)

    @Slot()
    def restart(self) -> None:
        """Restart JARVIS so changed settings take effect."""
        import sys

        from PySide6.QtWidgets import QApplication

        python = Path(sys.executable)
        windowless = python.with_name("pythonw.exe")
        script = Path(__file__).resolve().parents[1] / "run.py"
        # A helper waits for this instance to exit (it holds the single-instance lock), then starts JARVIS again.
        starter = (f"import subprocess, time; time.sleep(4); "
                   f"subprocess.Popen([{str(windowless if windowless.exists() else python)!r}, {str(script)!r}], "
                   f"cwd={str(script.parent)!r})")
        subprocess.Popen([str(windowless if windowless.exists() else python), "-c", starter],
                         cwd=str(script.parent), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        log.info("Restarting JARVIS at the user's request")
        QApplication.quit()
