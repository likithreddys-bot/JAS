"""Conversational brain backed by Google Gemini (free tier via AI Studio API key).

Streams the reply as text deltas so speech can start on the first sentence.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

import httpx
from google import genai
from google.genai import errors, types

from app.brain.base import IDLE_RESET_SECONDS, MAX_TURNS, BrainError, system_prompt

log = logging.getLogger("jarvis.agent")


# Try the next model when one is overloaded (503), rate-limited (429) or retired (404).
_RETRY_NEXT_MODEL = {404, 429, 500, 503}


class GeminiBrain:
    def __init__(self, api_key: str, models: str) -> None:
        """`models` is a comma-separated priority list, e.g. "gemini-3.1-flash-lite,gemini-3-flash-preview"."""
        if not api_key:
            raise BrainError("No Gemini API key. Add GEMINI_API_KEY to the .env file.")
        # One attempt per model: on overload we move to the next model instead of the SDK's
        # built-in backoff (which can stall a spoken reply for 10+ s). Timeout is in ms.
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=20_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        self._models = [m.strip() for m in models.split(",") if m.strip()]
        self._history: list[dict] = []
        self._last_turn = 0.0

    def reply(self, text: str) -> Iterator[str]:
        """Stream Gemini's answer to `text` as text deltas."""
        if time.monotonic() - self._last_turn > IDLE_RESET_SECONDS or len(self._history) >= 2 * MAX_TURNS:
            self._history = []
        contents = self._history + [{"role": "user", "parts": [{"text": text}]}]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        started = time.perf_counter()
        answer = ""
        for index, model in enumerate(self._models):
            is_last = index == len(self._models) - 1
            try:
                for chunk in self._client.models.generate_content_stream(
                    model=model, contents=contents, config=config
                ):
                    if chunk.text:
                        if not answer:
                            log.info("First reply text from %s after %.2f s", model, time.perf_counter() - started)
                        answer += chunk.text
                        yield chunk.text
                break
            except errors.APIError as exc:
                # Only switch models if nothing was spoken yet; otherwise the reply would repeat.
                if answer or is_last or exc.code not in _RETRY_NEXT_MODEL:
                    raise BrainError(_error_reason(exc)) from exc
                log.warning("Gemini model %s failed (%s); trying next model", model, exc.code)
            except httpx.TransportError as exc:
                raise BrainError("Can't reach Gemini. Check the internet connection.") from exc

        log.info("Reply done in %.2f s (%d chars)", time.perf_counter() - started, len(answer))
        if answer:
            self._history = contents + [{"role": "model", "parts": [{"text": answer}]}]
            self._last_turn = time.monotonic()


def _error_reason(exc: errors.APIError) -> str:
    message = str(exc).lower()
    if isinstance(exc, errors.ServerError):
        return "Gemini is overloaded right now. Try again shortly."
    if exc.code == 429:
        return "Gemini free limit reached. Try again in a minute."
    if "api key" in message or exc.code in (401, 403):
        return "Gemini API key was rejected. Check GEMINI_API_KEY in .env."
    if exc.code == 404:
        return "Gemini model not available. Check GEMINI_MODEL in .env."
    return f"Gemini request failed ({exc.code})."
