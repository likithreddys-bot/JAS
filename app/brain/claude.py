"""Conversational brain backed by the Claude API.

Streams the reply as text deltas so speech can start on the first sentence.
Keeps short-term conversation history in memory; a new conversation starts
after a period of silence or when the history grows long.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

import anthropic

from app.brain.base import IDLE_RESET_SECONDS, MAX_TURNS, BrainError, system_prompt

log = logging.getLogger("jarvis.agent")

MAX_TOKENS = 8000


class ClaudeBrain:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise BrainError("No Claude API key. Add CLAUDE_API_KEY to the .env file.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._messages: list[dict] = []
        self._last_turn = 0.0

    def reply(self, text: str) -> Iterator[str]:
        """Stream Claude's answer to `text` as text deltas."""
        if time.monotonic() - self._last_turn > IDLE_RESET_SECONDS or len(self._messages) >= 2 * MAX_TURNS:
            self._messages = []  # new conversation (reset rather than trim: history stays append-only)
        messages = self._messages + [{"role": "user", "content": text}]
        system = system_prompt()
        started = time.perf_counter()
        try:
            with self._client.beta.messages.stream(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
                output_config={"effort": "low"},  # quick conversational replies
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                first = True
                for delta in stream.text_stream:
                    if first:
                        log.info("First reply text after %.2f s", time.perf_counter() - started)
                        first = False
                    yield delta
                final = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise BrainError("Claude API key was rejected. Check CLAUDE_API_KEY in .env.") from exc
        except anthropic.PermissionDeniedError as exc:
            raise BrainError("This Claude API key isn't allowed to use this model.") from exc
        except anthropic.RateLimitError as exc:
            raise BrainError("Claude rate limit reached. Try again in a minute.") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code == 402 or "credit" in str(exc.message).lower():
                raise BrainError("Claude account has no credits left.") from exc
            raise BrainError(f"Claude API error ({exc.status_code}).") from exc
        except anthropic.APIConnectionError as exc:
            raise BrainError("Can't reach Claude. Check the internet connection.") from exc

        log.info(
            "Reply done in %.2f s (stop=%s, in=%d, out=%d tokens)",
            time.perf_counter() - started,
            final.stop_reason,
            final.usage.input_tokens,
            final.usage.output_tokens,
        )
        if final.stop_reason == "refusal":
            yield "Sorry, I can't help with that."
            return  # don't keep a refused exchange in history
        self._messages = messages + [{"role": "assistant", "content": final.content}]
        self._last_turn = time.monotonic()
