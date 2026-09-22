import json
import logging

from app.config.logging_setup import setup_logging
from app.config.settings import Settings


def test_settings_read_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    s = Settings(_env_file=None)
    assert s.log_level == "DEBUG"
    assert s.log_dir == tmp_path


def test_logging_writes_json_and_routes_errors(tmp_path):
    setup_logging(tmp_path, "INFO")
    logging.getLogger("jarvis.voice").info("mic opened")
    logging.getLogger("jarvis.core").error("bad thing")
    for h in logging.getLogger("jarvis").handlers + logging.getLogger("jarvis.voice").handlers:
        h.flush()

    main_lines = [json.loads(l) for l in (tmp_path / "jarvis.log").read_text("utf-8").splitlines()]
    assert {l["msg"] for l in main_lines} == {"mic opened", "bad thing"}
    assert "mic opened" in (tmp_path / "voice.log").read_text("utf-8")
    errors = (tmp_path / "errors.log").read_text("utf-8")
    assert "bad thing" in errors and "mic opened" not in errors

    for name in ("jarvis", "jarvis.voice"):
        for h in logging.getLogger(name).handlers:
            h.close()


def test_crashes_in_background_threads_are_logged(tmp_path):
    import threading

    setup_logging(tmp_path, "INFO")

    def boom():
        raise RuntimeError("thread went bang")

    t = threading.Thread(target=boom, name="worker")
    t.start()
    t.join()
    for h in logging.getLogger("jarvis").handlers:
        h.flush()
    assert "thread went bang" in (tmp_path / "errors.log").read_text("utf-8")
    for h in logging.getLogger("jarvis").handlers:
        h.close()
