"""JAS learning from what actually happened, and letting that calibrate the next decision.

The model's weights cannot be trained here — Gemini's free tier offers no fine-tuning and the
weights are not ours. What *can* be done, and gives much of the same benefit, is a closed loop:

    act  ->  observe the outcome  ->  keep the lesson  ->  put it in the next prompt

The rewards are already there and were being thrown away. A tool returning ok=False is a negative
signal. The user saying "stop" mid-task is a stronger one — they are telling JAS, in the moment,
that what it chose was wrong. Both are recorded against the request that caused them.

Only repeated mistakes become lessons. One failure is noise; the same failure twice is a pattern
worth spending prompt tokens on.
"""
from __future__ import annotations

import logging

from app.core.events.events import StateChanged, TaskInterrupted, ToolFinished, TranscriptReady
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState
from app.memory.store import MemoryStore

log = logging.getLogger("jarvis.agent")

MIN_REPEATS = 2      # a mistake becomes a lesson the second time it happens
MAX_LESSONS = 6      # the prompt is already large; only the worst offenders earn a place
STOPPED = "the user said stop while this was running"


class Learner:
    """Records what JAS tried and how it went, and turns repeats into prompt lessons."""

    def __init__(self, core: Jarvis, memory: MemoryStore) -> None:
        self._memory = memory
        self._request = ""
        self._last_tool = ""
        core.bus.subscribe(TranscriptReady, self._on_heard)
        core.bus.subscribe(ToolFinished, self._on_tool)
        core.bus.subscribe(TaskInterrupted, self._on_interrupted)
        core.bus.subscribe(StateChanged, self._on_state)

    def _on_heard(self, event: TranscriptReady) -> None:
        self._request = event.text or ""

    def _on_tool(self, event: ToolFinished) -> None:
        if not event.tool:
            return
        self._last_tool = event.tool
        self._memory.record_outcome(event.tool, event.ok, event.error or "", self._request)

    def _on_interrupted(self, event: TaskInterrupted) -> None:
        """Being stopped is the clearest signal there is that the choice was wrong."""
        if "user" in event.reason and self._last_tool:
            self._memory.record_outcome(self._last_tool, False, STOPPED, self._request)
            log.info("Noted that %s was stopped by the user", self._last_tool)

    def _on_state(self, event: StateChanged) -> None:
        if event.current is JarvisState.STANDBY:
            self._last_tool = ""

    def lessons(self) -> str:
        """The lines that go into the system prompt. Empty until JAS has repeated a mistake."""
        return lessons_from(self._memory)


def lessons_from(memory: MemoryStore) -> str:
    repeats = memory.repeated_failures(minimum=MIN_REPEATS)[:MAX_LESSONS]
    if not repeats:
        return ""
    lines = []
    for tool, detail, times in repeats:
        if detail == STOPPED:
            lines.append(f"- {tool}: the user stopped this {times} times. Check with them before using it again.")
        else:
            lines.append(f"- {tool} failed {times} times with: {detail.strip()[:160]}")
    return ("What you have got wrong before, so you don't repeat it:\n" + "\n".join(lines))
