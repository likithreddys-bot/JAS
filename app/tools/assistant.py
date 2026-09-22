"""Tools about JARVIS itself."""
from __future__ import annotations

from app.core.jarvis import Jarvis
from app.tools.base import Tool, ToolResult


def assistant_tools(core: Jarvis) -> list[Tool]:
    def go_offline() -> ToolResult:
        core.rest_requested = True  # takes effect right after this reply is spoken
        return ToolResult(True, {"note": "JARVIS will rest after this reply; 'wake up Jarvis' wakes it with a briefing."})

    return [
        Tool("go_offline", "Go offline / rest mode when the user says 'go offline', 'go to sleep' or 'take rest'. "
             "JARVIS stays quiet until woken with the wake word.",
             {"type": "object", "properties": {}}, go_offline, lambda: "Going offline"),
    ]
