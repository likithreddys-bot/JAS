"""Choose the LLM provider from settings."""
from __future__ import annotations

from typing import Callable, Iterable

from app.brain.base import BrainError
from app.config.settings import Settings

Responder = Callable[[str], Iterable[str]]


def create_responder(settings: Settings) -> Responder:
    provider = settings.llm_provider.strip().lower()
    if provider == "gemini":
        from app.brain.gemini import GeminiBrain

        return GeminiBrain(settings.gemini_api_key, settings.gemini_model).reply
    if provider == "claude":
        from app.brain.claude import ClaudeBrain

        return ClaudeBrain(settings.claude_api_key, settings.claude_model).reply
    raise BrainError(f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Use 'gemini' or 'claude'.")
