"""Structured (JSON-lines) logging with rotating per-subsystem files.

Loggers are named `jarvis.<subsystem>`. Everything goes to `jarvis.log`,
ERROR and above also to `errors.log`, and each subsystem below gets its own file.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

SUBSYSTEM_FILES = {
    "jarvis.agent": "agent.log",
    "jarvis.voice": "voice.log",
    "jarvis.browser": "browser.log",
}

_MAX_BYTES = 5 * 1024 * 1024
_BACKUPS = 3


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def _file_handler(path: Path, level: int = logging.NOTSET) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8", delay=True
    )
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    return handler


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("jarvis")
    root.setLevel(level.upper())
    root.handlers.clear()
    root.propagate = False

    root.addHandler(_file_handler(log_dir / "jarvis.log"))
    root.addHandler(_file_handler(log_dir / "errors.log", logging.ERROR))

    if sys.stderr is not None:  # None under pythonw.exe (autostart, no console)
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(console)

    for name, filename in SUBSYSTEM_FILES.items():
        sub = logging.getLogger(name)
        sub.handlers.clear()
        sub.addHandler(_file_handler(log_dir / filename))

    def _log_uncaught(exc_type, exc, tb):
        root.critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = _log_uncaught
    # Background threads report crashes separately; without this they'd vanish (no console under pythonw).
    threading.excepthook = lambda args: root.critical(
        "Uncaught exception in thread %s", args.thread.name if args.thread else "?",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
