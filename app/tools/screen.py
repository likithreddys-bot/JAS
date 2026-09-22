"""Screen understanding: capture the screen on request and ask a vision model about it.

Never runs on its own: the screen is captured only when the user asks (the orb shows
"Looking at your screen" while it happens).
"""
from __future__ import annotations

import io
from typing import Callable

import mss
from PIL import Image

from app.tools.base import Tool, ToolResult

MAX_WIDTH = 1600  # enough to read text, small enough to upload quickly


def capture_screen_jpeg() -> bytes:
    with mss.mss() as screen:
        shot = screen.grab(screen.monitors[1])  # primary monitor
    image = Image.frombytes("RGB", shot.size, shot.rgb)
    if image.width > MAX_WIDTH:
        image = image.resize((MAX_WIDTH, round(image.height * MAX_WIDTH / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def screen_tools(ask_vision: Callable[[bytes, str], str]) -> list[Tool]:
    def look_at_screen(question: str = "What is on the screen?") -> ToolResult:
        try:
            answer = ask_vision(capture_screen_jpeg(), question)
        except Exception as exc:
            return ToolResult(False, error=str(exc))
        return ToolResult(True, {"screen": answer})

    return [
        Tool("look_at_screen",
             "Look at the user's screen right now and answer a question about it: what's open, read text, "
             "explain an error, describe an image or chart. Call it again for follow-up questions about the screen.",
             {"type": "object", "properties": {"question": {"type": "string", "description": "What the user wants to know"}}},
             look_at_screen, lambda question="": "\U0001f441 Looking at your screen"),
    ]
