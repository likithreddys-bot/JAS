"""Image understanding with Gemini (used for "what's on my screen?")."""
from __future__ import annotations

import json
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


LOCATE_PROMPT = """Look at this screenshot of a Windows screen and find: {target}

Answer with JSON only:
{{"found": true/false, "point": [y, x], "label": "what you found and where it is"}}
`point` is the centre of the thing to click, as numbers 0-1000 where 0,0 is the top-left corner
and 1000,1000 the bottom-right. If several match, pick the most likely one for the user's words.
If it is not visible, answer {{"found": false, "point": [0, 0], "label": "why not"}}."""

LOCATE_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "point": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
        "label": {"type": "string"},
    },
    "required": ["found", "point", "label"],
}


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
        return self._generate(image_jpeg, PROMPT.format(question=question))

    def locate(self, image_jpeg: bytes, target: str) -> dict:
        """Where is `target` on this screen? {found, point: [y, x] in 0-1000, label}."""
        answer = self._generate(image_jpeg, LOCATE_PROMPT.format(target=target), schema=LOCATE_SCHEMA)
        try:
            found = json.loads(answer)
            y, x = found["point"]
            return {"found": bool(found["found"]), "point": (int(y), int(x)), "label": str(found["label"])}
        except (ValueError, KeyError, TypeError) as exc:
            raise BrainError("I couldn't work out where that is on the screen.") from exc

    def _generate(self, image_jpeg: bytes, prompt: str, schema: dict | None = None) -> str:
        started = time.perf_counter()
        last_error: Exception | None = None
        config = types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="LOW"))
        if schema:
            config.response_mime_type = "application/json"
            config.response_json_schema = schema
        for model in self._models:
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=image_jpeg, mime_type="image/jpeg"), prompt],
                    config=config,
                )
                log.info("Vision answer from %s in %.1f s", model, time.perf_counter() - started)
                return response.text or ""
            except (errors.APIError, httpx.TransportError) as exc:
                log.warning("Vision model %s failed: %s", model, str(exc)[:120])
                last_error = exc
        raise BrainError("Couldn't analyse the screen right now (Gemini unavailable).") from last_error
