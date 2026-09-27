"""Instant voice commands handled without the LLM, for ~1 s answers instead of ~9 s.

Two kinds. `_COMMANDS` are fixed phrases that always run the same tool. `_SMART` commands read
something out of the phrase (which app to open) or answer from the machine itself (the time), and
may decline: returning None sends the request on to the LLM, which is what should happen when
"open my emails" turns out not to be an installed app.
"""
from __future__ import annotations

import re
from datetime import datetime
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
    # Locking says nothing at all: the screen is about to go, and JARVIS rests with it.
    (re.compile(r"^lock( (my|the))?( pc| laptop| computer| screen| system)?$"), "lock_pc", {}, ""),
]
_FILLER = re.compile(r"\b(jarvis|hey|please|can you|could you|just|okay|ok)\b")
# "JAS" is stripped only when it opens the sentence, and never in front of a word like "music":
# the transcriber writes it as Jazz or Jass as often as JAS, and "play jazz music" must survive.
_ADDRESSED = re.compile(r"^(?:hey |ok |okay )?(?:jas|jass|jazz|jaz)\b[,.!]?\s+"
                        r"(?!music|song|songs|playlist|radio|track|album)", re.I)
VOLUME_STEPS = 5  # each volume key press is ~2%


def _open_app(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str | None:
    result = run_tool("open_application", {"name": said["name"]})
    if not result.get("ok"):
        return None  # not an installed app — the LLM can work out what they meant (a site, a file)
    return f"Opening {result.get('app') or said['name']}."


def _switch_to(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str | None:
    result = run_tool("focus_window", {"name": said["name"]})
    if not result.get("ok"):
        return None
    return f"Here's {result.get('window') or said['name']}."


def _screenshot(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str | None:
    result = run_tool("take_screenshot", {})
    return "Saved to your Pictures folder." if result.get("ok") else None


def _excel_fit(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str | None:
    """"Compact column A" is one call; going through the LLM for it costs ten extra seconds."""
    column = (said.groupdict().get("col") or "").upper()
    result = run_tool("excel_autofit", {"columns": column})
    if not result.get("ok"):
        return f"Sorry, {result.get('error', 'that did not work')}"
    return f"Done, column {column} fits now." if column else "Done, the columns fit now."


def _excel_save(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str | None:
    result = run_tool("excel_save", {})
    if not result.get("ok"):
        return None  # not an Excel thing after all — let the LLM read "save it" in context
    return "Saved."


def _time(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str:
    return f"It's {datetime.now().strftime('%I:%M %p').lstrip('0')}."


def _date(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str:
    now = datetime.now()
    suffix = "th" if 11 <= now.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(now.day % 10, "th")
    return f"It's {now:%A}, the {now.day}{suffix} of {now:%B}."


def _battery(said: re.Match, run_tool: Callable[[str, dict], dict]) -> str | None:
    import psutil

    level = psutil.sensors_battery()
    if level is None:
        return None  # a desktop, or the driver won't say
    if level.power_plugged:
        return f"{round(level.percent)} percent, and charging."
    return f"{round(level.percent)} percent left."


# (pattern on the normalised utterance, handler). The handler may return None to pass to the LLM.
_SMART: list[tuple[re.Pattern, Callable[[re.Match, Callable[[str, dict], dict]], str | None]]] = [
    (re.compile(r"^open (?:the |my )?(?P<name>.+)$"), _open_app),
    (re.compile(r"^(?:switch|go|change) to (?:the |my )?(?P<name>.+)$"), _switch_to),
    (re.compile(r"^(?:take (a )?)?screenshot$"), _screenshot),
    # "what's" survives normalising as "what s", but the transcriber also writes "whats"
    (re.compile(r"^what(?: s|s| is)? the time$|^what time is it( now)?$|^tell me the time$|^the time$"), _time),
    (re.compile(r"^what(?: s|s| is)? (?:the |today s )?date$|^what date is it$|"
                r"^what day is it( today)?$"), _date),
    (re.compile(r"^(?:what(?: s|s| is)? )?(?:the )?battery( level| percentage| status)?$|"
                r"^how much battery( is left| do i have)?$"), _battery),
    (re.compile(r"^thank you( so much| very much)?$|^thanks( a lot)?$|^thank u$"), lambda m, run: "Anytime."),
    # Excel jobs that are one call and need no thinking.
    (re.compile(r"^(?:compact|fit|widen|autofit|auto fit|resize)\s+(?:the\s+)?column\s+(?P<col>[a-z])$"),
     _excel_fit),
    (re.compile(r"^(?:compact|fit|widen|autofit|auto fit|resize)\s+(?:all\s+)?(?:the\s+)?columns$"),
     _excel_fit),
    (re.compile(r"^save (?:the |this )?(?:file|sheet|workbook|excel)$"), _excel_save),
]


def normalise(text: str) -> str:
    text = _ADDRESSED.sub("", text.strip())  # "JAS, lock my pc" -> "lock my pc"
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
    said = normalise(text)
    found = match(text)
    if found is None and said == "stop":  # bare "stop" pauses music if any is playing
        if run_tool("now_playing", {}).get("playing"):
            found = ("media_control", {"action": "pause"}, "Paused.")
    if found is None:
        for pattern, handler in _SMART:
            if hit := pattern.match(said):
                return handler(hit, run_tool)
        return None
    tool, args, reply = found
    result = {}
    for _ in range(VOLUME_STEPS if args.get("keys") in ("volumeup", "volumedown") else 1):
        result = run_tool(tool, args)
        if not result.get("ok"):
            return f"Sorry, {result.get('error', 'that did not work')}"
    return reply.format(title=result.get("title") or "the next track")
