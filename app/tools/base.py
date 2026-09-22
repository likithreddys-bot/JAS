"""Tool definitions shared by every tool and every LLM provider.

A tool is the only way the LLM can act on the computer. Each tool declares a JSON
schema for its arguments and a risk level; the executor enforces both.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Risk(Enum):
    LOW = "low"  # run automatically
    MEDIUM = "medium"  # ask the user first
    HIGH = "high"  # always ask, stating the exact impact


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"ok": True, **self.data} if self.ok else {"ok": False, "error": self.error}


class TaskCancelled(Exception):
    """The user paused or cancelled while a task was running."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema (type: object)
    run: Callable[..., ToolResult]
    label: Callable[..., str]  # short present-tense UI text, e.g. "Opening Notepad"
    risk: Risk | Callable[..., Risk] = Risk.LOW
    confirm_question: Callable[..., str] | None = None  # spoken when confirmation is needed

    def risk_for(self, args: dict[str, Any]) -> Risk:
        return self.risk(**args) if callable(self.risk) else self.risk
