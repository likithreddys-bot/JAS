"""Choose the LLM provider from settings."""
from __future__ import annotations

import logging
from typing import Callable, Iterable

from app.brain.base import BrainError
from app.config.settings import Settings
from app.tools.executor import ToolExecutor

log = logging.getLogger("jarvis.agent")

Responder = Callable[[str], Iterable[str]]


def create_responder(
    settings: Settings, executor: ToolExecutor | None = None, memory: Callable[[], str] = lambda: ""
) -> Responder:
    provider = settings.llm_provider.strip().lower()
    if provider == "gemini":
        from app.brain.gemini import GeminiBrain

        return GeminiBrain(
            settings.gemini_api_key, settings.gemini_model, executor, settings.gemini_thinking,
            settings.user_name, memory, settings.assistant_name,
        ).reply
    if provider == "claude":
        from app.brain.claude import ClaudeBrain

        return ClaudeBrain(
            settings.claude_api_key, settings.claude_model, executor,
            settings.user_name, memory, settings.assistant_name,
        ).reply
    raise BrainError(f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Use 'gemini' or 'claude'.")
