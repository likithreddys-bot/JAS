"""One-time setup: converts Whisper into the format OpenVINO needs to run it on the NPU.

faster-whisper (the CPU path) uses ctranslate2's own model format, already cached under
data/models/whisper/. OpenVINO needs a different format entirely, converted from the *original*
HuggingFace checkpoint - so this downloads openai/whisper-<size> fresh and converts it, rather than
reusing anything already on disk.

Run once:  .venv\\Scripts\\python.exe scripts\\export_whisper_openvino.py [size]

`size` defaults to STT_MODEL in .env (normally "small"), matching whichever size faster-whisper is
already configured to use, so switching STT_BACKEND doesn't also change how accurate JAS is.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.config.settings import Settings

    settings = Settings()
    size = sys.argv[1] if len(sys.argv) > 1 else settings.stt_model
    out_dir = settings.models_dir / "whisper-openvino" / size

    if (out_dir / "openvino_encoder_model.xml").exists():
        print(f"Already exported at {out_dir} - delete it first to re-export.")
        return 0

    print(f"Exporting openai/whisper-{size} to OpenVINO format at {out_dir}")
    print("This downloads the original checkpoint fresh (not the ctranslate2 copy already on "
          "disk, which is a different format) - it can take a while on a slow connection.")

    from optimum.intel.openvino import OVModelForSpeechSeq2Seq
    from transformers import AutoProcessor

    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    model = OVModelForSpeechSeq2Seq.from_pretrained(
        f"openai/whisper-{size}",
        export=True,
        task="automatic-speech-recognition-with-past",
    )
    model.save_pretrained(str(out_dir))
    # openvino_genai.WhisperPipeline also needs the tokenizer/processor files alongside the model.
    AutoProcessor.from_pretrained(f"openai/whisper-{size}").save_pretrained(str(out_dir))

    print(f"Done in {time.perf_counter() - started:.0f} s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
