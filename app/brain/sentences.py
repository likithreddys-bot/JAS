"""Turn a stream of text deltas into speakable sentences."""
from __future__ import annotations

import re
from typing import Iterable, Iterator

MIN_SENTENCE_CHARS = 20  # merge very short fragments ("Sure.") with what follows
_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")
_MARKUP = re.compile(r"[*_#`>]+")


def sentences(deltas: Iterable[str]) -> Iterator[str]:
    buffer = ""
    for delta in deltas:
        buffer += delta
        while True:
            match = _find_boundary(buffer)
            if match is None:
                break
            sentence, buffer = buffer[: match.start()], buffer[match.end() :]
            if cleaned := _clean(sentence):
                yield cleaned
    if cleaned := _clean(buffer):
        yield cleaned


def _find_boundary(text: str) -> re.Match | None:
    for match in _BOUNDARY.finditer(text):
        if match.start() >= MIN_SENTENCE_CHARS:
            return match
    return None


def _clean(text: str) -> str:
    return " ".join(_MARKUP.sub("", text).split())
