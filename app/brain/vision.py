"""Image understanding with Gemini (used for "what's on my screen?")."""
from __future__ import annotations

import logging
import time

import httpx
from google import genai
from google.genai import errors, types

from app.brain.base import BrainError

log = logging.getLogger("jarvis.agent")

PROMPT = """This is a screenshot of the user's Windows screen, taken because they asked about it.
First describe briefly what is visible: which apps/windows, and the main content. Transcribe
important visible text exactly (error messages, code, headings, numbers). Then answer the
user's question about the screen: {question}"""


class GeminiVision:
    def __init__(self, api_key: str, models: str) -> None:
        if not api_key:
            raise BrainError("No Gemini API key. Add GEMINI_API_KEY to the .env file.")
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1)),
        )
        self._models = [m.strip() for m in models.split(",") if m.strip()]

    def ask(self, image_jpeg: bytes, question: str) -> str:
        started = time.perf_counter()
        last_error: Exception | None = None
        for model in self._models:
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=image_jpeg, mime_type="image/jpeg"),
                              PROMPT.format(question=question)],
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                    ),
                )
                log.info("Vision answer from %s in %.1f s", model, time.perf_counter() - started)
                return response.text or ""
            except (errors.APIError, httpx.TransportError) as exc:
                log.warning("Vision model %s failed: %s", model, str(exc)[:120])
                last_error = exc
        raise BrainError("Couldn't analyse the screen right now (Gemini unavailable).") from last_error
