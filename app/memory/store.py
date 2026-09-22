"""JARVIS's long-term memory: facts about the user, to-dos, learned words and a conversation log.

Stored only on this laptop (SQLite). Relevant parts are included in the LLM prompt so JARVIS
knows the user across conversations and restarts.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY, created TEXT NOT NULL, text TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, created TEXT NOT NULL, text TEXT NOT NULL, done_at TEXT);
CREATE TABLE IF NOT EXISTS words (word TEXT PRIMARY KEY COLLATE NOCASE, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exchanges (id INTEGER PRIMARY KEY, at TEXT NOT NULL, user TEXT NOT NULL, assistant TEXT NOT NULL);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def _query(self, sql: str, *args) -> list[tuple]:
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
            self._db.commit()
            return rows

    # --- facts -----------------------------------------------------------------

    def remember(self, text: str) -> bool:
        """Store a fact; False if it was already known."""
        text = " ".join(text.split())
        return bool(self._query("INSERT OR IGNORE INTO facts (created, text) VALUES (?, ?) RETURNING id", _now(), text))

    def facts(self, limit: int = 50) -> list[str]:
        return [r[0] for r in reversed(self._query("SELECT text FROM facts ORDER BY id DESC LIMIT ?", limit))]

    def forget(self, about: str) -> list[str]:
        """Forget facts containing `about` (case-insensitive). Returns what was forgotten."""
        pattern = f"%{about.strip()}%"
        return [r[0] for r in self._query("DELETE FROM facts WHERE text LIKE ? RETURNING text", pattern)]

    # --- to-dos ----------------------------------------------------------------

    def add_todo(self, text: str) -> int:
        return self._query("INSERT INTO todos (created, text) VALUES (?, ?) RETURNING id", _now(), " ".join(text.split()))[0][0]

    def open_todos(self) -> list[tuple[int, str]]:
        return self._query("SELECT id, text FROM todos WHERE done_at IS NULL ORDER BY id")

    def complete_todo(self, match: str) -> list[str]:
        """Mark open to-dos containing `match` (or with that number) as done."""
        if match.strip().isdigit():
            return [r[0] for r in self._query(
                "UPDATE todos SET done_at = ? WHERE id = ? AND done_at IS NULL RETURNING text", _now(), int(match))]
        return [r[0] for r in self._query(
            "UPDATE todos SET done_at = ? WHERE text LIKE ? AND done_at IS NULL RETURNING text", _now(), f"%{match.strip()}%")]

    # --- learned words (spellings for speech recognition) ------------------------

    def learn_word(self, word: str) -> None:
        self._query("INSERT OR IGNORE INTO words (word, created) VALUES (?, ?)", word.strip(), _now())

    def words(self) -> list[str]:
        return [r[0] for r in self._query("SELECT word FROM words ORDER BY created")]

    # --- conversation log --------------------------------------------------------

    def log_exchange(self, user: str, assistant: str) -> None:
        self._query("INSERT INTO exchanges (at, user, assistant) VALUES (?, ?, ?)", _now(), user, assistant)

    def recent_exchanges(self, limit: int = 6) -> list[tuple[str, str, str]]:
        return list(reversed(self._query("SELECT at, user, assistant FROM exchanges ORDER BY id DESC LIMIT ?", limit)))

    def search(self, query: str, limit: int = 10) -> dict:
        words = [w for w in query.lower().split() if len(w) > 2] or [query.lower()]
        clause = " OR ".join(["lower({col}) LIKE ?"] * len(words))
        args = [f"%{w}%" for w in words]
        facts = self._query(f"SELECT text FROM facts WHERE {clause.format(col='text')} LIMIT ?", *args, limit)
        talks = self._query(
            f"SELECT at, user, assistant FROM exchanges WHERE {clause.format(col='user')} OR "
            f"{clause.format(col='assistant')} ORDER BY id DESC LIMIT ?", *args, *args, limit)
        return {"facts": [r[0] for r in facts],
                "conversations": [{"when": at, "user": u, "jarvis": a} for at, u, a in talks]}

    # --- prompt context ------------------------------------------------------------

    def context(self) -> str:
        """What JARVIS knows about the user, for the system prompt."""
        sections = []
        if facts := self.facts():
            sections.append("Things you remember about the user:\n" + "\n".join(f"- {f}" for f in facts))
        if todos := self.open_todos():
            sections.append("The user's open to-dos:\n" + "\n".join(f"- ({i}) {t}" for i, t in todos))
        if talks := self.recent_exchanges():
            sections.append("Your most recent exchanges (possibly from earlier sessions):\n" + "\n".join(
                f"- [{at[:16].replace('T', ' ')}] User: {u} | You: {a[:200]}" for at, u, a in talks))
        return "\n\n".join(sections)
