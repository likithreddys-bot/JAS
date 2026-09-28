"""Picking between the CPU and OpenVINO speech-to-text backends.

CPU (faster-whisper) always works. OpenVINO needs a one-time model export
(scripts/export_whisper_openvino.py) that not every machine will have run, so asking for it must
never stop JAS from starting - it should fall back to CPU instead.
"""
from app.voice.stt import make_transcriber
from app.voice.stt.transcriber import Transcriber


def test_cpu_backend_is_a_transcriber(tmp_path):
    t = make_transcriber("cpu", "GPU", "small", tmp_path, "en")
    assert isinstance(t, Transcriber)


def test_openvino_without_an_export_falls_back_to_cpu(tmp_path):
    """Nothing at tmp_path/whisper-openvino/small - as on any machine that hasn't run the export."""
    t = make_transcriber("openvino", "GPU", "small", tmp_path, "en")
    assert isinstance(t, Transcriber), "must still start JAS, not raise or refuse"


def test_openvino_with_a_real_export_is_used(tmp_path):
    ov_dir = tmp_path / "whisper-openvino" / "small"
    ov_dir.mkdir(parents=True)
    (ov_dir / "openvino_encoder_model.xml").write_text("<fake/>")

    t = make_transcriber("openvino", "GPU", "small", tmp_path, "en")
    from app.voice.stt.openvino_transcriber import OpenVinoTranscriber
    assert isinstance(t, OpenVinoTranscriber)


def test_the_vocabulary_hint_reaches_either_backend(tmp_path):
    t = make_transcriber("cpu", "GPU", "small", tmp_path, "en", vocabulary="Sreenidhi, Arzoo")
    assert t._hint == "Sreenidhi, Arzoo."

    ov_dir = tmp_path / "whisper-openvino" / "small"
    ov_dir.mkdir(parents=True)
    (ov_dir / "openvino_encoder_model.xml").write_text("<fake/>")
    t2 = make_transcriber("openvino", "GPU", "small", tmp_path, "en", vocabulary="Sreenidhi, Arzoo")
    assert t2._hotwords == "Sreenidhi, Arzoo"
