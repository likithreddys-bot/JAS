"""The Kokoro voice, its moods, and the fall back to Piper. Kokoro itself is faked: these tests
check what is asked of it, not the model (that was measured by hand, see kokoro_speaker.py)."""
import sys
import types

import numpy as np
import pytest

from app.voice.tts.moods import MOODS, style


class FakeKokoro:
    calls: list = []

    def __init__(self, model, voices):
        pass

    def get_voices(self):
        return ["am_puck", "af_heart"]

    def create(self, text, voice, speed, lang):
        FakeKokoro.calls.append((text, voice, round(speed, 3)))
        return np.full(2400, 0.5, dtype=np.float32), 24000


@pytest.fixture
def kokoro(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "kokoro_onnx", types.SimpleNamespace(Kokoro=FakeKokoro))
    for name in ("kokoro-v1.0.fp16.onnx", "voices-v1.0.bin"):
        (tmp_path / name).write_bytes(b"x")
    FakeKokoro.calls = []
    from app.voice.tts.kokoro_speaker import KokoroSpeaker

    return KokoroSpeaker("am_puck", tmp_path, speed=1.0)


def test_moods_change_pace_and_level():
    assert style("greeting")[0] > style("reply")[0] > style("confirming")[0]
    assert style("done")[0] > 1 and style("error")[1] < 1
    assert style("no-such-mood") == MOODS["reply"]


def test_kokoro_speaks_each_mood_at_its_own_pace(kokoro):
    kokoro._synth("Yes?", "greeting")
    kokoro._synth("Send it?", "confirming")
    assert FakeKokoro.calls == [("Yes?", "am_puck", 1.1), ("Send it?", "am_puck", 0.93)]


def test_kokoro_audio_is_levelled_to_the_moods_gain(kokoro):
    loud = kokoro._synth("Done!", "done")
    quiet = kokoro._synth("That failed.", "error")
    assert loud.dtype == np.int16
    assert abs(int(quiet.max()) / int(loud.max()) - style("error")[1] / style("done")[1]) < 0.01


def test_prepared_phrases_are_not_synthesised_again(kokoro):
    kokoro.prepare(("Yes?", "greeting"), "Okay, stopped.")
    n = len(FakeKokoro.calls)
    kokoro._synth("Yes?", "greeting")
    kokoro._synth("Okay, stopped.", "reply")
    assert len(FakeKokoro.calls) == n


def test_render_is_a_wav_for_the_phone(kokoro):
    wav = kokoro.render("Hello", "greeting")
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"


def test_an_unknown_voice_is_refused(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "kokoro_onnx", types.SimpleNamespace(Kokoro=FakeKokoro))
    for name in ("kokoro-v1.0.fp16.onnx", "voices-v1.0.bin"):
        (tmp_path / name).write_bytes(b"x")
    from app.voice.tts.kokoro_speaker import KokoroSpeaker

    with pytest.raises(ValueError):
        KokoroSpeaker("not_a_voice", tmp_path)


def test_falls_back_to_piper_when_kokoro_cannot_load(monkeypatch, tmp_path):
    import app.voice.tts.speaker as piper_mod
    from app.voice.tts import make_speaker

    def broken(*a, **k):
        raise RuntimeError("model download failed")

    monkeypatch.setattr("app.voice.tts.kokoro_speaker.KokoroSpeaker", broken)

    class FakePiper:
        def __init__(self, voice, *a, **k):
            self.voice = voice

    monkeypatch.setattr(piper_mod, "Speaker", FakePiper)
    settings = types.SimpleNamespace(tts_engine="kokoro", kokoro_voice="am_puck", kokoro_voice_higher="",
                                     models_dir=tmp_path, tts_speed=1.0, tts_voice="en_GB-alan-medium",
                                     tts_voice_higher="")
    speaker = make_speaker(settings)
    assert isinstance(speaker, FakePiper) and speaker.voice == "en_GB-alan-medium"
