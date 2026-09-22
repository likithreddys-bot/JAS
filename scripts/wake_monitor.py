"""Live wake-word score meter, for testing reliability and choosing WAKE_WORD_THRESHOLD.

Close the main JARVIS app first (both would compete for the mic). Ctrl+C to stop.
    .venv\\Scripts\\python.exe scripts\\wake_monitor.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import get_settings  # noqa: E402
from app.voice.audio.microphone import Microphone  # noqa: E402
from app.voice.wake_word.detector import load_openwakeword  # noqa: E402


def main() -> None:
    settings = get_settings()
    threshold = settings.wake_word_threshold
    detector = load_openwakeword(settings.wake_word_model, threshold)
    predict = detector._predict  # raw scores, without cooldown
    mic = Microphone(settings.microphone_device or None)
    mic.open()
    print(f"Listening. Say 'Hey Jarvis'. Threshold = {threshold}. Ctrl+C to stop.\n")
    detections, peak, last_hit = 0, 0.0, 0.0
    try:
        while True:
            frame = mic.read(1.0)
            if frame is None:
                continue
            score = predict(frame)
            peak = max(peak, score)
            level = min(int(abs(frame.astype("int32")).mean() / 150), 20)
            if score >= threshold and time.time() - last_hit > 2:
                detections += 1
                last_hit = time.time()
                print(f"\r  >>> WAKE #{detections}  score={score:.2f}".ljust(70))
            bar = "#" * int(score * 30)
            print(f"\r  mic {'|' * level:<20}  score {score:4.2f} {bar:<30} peak {peak:.2f}", end="")
    except KeyboardInterrupt:
        print(f"\n\nDetections: {detections}   Highest score: {peak:.2f}")
    finally:
        mic.close()


if __name__ == "__main__":
    main()
