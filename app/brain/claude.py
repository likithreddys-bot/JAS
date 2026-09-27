"""Conversational brain backed by the Claude API.

Streams the reply as text deltas so speech can start on the first sentence. With a
ToolExecutor it runs a tool-use loop: model → tool calls → results → model …

Every request carries the same ~5,500 tokens of system prompt and tool schemas, so both are
marked for prompt caching: a cache read costs a tenth of normal input, which is most of the bill
for a voice assistant that says short things very often.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Iterator

import anthropic

from app.brain.base import IDLE_RESET_SECONDS, MAX_TURNS, BrainError, system_prompt
from app.tools.executor import ToolExecutor

log = logging.getLogger("jarvis.agent")

MAX_TOKENS = 2000  # spoken replies are short; tool arguments are the long part
MAX_TOOL_STEPS = 8
TOO_MANY_STEPS = "Sorry, that needed more steps than I'm allowed, so I stopped."


class ClaudeBrain:
    def __init__(
        self, api_key: str, model: str, executor: ToolExecutor | None = None,
        user_name: str = "", memory: Callable[[], str] = lambda: "", assistant_name: str = "JAS",
    ) -> None:
        if not api_key:
            raise BrainError("No Claude API key. Add CLAUDE_API_KEY to the .env file.")
        self._client = anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=1)
        self._model = model
        self._executor = executor
        self._user_name = user_name
        self._assistant_name = assistant_name
        self._memory = memory
        self._tools = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in executor.tools
        ] if executor else []
        if self._tools:  # cache everything up to and including the last tool
            self._tools[-1] = {**self._tools[-1], "cache_control": {"type": "ephemeral"}}
        self._messages: list[dict] = []
        self._last_turn = 0.0

    def reply(self, text: str) -> Iterator[str]:
        """Stream Claude's answer to `text`, running any tools it calls."""
        if time.monotonic() - self._last_turn > IDLE_RESET_SECONDS or len(self._messages) >= 3 * MAX_TURNS:
            self._messages = []  # a new conversation, rather than trimming mid-tool-call
        messages = self._messages + [{"role": "user", "content": text}]
        system = [{"type": "text",
                   "text": system_prompt(self._executor is not None, self._user_name, self._memory(),
                                         self._assistant_name),
                   "cache_control": {"type": "ephemeral"}}]
        started = time.perf_counter()

        for step in range(MAX_TOOL_STEPS + 1):
            blocks = yield from self._stream_turn(messages, system, started)
            messages = messages + [{"role": "assistant", "content": blocks}]
            calls = [b for b in blocks if b.get("type") == "tool_use"]
            if not calls:
                break
            if step == MAX_TOOL_STEPS:
                yield TOO_MANY_STEPS
                break
            messages = messages + [{"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": call["id"],
                 "content": _as_text(self._executor.run(call["name"], call["input"]))}
                for call in calls
            ]}]

        log.info("Reply done in %.2f s", time.perf_counter() - started)
        self._messages = messages
        self._last_turn = time.monotonic()

    def _stream_turn(self, messages, system, started) -> Iterator[str]:
        """One model call. Yields spoken text; returns the assistant's content blocks."""
        blocks: list[dict] = []
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
                tools=self._tools or anthropic.NOT_GIVEN,
            ) as stream:
                spoken = False
                for event in stream:
                    if event.type == "text" and not spoken:
                        log.info("First text after %.2f s", time.perf_counter() - started)
                        spoken = True
                    if event.type == "text":
                        yield event.text
                final = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise BrainError("Claude API key was rejected. Check CLAUDE_API_KEY in .env.") from exc
        except anthropic.PermissionDeniedError as exc:
            raise BrainError("This Claude API key isn't allowed to use this model.") from exc
        except anthropic.NotFoundError as exc:
            raise BrainError("Claude model not available. Check CLAUDE_MODEL in .env.") from exc
        except anthropic.RateLimitError as exc:
            raise BrainError("Claude rate limit reached. Try again in a minute.") from exc
        except anthropic.APIStatusError as exc:
            raise BrainError(f"Claude request failed ({exc.status_code}).") from exc
        except anthropic.APIConnectionError as exc:
            raise BrainError("Can't reach Claude. Check the internet connection.") from exc

        usage = final.usage
        log.info("Claude usage: %d in (%d cached), %d out",
                 usage.input_tokens, getattr(usage, "cache_read_input_tokens", 0) or 0, usage.output_tokens)
        for block in final.content:
            if block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                log.info("%s requested %s(%s)", self._model, block.name, block.input)
                blocks.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        return blocks


def _as_text(result: dict) -> str:
    """Tool results go back as text: Claude reads the same JSON the tools already return."""
    import json

    return json.dumps(result, default=str)[:20000]  # a huge file read must not blow up the context
