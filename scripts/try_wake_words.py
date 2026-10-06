"""Record your voice and score every wake-word model against it, to pick the best one.

    .venv\\Scripts\\python.exe scripts\\try_wake_words.py

It asks you to say "Hey VEM" normally, then quietly, then with noise around you (music or the TV
on), then "Jarvis", then ordinary speech. A good model scores high on the takes with its own
word and near zero on ordinary speech. Models whose file is missing are skipped.
"""
from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import Settings  # noqa: E402
from app.voice.audio.microphone import Microphone  # noqa: E402
from app.voice.wake_word.detector import load_openwakeword  # noqa: E402

MODELS = ["hey_vem.onnx", "hey_jarvis", "jarvis_v1.onnx", "jarvis_v2.onnx"]
SECONDS = 12


def record(seconds: int, prompt: str) -> np.ndarray:
    mic = Microphone(None)
    mic.open()
    print(f"\n>>> {prompt}")
    for count in (3, 2, 1):
        print(f"    {count}...", flush=True)
        time.sleep(1)
    print(f"    RECORDING for {seconds} seconds - go!", flush=True)
    frames, end = [], time.time() + seconds
    while time.time() < end:
        frame = mic.read(1.0)
        if frame is not None:
            frames.append(frame)
    mic.close()
    print("    done.")
    return np.concatenate(frames) if frames else np.zeros(0, np.int16)


def peak_scores(audio: np.ndarray, models_dir: Path) -> dict[str, float]:
    scores = {}
    for name in MODELS:
        if name.endswith(".onnx") and not (models_dir / name).exists():
            continue
        detector = load_openwakeword(name, 0.5, models_dir)
        scores[name] = max((detector._predict(audio[i:i + 1280])
                            for i in range(0, len(audio) - 1280, 1280)), default=0.0)
    return scores


def main() -> None:
    settings = Settings()
    models_dir = settings.models_dir / "openwakeword"
    takes = [
        ("say HEY VEM, the way you normally would, about 6 times with a pause between each", "Hey VEM"),
        ("now say HEY VEM QUIETLY, almost under your breath, 5 times", "Hey VEM, quiet"),
        ("turn music or the TV on loud, then say HEY VEM 5 times over it", "Hey VEM, noisy"),
        ("now say JARVIS, 5 times", "Jarvis"),
        ("now just talk normally - say 'hey Ben', 'hey them', anything - but NOT Hey VEM or Jarvis", "other speech"),
    ]
    results = []
    for prompt, label in takes:
        audio = record(SECONDS, prompt)
        if not len(audio):
            print("No audio captured - is the microphone muted?")
            return
        results.append((label, peak_scores(audio, models_dir)))

    print("\n\n  Peak score per model (1.0 = certain it heard the wake word)\n")
    names = list(results[0][1])
    print(f"  {'you said':18}" + "".join(f"{m:>18}" for m in names))
    print("  " + "-" * (18 + 18 * len(names)))
    for label, scores in results:
        print(f"  {label:18}" + "".join(f"{scores[m]:>18.3f}" for m in names))
    print("\n  A good model scores high on the rows with its own word and near zero on the last row.")
    print("  Send this table back and I'll set the model and threshold for you.\n")


if __name__ == "__main__":
    main()
