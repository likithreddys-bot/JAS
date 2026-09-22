"""Instant voice commands handled without the LLM (media and volume), for ~1 s responses."""
from __future__ import annotations

import re
from typing import Callable

# (pattern on the normalised utterance, tool name, tool args, spoken reply template)
_COMMANDS: list[tuple[re.Pattern, str, dict, str]] = [
    (re.compile(r"^pause( (the|this))?( song| music| it| playback| video)?$"), "media_control", {"action": "pause"}, "Paused."),
    (re.compile(r"^stop( (the|this))?( song| music| it| playback| video)$"), "media_control", {"action": "pause"}, "Paused."),
    (re.compile(r"^(resume|continue|unpause|play)( (the|it))?( song| music| it| playback)?( again)?$"), "media_control", {"action": "resume"}, "Resuming."),
    (re.compile(r"^(play )?(the )?(next|skip)( song| track| one| this)?$"), "media_control", {"action": "next"}, "Next: {title}."),
    (re.compile(r"^(play )?(the )?(previous|last)( song| track| one)?$|^go back$"), "media_control", {"action": "previous"}, "Back to {title}."),
    (re.compile(r"^(turn |increase |raise )?(the )?volume up$|^(louder|increase (the )?volume)$"), "press_keys", {"keys": "volumeup"}, "Louder."),
    (re.compile(r"^(turn |decrease |lower )?(the )?volume down$|^(quieter|softer|decrease (the )?volume)$"), "press_keys", {"keys": "volumedown"}, "Quieter."),
    (re.compile(r"^(mute|unmute)( (the )?(sound|volume|audio))?$"), "press_keys", {"keys": "volumemute"}, "Done."),
    (re.compile(r"^(go )?(offline|to sleep|to rest|rest mode|sleep mode)$|^take (a )?rest$|^(you can )?rest( now)?$"),
     "go_offline", {}, "Going offline. Say \u201cwake up, Jarvis\u201d when you need me."),
]
_FILLER = re.compile(r"\b(jarvis|hey|please|can you|could you|just|okay|ok)\b")
VOLUME_STEPS = 5  # each volume key press is ~2%


def normalise(text: str) -> str:
    text = re.sub(r"[^a-z ]", " ", text.lower())
    return " ".join(_FILLER.sub(" ", text).split())


def match(text: str) -> tuple[str, dict, str] | None:
    """(tool, args, reply template) if `text` is an instant command."""
    said = normalise(text)
    for pattern, tool, args, reply in _COMMANDS:
        if pattern.match(said):
            return tool, args, reply
    return None


def run(text: str, run_tool: Callable[[str, dict], dict]) -> str | None:
    """Execute an instant command. Returns what to say, or None if `text` isn't one."""
    found = match(text)
    if found is None and normalise(text) == "stop":  # bare "stop" pauses music if any is playing
        if run_tool("now_playing", {}).get("playing"):
            found = ("media_control", {"action": "pause"}, "Paused.")
    if found is None:
        return None
    tool, args, reply = found
    result = {}
    for _ in range(VOLUME_STEPS if args.get("keys") in ("volumeup", "volumedown") else 1):
        result = run_tool(tool, args)
        if not result.get("ok"):
            return f"Sorry, {result.get('error', 'that did not work')}"
    return reply.format(title=result.get("title") or "the next track")
