import pytest

from app.brain.base import BrainError
from app.brain.claude import ClaudeBrain
from app.brain.factory import create_responder
from app.brain.gemini import GeminiBrain
from app.config.settings import Settings
from app.brain.sentences import sentences


def test_sentences_split_streamed_deltas():
    deltas = ["I'm doing well, th", "anks for asking! The weather", " today is sunny.", " Anything else?"]
    assert list(sentences(deltas)) == [
        "I'm doing well, thanks for asking!",
        "The weather today is sunny.",
        "Anything else?",
    ]


def test_short_fragments_merge_and_markdown_is_stripped():
    assert list(sentences(["Sure. ", "**Paris** is the capital of France."])) == [
        "Sure. Paris is the capital of France."
    ]


def test_newlines_split_and_blank_output_yields_nothing():
    assert list(sentences(["First line is long enough\n\nSecond line"])) == [
        "First line is long enough",
        "Second line",
    ]
    assert list(sentences(["  ", "\n"])) == []


def test_missing_api_key_is_a_clear_error():
    with pytest.raises(BrainError, match="CLAUDE_API_KEY"):
        ClaudeBrain("", "claude-opus-5")
    with pytest.raises(BrainError, match="GEMINI_API_KEY"):
        GeminiBrain("", "gemini-flash-latest")


def test_factory_picks_provider():
    reply = create_responder(Settings(_env_file=None, llm_provider="gemini", gemini_api_key="test-key"))
    assert reply.__self__.__class__ is GeminiBrain
    reply = create_responder(Settings(_env_file=None, llm_provider="Claude", claude_api_key="test-key"))
    assert reply.__self__.__class__ is ClaudeBrain
    with pytest.raises(BrainError, match="LLM_PROVIDER"):
        create_responder(Settings(_env_file=None, llm_provider="gpt"))


def _chunk(*parts):
    from google.genai import types

    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
    )


def _text(t):
    from google.genai import types

    return types.Part.from_text(text=t)


def _brain_with(streams, executor=None):
    """GeminiBrain whose API returns `streams[model]`: a list of texts/parts (or a list of such
    lists, one per call), or an exception to raise."""
    brain = GeminiBrain("test-key", "busy-model, good-model", executor)
    calls = []

    def generate_content_stream(model, contents, config):
        calls.append(model)
        result = streams[model]
        if isinstance(result, list) and result and isinstance(result[0], list):
            result = result.pop(0)
        if isinstance(result, Exception):
            raise result
        return (_chunk(p if not isinstance(p, str) else _text(p)) for p in result)

    brain._client = type("C", (), {"models": type("M", (), {"generate_content_stream": staticmethod(generate_content_stream)})})()
    return brain, calls


def test_gemini_falls_back_to_next_model_when_busy():
    from google.genai import errors

    busy = errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    brain, calls = _brain_with({"busy-model": busy, "good-model": ["Hello ", "there."]})
    assert "".join(brain.reply("hi")) == "Hello there."
    assert calls == ["busy-model", "good-model"]


def test_gemini_reports_friendly_error_when_all_models_fail():
    from google.genai import errors

    busy = errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    brain, _ = _brain_with({"busy-model": busy, "good-model": busy})
    with pytest.raises(BrainError, match="overloaded"):
        list(brain.reply("hi"))


def test_gemini_keeps_conversation_history():
    brain, _ = _brain_with({"busy-model": ["Paris."], "good-model": []})
    list(brain.reply("Capital of France?"))
    list(brain.reply("Population?"))
    assert [c.role for c in brain._history] == ["user", "model", "user", "model"]


def test_gemini_tool_loop_runs_tools_and_speaks_result():
    from google.genai import types

    from app.core.jarvis import Jarvis
    from app.tools.base import Tool, ToolResult
    from app.tools.executor import ToolExecutor

    opened = []
    tool = Tool("open_application", "Open an app", {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                lambda name: opened.append(name) or ToolResult(True, {"app": "Notepad"}), lambda name: f"Opening {name}")
    from app.core.state.states import JarvisState as S

    core = Jarvis()
    core.start()
    for state in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING):
        core.state.transition(state)
    executor = ToolExecutor(core, [tool])
    call = types.Part(function_call=types.FunctionCall(id="c1", name="open_application", args={"name": "notepad"}))
    brain, calls = _brain_with({"busy-model": [[call], ["Done, Notepad is open."]], "good-model": []}, executor)

    assert "".join(brain.reply("open notepad")) == "Done, Notepad is open."
    assert opened == ["notepad"] and calls == ["busy-model", "busy-model"]
    roles = [c.role for c in brain._history]
    assert roles == ["user", "model", "user", "model"]
    response = brain._history[2].parts[0].function_response
    assert response.id == "c1" and response.response == {"ok": True, "app": "Notepad"}


def test_gemini_stops_after_too_many_tool_steps():
    from google.genai import types

    from app.brain.gemini import MAX_TOOL_STEPS, TOO_MANY_STEPS
    from app.core.jarvis import Jarvis
    from app.tools.base import Tool, ToolResult
    from app.tools.executor import ToolExecutor

    tool = Tool("list_open_windows", "List", {"type": "object", "properties": {}}, lambda: ToolResult(True), lambda: "Listing")
    from app.core.state.states import JarvisState as S

    core = Jarvis()
    core.start()
    for state in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING):
        core.state.transition(state)
    call = types.Part(function_call=types.FunctionCall(name="list_open_windows", args={}))
    brain, _ = _brain_with({"busy-model": [[call] for _ in range(MAX_TOOL_STEPS + 1)], "good-model": []}, ToolExecutor(core, [tool]))
    assert "".join(brain.reply("loop forever")) == TOO_MANY_STEPS
