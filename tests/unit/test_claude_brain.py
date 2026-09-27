"""The Claude brain: streaming, the tool-use loop, prompt caching and honest errors.

The Anthropic client is faked, so these run without an API key or a network.
"""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.brain.base import BrainError
from app.brain.claude import MAX_TOOL_STEPS, TOO_MANY_STEPS, ClaudeBrain
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.tools.base import Tool, ToolResult
from app.tools.executor import ToolExecutor


def text_block(t):
    return SimpleNamespace(type="text", text=t)


def tool_block(call_id, name, args):
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=args)


class FakeStream:
    """Replays one turn: text is streamed, then get_final_message() returns the blocks."""

    def __init__(self, blocks):
        self._blocks = blocks

    def __iter__(self):
        for block in self._blocks:
            if block.type == "text":
                yield SimpleNamespace(type="text", text=block.text)

    def get_final_message(self):
        return SimpleNamespace(content=self._blocks,
                               usage=SimpleNamespace(input_tokens=100, output_tokens=10,
                                                     cache_read_input_tokens=90))


def brain_with(turns, executor=None, error=None):
    """A ClaudeBrain whose API replays `turns` (a list of block-lists), recording each request."""
    brain = ClaudeBrain("test-key", "claude-haiku-4-5-20251001", executor)
    sent = []
    remaining = list(turns)

    @contextmanager
    def stream(**kwargs):
        sent.append(kwargs)
        if error:
            raise error
        yield FakeStream(remaining.pop(0))

    brain._client = SimpleNamespace(messages=SimpleNamespace(stream=stream))
    return brain, sent


def ready_executor(tool):
    core = Jarvis()
    core.start()
    for state in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING):
        core.state.transition(state)
    return ToolExecutor(core, [tool])


def test_missing_api_key_is_a_clear_error():
    with pytest.raises(BrainError, match="CLAUDE_API_KEY"):
        ClaudeBrain("", "claude-haiku-4-5-20251001")


def test_plain_reply_is_streamed():
    brain, sent = brain_with([[text_block("It is "), text_block("half past four.")]])
    assert "".join(brain.reply("what's the time")) == "It is half past four."
    assert [m["role"] for m in brain._messages] == ["user", "assistant"]


def test_tool_loop_runs_the_tool_and_speaks_the_result():
    opened = []
    tool = Tool("open_application", "Open an app",
                {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                lambda name: opened.append(name) or ToolResult(True, {"app": "Notepad"}),
                lambda name: f"Opening {name}")
    executor = ready_executor(tool)
    brain, sent = brain_with([
        [tool_block("c1", "open_application", {"name": "notepad"})],
        [text_block("Done, Notepad is open.")],
    ], executor)

    assert "".join(brain.reply("open notepad")) == "Done, Notepad is open."
    assert opened == ["notepad"]
    assert [m["role"] for m in brain._messages] == ["user", "assistant", "user", "assistant"]

    result = brain._messages[2]["content"][0]
    assert result["tool_use_id"] == "c1"
    assert json.loads(result["content"]) == {"ok": True, "app": "Notepad"}


def test_the_tools_and_system_prompt_are_cached():
    """The same ~5,500 tokens ride on every request; a cache read costs a tenth of normal input."""
    tool = Tool("open_application", "Open an app", {"type": "object", "properties": {}},
                lambda: ToolResult(True, {}), lambda: "Opening")
    brain, sent = brain_with([[text_block("Hello.")]], ready_executor(tool))
    list(brain.reply("hi"))

    request = sent[0]
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert request["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert request["tools"][0]["name"] == "open_application"


def test_it_stops_after_too_many_tool_steps():
    tool = Tool("look", "Look", {"type": "object", "properties": {}},
                lambda: ToolResult(True, {"seen": "nothing"}), lambda: "Looking")
    executor = ready_executor(tool)
    forever = [[tool_block(f"c{i}", "look", {})] for i in range(MAX_TOOL_STEPS + 1)]
    brain, sent = brain_with(forever, executor)
    assert TOO_MANY_STEPS in "".join(brain.reply("keep looking"))


def test_api_failures_become_readable_reasons():
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    cases = [
        (anthropic.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None),
         "CLAUDE_API_KEY"),
        (anthropic.NotFoundError("no model", response=httpx.Response(404, request=request), body=None),
         "CLAUDE_MODEL"),
        (anthropic.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None),
         "rate limit"),
        (anthropic.APIConnectionError(request=request), "internet connection"),
    ]
    for error, expected in cases:
        brain, _ = brain_with([[text_block("x")]], error=error)
        with pytest.raises(BrainError, match=expected):
            list(brain.reply("hi"))


def test_factory_builds_a_claude_brain_with_tools():
    from app.brain.factory import create_responder
    from app.config.settings import Settings

    settings = Settings(_env_file=None)
    settings.llm_provider = "claude"
    settings.claude_api_key = "test-key"
    tool = Tool("look", "Look", {"type": "object", "properties": {}}, lambda: ToolResult(True, {}), lambda: "Looking")
    reply = create_responder(settings, ready_executor(tool))
    brain = reply.__self__
    assert brain.__class__ is ClaudeBrain
    assert [t["name"] for t in brain._tools] == ["look"], "the tools must reach Claude"
