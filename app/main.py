"""Application entry point: wires settings, logging, core, voice, UI and tray together."""
from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtCore import QLockFile, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from app.brain.base import BrainError
from app.brain.factory import create_responder
from app.config.logging_setup import setup_logging
from app.config.settings import PROJECT_ROOT, Settings, get_settings
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState
from app.tools.computer import computer_tools
from app.tools.computer.apps import AppIndex
from app.tools.executor import ToolExecutor
from app.voice.audio.microphone import Microphone
from app.voice.listen.recorder import UtteranceRecorder
from app.voice.pipeline import ACK_PHRASE, NOT_UNDERSTOOD, VoicePipeline, echo_reply
from app.voice.stt.transcriber import Transcriber
from app.voice.tts.speaker import Speaker
from app.voice.wake_word.detector import load_openwakeword, load_porcupine
from app.voice.wake_word.service import WakeWordService
from ui.bridge import UiBridge
from ui.single_instance import InstanceServer, notify_running_instance
from ui.tray import Tray

log = logging.getLogger("jarvis")

ORB_QML = PROJECT_ROOT / "ui" / "qml" / "Orb.qml"


def start_voice(core: Jarvis, settings: Settings, services: list[WakeWordService]) -> None:
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
            log.warning("Porcupine unavailable (%s); falling back to 'Hey Jarvis'", exc)
            wake_problem = f"{exc}. Using \"Hey Jarvis\" instead."
    try:
        if settings.wake_word_engine.strip().lower() != "porcupine" or wake_problem:
            detector = load_openwakeword(settings.wake_word_model, settings.wake_word_threshold)
        speaker = Speaker(settings.tts_voice, settings.models_dir / "piper", settings.tts_speed)
        speaker.prepare(ACK_PHRASE, NOT_UNDERSTOOD)
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
    )
    transcriber = Transcriber(
        settings.stt_model, settings.models_dir / "whisper", settings.stt_language, settings.stt_vocabulary
    )
    app_index = AppIndex()
    threading.Thread(target=app_index.refresh, name="app-index", daemon=True).start()
    executor = ToolExecutor(core, computer_tools(app_index))
    try:
        respond = create_responder(settings, executor)
    except BrainError as exc:
        log.warning("%s Falling back to echo replies.", exc)
        respond = echo_reply
    pipeline = VoicePipeline(
        core, speaker, transcriber, recorder, respond=respond, follow_up_seconds=settings.follow_up_seconds
    )
    executor.set_confirmer(pipeline.ask_yes_no)

    device = settings.microphone_device or None
    if device is not None and device.isdigit():
        device = int(device)
    core.start()
    if wake_problem:  # show why the wake word differs from what was configured, then carry on
        core.state.transition(JarvisState.ERROR, wake_problem)
        timer = threading.Timer(8.0, core.state.transition_from, (JarvisState.ERROR, JarvisState.STANDBY))
        timer.daemon = True
        timer.start()
    service = WakeWordService(
        core.bus, Microphone(device), detector, core.state.current, listen_sink=pipeline.feed
    )
    services.append(service)
    service.start()


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_dir, settings.log_level)
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setQuitOnLastWindowClosed(False)  # lives in the tray

    lock = QLockFile(str(settings.data_dir / "jarvis.lock"))
    if not lock.tryLock(100):
        shown = notify_running_instance()
        log.info("JARVIS is already running; %s", "asked it to show" if shown else "exiting")
        return 0

    core = Jarvis()
    bridge = UiBridge(core)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(ORB_QML)))
    if not engine.rootObjects():
        log.error("Failed to load UI from %s", ORB_QML)
        return 1
    window = engine.rootObjects()[0]

    tray = Tray(bridge, window)
    tray.show()

    instance_server = InstanceServer()
    instance_server.showRequested.connect(tray.show_window)
    if not instance_server.listen_for_launches():
        log.warning("Could not listen for relaunches: %s", instance_server.errorString())

    services: list[WakeWordService] = []
    threading.Thread(
        target=start_voice, args=(core, settings, services), name="voice-startup", daemon=True
    ).start()

    code = app.exec()
    for service in services:
        service.stop()
    log.info("JARVIS stopped")
    return code
