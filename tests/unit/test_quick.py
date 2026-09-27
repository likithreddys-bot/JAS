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


# --- commands that read the phrase or answer from the machine itself -------

def test_open_app_is_instant_but_steps_aside_when_it_is_not_an_app():
    calls = []

    def installed(name, args):
        calls.append((name, args))
        return {"ok": True, "app": "Notepad", "window": "Untitled - Notepad"}

    assert quick.run("Jarvis, open notepad", installed) == "Opening Notepad."
    assert calls == [("open_application", {"name": "notepad"})]

    # "open my emails" is not an installed app: hand it to the LLM instead of apologising
    assert quick.run("open my emails", lambda n, a: {"ok": False, "error": "No installed app matches."}) is None


def test_switch_to_a_window_is_instant():
    assert quick.run("switch to chrome", lambda n, a: {"ok": True, "window": "YouTube - Google Chrome"}) \
        == "Here's YouTube - Google Chrome."
    assert quick.run("go to the calculator", lambda n, a: {"ok": False, "error": "No open window"}) is None


def test_the_time_and_date_need_no_tool_at_all():
    called = []
    answer = quick.run("what's the time", lambda n, a: called.append(n) or {})
    assert answer.startswith("It's") and answer.endswith(".") and called == []
    assert ("AM" in answer) or ("PM" in answer)

    date = quick.run("what day is it today", lambda n, a: called.append(n) or {})
    assert date.startswith("It's") and called == []


def test_battery_is_read_from_the_machine():
    answer = quick.run("how much battery", lambda n, a: {})
    assert answer is None or "percent" in answer  # None on a machine with no battery


def test_thanks_gets_a_reply_without_waking_the_llm():
    """Whisper also hallucinates 'Thank you.' on silence, so this saves a pointless LLM call."""
    assert quick.run("Thank you, Jarvis.", lambda n, a: {}) == "Anytime."
    assert quick.run("thanks", lambda n, a: {}) == "Anytime."


def test_ordinary_requests_still_go_to_the_llm():
    for said in ("what's the weather", "open the pod bay doors and then explain why",
                 "who is Sunny", "make me a deck about the project"):
        assert quick.run(said, lambda n, a: {"ok": False}) is None, said


@pytest.mark.parametrize("said, expected", [
    ("JAS, lock my pc", "lock my pc"),
    ("Jazz, open notepad", "open notepad"),          # the transcriber often hears JAS as "Jazz"
    ("Jass, take a screenshot", "take a screenshot"),
    ("Hey JAS, what is the time", "what is the time"),
    ("Jarvis, lock my pc", "lock my pc"),            # the wake word still works as an address
    ("play jazz music", "play jazz music"),          # a real request, not an address
    ("play some jazz", "play some jazz"),
])
def test_jas_is_understood_as_being_addressed(said, expected):
    assert quick.normalise(said) == expected


def test_common_excel_jobs_skip_the_llm():
    """"Compact column A" is one tool call; the LLM added ~14 s for nothing."""
    calls = []

    def run_tool(name, args):
        calls.append((name, args))
        return {"ok": True}

    assert quick.run("JAS, compact column A", run_tool) == "Done, column A fits now."
    assert quick.run("widen column b", run_tool) == "Done, column B fits now."
    assert quick.run("fit the columns", run_tool) == "Done, the columns fit now."
    assert quick.run("save the file", run_tool) == "Saved."
    assert [c[0] for c in calls] == ["excel_autofit"] * 3 + ["excel_save"]
    assert calls[0][1] == {"columns": "A"} and calls[2][1] == {"columns": ""}


def test_excel_phrases_that_are_not_excel_go_to_the_llm():
    assert quick.run("compact my notes", lambda n, a: {"ok": True}) is None
    assert quick.run("save the world", lambda n, a: {"ok": True}) is None
    # "save it" when Excel isn't open must fall through rather than apologise about Excel
    assert quick.run("save the file", lambda n, a: {"ok": False, "error": "no workbook"}) is None


def test_a_failed_autofit_is_reported_not_hidden():
    said = quick.run("compact column A", lambda n, a: {"ok": False, "error": "Excel isn't open."})
    assert said and "Excel isn't open" in said
