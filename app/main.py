"""Application entry point: wires settings, logging, core, voice, UI and tray together."""
from __future__ import annotations

import contextlib
import logging
import sys
import threading
import time
from datetime import date
from typing import Callable

from PySide6.QtCore import QLockFile, QMetaObject, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from app.brain.base import BrainError
from app.brain.factory import create_responder
from app.brain.vision import GeminiVision
from app.config.logging_setup import setup_logging
from app.config.settings import PROJECT_ROOT, Settings, get_settings
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState
from app.google.auth import load_credentials
from app.lockart import set_lock_screen, set_wallpaper
from app.lockscreen import LockWatcher
from app.memory.store import MemoryStore
from app.routines.briefing import build_briefing
from app.tools.assistant import assistant_tools
from app.tools.google_tools import GoogleServices, google_tools
from app.tools.memory_tools import memory_tools
from app.notifications import notify
from app.reminders import ReminderService
from app.beacon import Beacon
from app.remote import RemoteControl, pin_for
from app.wellbeing import ActivityMonitor
from app.tools.browser import browser_tools
from app.tools.browser.session import BrowserSession
from app.tools.computer import computer_tools
from app.tools.computer import session
from app.tools.computer.apps import AppIndex
from app.tools.excel import excel_tools
from app.tools.executor import ToolExecutor
from app.tools.files import FileAccess, file_tools, vscode_folders
from app.tools.screen import screen_tools
from app.voice import quick
from app.voice.audio.microphone import Microphone
from app.voice.bargein import BargeIn
from app.voice.ducking import AudioDucker
from app.voice.listen.recorder import UtteranceRecorder
from app.voice.pipeline import (
    ACK_PHRASE,
    NOT_UNDERSTOOD,
    STOPPED_PHRASE,
    WORKING_PHRASE,
    VoicePipeline,
    echo_reply,
)
from app.voice.stt import make_transcriber
from app.voice.tts.speaker import Speaker
from app.voice.wake_word.detector import load_openwakeword, load_porcupine
from app.voice.wake_word.service import WakeWordService
from ui import hotkey
from ui.activity import ActivityLog
from ui.bridge import UiBridge
from ui.dashboard import DashboardBridge
from ui.screenglow import ScreenGlow
from ui.single_instance import InstanceServer, notify_running_instance
from ui.tray import Tray

log = logging.getLogger("jarvis")

ORB_QML = PROJECT_ROOT / "ui" / "qml" / "Orb.qml"
DASHBOARD_QML = PROJECT_ROOT / "ui" / "qml" / "Dashboard.qml"
SCREEN_GLOW_QML = PROJECT_ROOT / "ui" / "qml" / "ScreenGlow.qml"


def _wav_to_audio(wav: bytes):
    """The phone sends 16 kHz mono WAV, which is exactly what Whisper wants."""
    import io
    import wave

    import numpy as np

    with wave.open(io.BytesIO(wav), "rb") as clip:
        frames = clip.readframes(clip.getnframes())
    return np.frombuffer(frames, dtype=np.int16)


def _show_face(settings: Settings, mood: str) -> bool:
    """JAS's face on both the lock screen and the desktop, so its mood follows you either way."""
    where = settings.data_dir / "lockscreen"
    locked = set_lock_screen(mood, where, settings.user_name, settings.assistant_name)
    paper = set_wallpaper(mood, where, settings.user_name, settings.assistant_name)
    return locked or paper


def start_voice(core: Jarvis, settings: Settings, services: list[WakeWordService],
                memory: MemoryStore, google: GoogleServices, executor_holder: dict,
                hide_ui: "Callable[[], contextlib.AbstractContextManager] | None" = None) -> None:
    """Runs off the UI thread: loading the model takes a moment. The orb shows STARTING meanwhile."""
    if not settings.wake_word_enabled:
        core.start()
        return
    wake_problem = None
    if settings.wake_word_engine.strip().lower() == "porcupine":
        try:
            detector = load_porcupine(
                settings.picovoice_access_key, settings.porcupine_keyword, settings.porcupine_sensitivity
            )
        except Exception as exc:
            log.warning("Porcupine unavailable (%s); falling back to the openWakeWord model", exc)
            wake_problem = f"{exc}. Listening for \"Jarvis\" instead."
    try:
        if settings.wake_word_engine.strip().lower() != "porcupine" or wake_problem:
            detector = load_openwakeword(settings.wake_word_model, settings.wake_word_threshold,
                                         settings.models_dir / "openwakeword")
        speaker = Speaker(settings.tts_voice, settings.models_dir / "piper", settings.tts_speed,
                          settings.tts_voice_higher)
        speaker.prepare(ACK_PHRASE, NOT_UNDERSTOOD, STOPPED_PHRASE, WORKING_PHRASE)
    except Exception as exc:
        log.exception("Voice failed to load")
        core.start()
        core.state.transition(JarvisState.ERROR, f"Voice unavailable: {exc}")
        return

    from openwakeword.vad import VAD

    vad = VAD()
    recorder = UtteranceRecorder(
        speech_prob=lambda frame: float(vad.predict(frame, frame_size=640)),
        reset_vad=vad.reset_states,
        end_silence=settings.listen_end_silence,
        start_timeout=settings.listen_start_timeout,
        max_duration=settings.listen_max_seconds,
    )
    transcriber = make_transcriber(settings.stt_backend, settings.stt_device, settings.stt_model,
                                   settings.models_dir, settings.stt_language)

    def refresh_vocabulary() -> None:  # configured words + words JARVIS learned from the user
        transcriber.set_vocabulary(", ".join(filter(None, [settings.stt_vocabulary, *memory.words()])))

    refresh_vocabulary()
    app_index = AppIndex()
    threading.Thread(target=app_index.refresh, name="app-index", daemon=True).start()
    browser = BrowserSession(settings.browser_profile_dir)
    files = FileAccess(settings.files_root, settings.data_dir / "backups", settings.data_dir / "notes")
    tools = (computer_tools(app_index) + browser_tools(browser, settings.chrome_profile) + file_tools(files)
             + memory_tools(memory, settings.home_city, refresh_vocabulary) + assistant_tools(core)
             + excel_tools(settings.data_dir / "backups", files.resolve))
    tools += google_tools(google)
    if settings.gemini_api_key:
        vision = GeminiVision(settings.gemini_api_key, settings.gemini_model)
        tools += screen_tools(vision.ask, vision.locate, hide_ui)
    executor = ToolExecutor(core, tools)
    executor_holder["executor"] = executor
    # Learner (app/learning.py) used to record the text of every request plus each tool's outcome,
    # with no consent, to learn from repeated failures. The user's rule is explicit: nothing is
    # remembered without permission - not wired up here any more. The module itself is left in
    # place, unused, rather than deleted, in case standing consent for it is asked for later.

    try:
        respond = create_responder(settings, executor, memory.context)
    except BrainError as exc:
        log.warning("%s Falling back to echo replies.", exc)
        respond = echo_reply
    def morning_briefing() -> tuple[str, bool]:
        """The full briefing once a day. Waking from rest again later is just a greeting."""
        today = date.today().isoformat()
        if memory.note("last_briefing") == today:
            return f"Welcome back, {settings.user_name}.", False
        memory.set_note("last_briefing", today)
        return build_briefing(
            settings.user_name, settings.home_city, memory, lambda: list(vscode_folders()),
            meetings=(lambda: [f"{m['title']} at {m['start'][11:16]}"
                               for m in executor.run("list_meetings", {"day": "today"}).get("meetings", [])])
            if google.connected else None,
        ), True

    def start_the_day() -> str:
        played = executor.run("play_music", {"query": settings.morning_music, "service": "youtube",
                                             "pick": date.today().toordinal()})  # a different video each day
        return f"Enjoy your day, {settings.user_name}." if played.get("ok") else ""

    pipeline = VoicePipeline(
        core, speaker, transcriber, recorder, respond=respond,
        quick=lambda text: quick.run(text, executor.run), follow_up_seconds=settings.follow_up_seconds,
        max_listen_seconds=settings.listen_max_seconds,
        match_voice=settings.voice_matches_speaker,
        on_exchange=memory.log_exchange,
        briefing=morning_briefing,
        after_briefing=start_the_day,
    )
    # Saying "stop" while JAS is answering must actually stop it. Its own second recorder, so it
    # never competes with the one capturing the user's request.
    barge_vad = VAD()  # Silero VAD carries state; sharing one with the main recorder corrupts both
    barge_in = BargeIn(core, transcriber, UtteranceRecorder(
        speech_prob=lambda frame: float(barge_vad.predict(frame, frame_size=640)),
        reset_vad=barge_vad.reset_states,
        end_silence=0.6, start_timeout=0.8, max_duration=4.0,
    ))
    if settings.remote_enabled:
        remote = RemoteControl(core, pin_for(memory), settings.remote_port,
                               settings.assistant_name, render=speaker.render,
                               transcribe=lambda wav: transcriber.transcribe(_wav_to_audio(wav)),
                               backlog=lambda: transcriber.backlog,
                               certificates=settings.data_dir / "certificates")
        remote.start()
        # So the phone finds this laptop after the router changes its address.
        Beacon(settings.remote_port).start()
        log.info("Phone remote: open %s and enter PIN %s", remote.address, pin_for(memory))
    AudioDucker(core.bus)
    LockWatcher(
        core, session.is_locked, f"Hey {settings.user_name}, I'm ready.",
        bad_passwords=session.bad_password_count,
        set_lock_face=lambda mood: _show_face(settings, mood),
    )
    executor.set_confirmer(pipeline.ask_yes_no)

    device = settings.microphone_device or None
    if device is not None and device.isdigit():
        device = int(device)
    core.start(resting=settings.start_resting)
    ActivityMonitor(core, settings.user_name, settings.break_reminder_minutes).start()
    ReminderService(core, memory, settings.user_name, notify).start()
    if wake_problem:  # show why the wake word differs from what was configured, then carry on
        core.state.transition(JarvisState.ERROR, wake_problem)
        timer = threading.Timer(8.0, core.state.transition_from, (JarvisState.ERROR, JarvisState.STANDBY))
        timer.daemon = True
        timer.start()
    service = WakeWordService(
        core.bus, Microphone(device), detector, core.state.current, listen_sink=pipeline.feed,
        busy_sink=barge_in.feed
    )
    services.append(service)
    service.start()


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_dir, settings.log_level)
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.assistant_name)
    app.setQuitOnLastWindowClosed(False)  # lives in the tray

    lock = QLockFile(str(settings.data_dir / "jarvis.lock"))
    if not lock.tryLock(100):
        shown = notify_running_instance()
        log.info("JARVIS is already running; %s", "asked it to show" if shown else "exiting")
        return 0

    core = Jarvis()
    bridge = UiBridge(core, settings.assistant_name, settings.wake_phrase)
    memory = MemoryStore(settings.data_dir / "memory.db")
    google = GoogleServices(lambda: load_credentials(settings.google_client_file, settings.google_token_file))
    activity = ActivityLog(core.bus)
    executor_holder: dict = {}

    def todays_meetings() -> list[str]:
        executor = executor_holder.get("executor")
        if executor is None:
            return []
        result = executor.run("list_meetings", {"day": "today"})
        return [f"{m['title']} at {m['start'][11:16]}" for m in result.get("meetings", [])] if result.get("ok") else []

    dashboard = DashboardBridge(core, memory, activity, settings, todays_meetings, lambda: google.connected)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("dashboard", dashboard)
    engine.load(QUrl.fromLocalFile(str(ORB_QML)))
    engine.load(QUrl.fromLocalFile(str(DASHBOARD_QML)))
    if len(engine.rootObjects()) < 2:
        log.error("Failed to load the UI from %s / %s", ORB_QML, DASHBOARD_QML)
        return 1
    window, dashboard_window = engine.rootObjects()

    tray = Tray(bridge, window, dashboard_window)
    hotkey_filter = hotkey.register(settings.hotkey, lambda: core.activate("hotkey"))  # noqa: F841
    tray.show()

    instance_server = InstanceServer()
    instance_server.showRequested.connect(tray.show_window)
    if not instance_server.listen_for_launches():
        log.warning("Could not listen for relaunches: %s", instance_server.errorString())

    services: list[WakeWordService] = []
    try:
        screen_glow = ScreenGlow(core, SCREEN_GLOW_QML)
    except Exception:  # the glow is a nicety; never let it stop JARVIS starting
        log.exception("Screen glow unavailable")
        screen_glow = None

    @contextlib.contextmanager
    def hidden_orb():
        """Hide JARVIS's own windows while the screen is captured, so it doesn't photograph itself."""
        visible = window.isVisible()
        if visible:
            QMetaObject.invokeMethod(window, "hide", Qt.QueuedConnection)
        if screen_glow:
            screen_glow.hide_for_capture(True)
        if visible or screen_glow:
            time.sleep(0.25)
        try:
            yield
        finally:
            if visible:
                QMetaObject.invokeMethod(window, "show", Qt.QueuedConnection)
            if screen_glow:
                screen_glow.hide_for_capture(False)

    def start_voice_safely() -> None:
        try:
            start_voice(core, settings, services, memory, google, executor_holder, hidden_orb)
        except Exception as exc:  # show it on the orb instead of hanging on "Starting"
            log.exception("Startup failed")
            if core.state.current is JarvisState.STARTING:
                core.state.transition(JarvisState.ERROR, f"Startup failed: {exc}")

    threading.Thread(target=start_voice_safely, name="voice-startup", daemon=True).start()

    code = app.exec()
    for service in services:
        service.stop()
    log.info("JARVIS stopped")
    return code
