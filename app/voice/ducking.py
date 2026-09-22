"""Lower other apps' volume while JARVIS is listening or talking, then restore it.

Like a phone assistant: music keeps playing quietly, so JARVIS doesn't talk over it and can
hear the user clearly. Runs on its own thread because Windows audio (COM) calls must stay on
one thread; the event bus may call us from any thread.
"""
from __future__ import annotations

import logging
import os
import queue
import threading

from app.core.events.bus import EventBus
from app.core.events.events import StateChanged
from app.core.state.states import BUSY_STATES, JarvisState

log = logging.getLogger("jarvis.voice.ducking")

DUCK_STATES = BUSY_STATES | {JarvisState.WAKE_DETECTED, JarvisState.LISTENING}


class AudioDucker:
    def __init__(self, bus: EventBus, level: float = 0.15) -> None:
        self._level = level
        self._saved: dict[int, float] = {}  # pid -> volume before ducking
        self._requests: queue.Queue[bool] = queue.Queue()
        threading.Thread(target=self._run, name="audio-ducking", daemon=True).start()
        bus.subscribe(StateChanged, self._on_state)

    def _on_state(self, event: StateChanged) -> None:
        if event.current in DUCK_STATES:
            self._requests.put(True)  # re-scan on every step: music started by a tool gets ducked too
        elif event.previous in DUCK_STATES:
            self._requests.put(False)

    def _run(self) -> None:
        import comtypes  # COM must be initialised on the thread that uses it

        comtypes.CoInitialize()
        from pycaw.pycaw import AudioUtilities

        own_pid = os.getpid()
        while True:
            duck = self._requests.get()
            try:
                for session in AudioUtilities.GetAllSessions():
                    if not session.Process or session.ProcessId == own_pid:
                        continue
                    volume = session.SimpleAudioVolume
                    if duck:
                        current = volume.GetMasterVolume()
                        if session.ProcessId not in self._saved and current > self._level:
                            self._saved[session.ProcessId] = current
                            volume.SetMasterVolume(self._level, None)
                    elif session.ProcessId in self._saved:
                        original = self._saved.pop(session.ProcessId)
                        if abs(volume.GetMasterVolume() - self._level) < 0.02:  # user didn't change it meanwhile
                            volume.SetMasterVolume(original, None)
                if not duck:
                    self._saved.clear()  # apps that closed meanwhile
            except Exception:
                log.exception("Audio ducking failed")
