"""Find songs (YouTube Music) and videos (YouTube) without opening a browser."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx
from ytmusicapi import YTMusic

_ytmusic = YTMusic()  # anonymous search client; no login needed to find songs
_VIDEO = re.compile(r'"videoRenderer":\{"videoId":"([\w-]{11})".*?"title":\{"runs":\[\{"text":"(.*?)"\}', re.S)


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    url: str


def find_song(query: str) -> Track | None:
    songs = _ytmusic.search(query, filter="songs", limit=3)
    if not songs:
        return None
    top = songs[0]
    artists = ", ".join(a["name"] for a in top.get("artists") or [])
    return Track(top["title"], artists, f"https://music.youtube.com/watch?v={top['videoId']}")


def find_video(query: str, pick: int = 0) -> Track | None:
    """The `pick`-th result (0 = best); larger numbers give variety, e.g. a different video each day."""
    page = httpx.get(
        "https://www.youtube.com/results",
        params={"search_query": query},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "en"},
        timeout=15,
    ).text
    matches = _VIDEO.findall(page)[:10]
    if not matches:
        return None
    video_id, title = matches[pick % len(matches)]
    title = json.loads(f'"{title}"')  # the page embeds JSON; undo its escaping
    return Track(title, "", f"https://www.youtube.com/watch?v={video_id}")


def relevant(query: str, found: str) -> bool:
    """Does the result share any meaningful word with what the user asked for?"""
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    return not words or any(w in found.lower() for w in words)
