import pytest

from app.voice import quick


@pytest.mark.parametrize("said, tool, args", [
    ("Stop the song.", "media_control", {"action": "pause"}),
    ("Jarvis, pause the music", "media_control", {"action": "pause"}),
    ("Resume", "media_control", {"action": "resume"}),
    ("Play it again", "media_control", {"action": "resume"}),
    ("Next song please", "media_control", {"action": "next"}),
    ("Skip", "media_control", {"action": "next"}),
    ("Previous track", "media_control", {"action": "previous"}),
    ("Turn the volume up", "press_keys", {"keys": "volumeup"}),
    ("Quieter", "press_keys", {"keys": "volumedown"}),
    ("Mute", "press_keys", {"keys": "volumemute"}),
])
def test_instant_commands_are_recognised(said, tool, args):
    assert quick.match(said)[:2] == (tool, args)


@pytest.mark.parametrize("said", ["Play Sahiba", "What's the weather", "Pause the video and open Notepad",
                                  "Next, open Chrome", "stop"])
def test_other_requests_go_to_the_llm(said):
    assert quick.match(said) is None


def test_bare_stop_pauses_only_when_something_plays():
    calls = []

    def run_tool(name, args, playing=True):
        calls.append(name)
        return {"ok": True, "playing": playing}

    assert quick.run("stop", run_tool) == "Paused."
    assert calls == ["now_playing", "media_control"]
    assert quick.run("stop", lambda n, a: {"ok": True, "playing": False}) is None  # -> treated as "cancel"


def test_volume_moves_in_several_steps_and_failures_are_spoken():
    calls = []
    quick.run("volume up", lambda n, a: calls.append(a) or {"ok": True})
    assert len(calls) == quick.VOLUME_STEPS
    assert quick.run("next", lambda n, a: {"ok": False, "error": "Nothing is playing right now."}) \
        == "Sorry, Nothing is playing right now."
