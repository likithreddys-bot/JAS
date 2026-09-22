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


class _Chunk:
    def __init__(self, text):
        self.text = text


def _brain_with(streams):
    """GeminiBrain whose API returns `streams[model]`: a list of texts, or an exception to raise."""
    brain = GeminiBrain("test-key", "busy-model, good-model")
    calls = []

    def generate_content_stream(model, contents, config):
        calls.append(model)
        result = streams[model]
        if isinstance(result, Exception):
            raise result
        return (_Chunk(t) for t in result)

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
    assert [c["role"] for c in brain._history] == ["user", "model", "user", "model"]
