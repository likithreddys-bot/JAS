"""System media controls (the same ones the keyboard media keys drive).

Works for whatever is playing — the user's Chrome (YouTube Music), Spotify, Media Player —
and lets JARVIS verify playback instead of assuming it.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from difflib import SequenceMatcher

PLAYING, PAUSED = 4, 5  # GlobalSystemMediaTransportControlsSessionPlaybackStatus


@dataclass(frozen=True)
class NowPlaying:
    app: str
    title: str
    artist: str
    playing: bool


def now_playing() -> NowPlaying | None:
    return asyncio.run(_now_playing())


def control(action: str) -> NowPlaying:
    """pause / resume / next / previous on the current media session; returns the resulting state."""
    return asyncio.run(_control(action))


def wait_until_playing(expected_title: str, app_hint: str = "chrome", timeout: float = 15.0) -> NowPlaying | None:
    """Wait for `app_hint` to report playback, preferring a session whose title matches."""
    return asyncio.run(_wait_until_playing(expected_title, app_hint, timeout))


def titles_match(expected: str, actual: str) -> bool:
    a, b = expected.lower().strip(), actual.lower().strip()
    return bool(a and b) and (a in b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.75)


async def _session_state(session) -> NowPlaying:
    props = await session.try_get_media_properties_async()
    status = session.get_playback_info().playback_status
    return NowPlaying(session.source_app_user_model_id, props.title or "", props.artist or "", int(status) == PLAYING)


async def _manager():
    # Imported lazily: loading WinRT before Qt in the same process crashes Python (COM apartment clash).
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager

    return await Manager.request_async()


async def _now_playing() -> NowPlaying | None:
    manager = await _manager()
    session = manager.get_current_session()
    return await _session_state(session) if session else None


async def _control(action: str) -> NowPlaying:
    manager = await _manager()
    session = manager.get_current_session()
    if session is None:
        raise RuntimeError("Nothing is playing right now.")
    before = await _session_state(session)
    command = {
        "pause": session.try_pause_async,
        "resume": session.try_play_async,
        "next": session.try_skip_next_async,
        "previous": session.try_skip_previous_async,
    }[action]
    if not await command():
        raise RuntimeError(f"{before.app} didn't accept {action}.")
    for _ in range(20):  # confirm the player actually changed
        await asyncio.sleep(0.25)
        after = await _session_state(session)
        if action == "pause" and not after.playing:
            return after
        if action == "resume" and after.playing:
            return after
        if action in ("next", "previous") and after.title and after.title != before.title:
            return after
    raise RuntimeError(f"Asked {before.app} to {action}, but nothing changed.")


async def _wait_until_playing(expected_title: str, app_hint: str, timeout: float) -> NowPlaying | None:
    manager = await _manager()
    fallback = None
    for _ in range(int(timeout / 0.5)):
        await asyncio.sleep(0.5)
        for session in manager.get_sessions():
            state = await _session_state(session)
            if app_hint.lower() not in state.app.lower() or not state.playing:
                continue
            if titles_match(expected_title, state.title):
                return state
            fallback = state  # playing, but a different title (e.g. an ad) — keep waiting a little
    return fallback
