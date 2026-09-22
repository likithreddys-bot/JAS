"""Conversational brain backed by Google Gemini (free tier via AI Studio API key).

Streams the reply as text deltas so speech can start on the first sentence. With a
ToolExecutor it runs a function-calling loop: model → tool calls → results → model …
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

import httpx
from google import genai
from google.genai import errors, types

from app.brain.base import IDLE_RESET_SECONDS, MAX_TURNS, BrainError, system_prompt
from app.tools.executor import ToolExecutor

log = logging.getLogger("jarvis.agent")

MAX_TOOL_STEPS = 8
TOO_MANY_STEPS = "Sorry, that needed more steps than I'm allowed, so I stopped."

# Try the next model when one is overloaded (503), rate-limited (429) or retired (404).
_RETRY_NEXT_MODEL = {404, 429, 500, 503}


class GeminiBrain:
    def __init__(self, api_key: str, models: str, executor: ToolExecutor | None = None) -> None:
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
        self._executor = executor
        self._tools = None
        if executor:
            self._tools = [types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
                for t in executor.tools
            ])]
        self._history: list[types.Content] = []
        self._last_turn = 0.0

    def reply(self, text: str) -> Iterator[str]:
        """Stream Gemini's answer to `text` as text deltas, running any tools it calls."""
        if time.monotonic() - self._last_turn > IDLE_RESET_SECONDS or len(self._history) >= 3 * MAX_TURNS:
            self._history = []
        contents = self._history + [types.Content(role="user", parts=[types.Part.from_text(text=text)])]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt(with_tools=self._executor is not None),
            tools=self._tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        started = time.perf_counter()
        for step in range(MAX_TOOL_STEPS + 1):
            parts = yield from self._stream_turn(contents, config, started)
            contents = contents + [types.Content(role="model", parts=parts)]
            calls = [p.function_call for p in parts if p.function_call]
            if not calls:
                break
            if step == MAX_TOOL_STEPS:
                yield TOO_MANY_STEPS
                break
            results = [
                types.Part(function_response=types.FunctionResponse(
                    id=call.id, name=call.name, response=self._executor.run(call.name, call.args)))
                for call in calls
            ]
            contents = contents + [types.Content(role="user", parts=results)]

        log.info("Reply done in %.2f s", time.perf_counter() - started)
        self._history = contents
        self._last_turn = time.monotonic()

    def _stream_turn(self, contents, config, started) -> Iterator[str]:
        """One model call. Yields text; returns all response parts (text, tool calls, signatures)."""
        for index, model in enumerate(self._models):
            parts: list[types.Part] = []
            try:
                for chunk in self._client.models.generate_content_stream(
                    model=model, contents=contents, config=config
                ):
                    candidate = chunk.candidates[0] if chunk.candidates else None
                    for part in (candidate.content.parts or []) if candidate and candidate.content else []:
                        parts.append(part)
                        if part.text and not part.thought:
                            if not any(p.text for p in parts[:-1]):
                                log.info("First text from %s after %.2f s", model, time.perf_counter() - started)
                            yield part.text
                        if part.function_call:
                            log.info("%s requested %s(%s)", model, part.function_call.name, part.function_call.args)
                return parts
            except errors.APIError as exc:
                # Only switch models if this call produced nothing; otherwise the reply would repeat.
                if parts or index == len(self._models) - 1 or exc.code not in _RETRY_NEXT_MODEL:
                    raise BrainError(_error_reason(exc)) from exc
                log.warning("Gemini model %s failed (%s); trying next model", model, exc.code)
            except httpx.TransportError as exc:
                raise BrainError("Can't reach Gemini. Check the internet connection.") from exc
        return []


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
