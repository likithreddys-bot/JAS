"""Render VEM's voice for the website and the film with the app's own speaker code.

The clips on the site are what the PC says: they come from app/voice/tts (KokoroSpeaker, voice
am_puck, the moods in app/voice/tts/moods.py), not from a separate demo voice.

Needs kokoro-onnx and the Kokoro model files (downloaded on first use into data/models/kokoro, or
pass a folder that already has them).
Usage (from website/):  python3 scripts/render_voice.py [models_dir]
"""
from __future__ import annotations

import io
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.voice.tts.kokoro_speaker import KokoroSpeaker  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "public" / "voice"
FILM = Path(__file__).resolve().parents[1] / "film" / "voice"

# id: (mood, line) - the site's "Hear VEM" section plays these
SITE = {
    "greeting": ("greeting", "Hey Likki! I'm here. What do you need?"),
    "working": ("working", "On it! Opening the Q3 report now."),
    "confirming": ("confirming", "I'm about to send the Q3 attrition report to Arjun Rao. Should I send it?"),
    "done": ("done", "Done! It's sent. Arjun has it. Anything else?"),
    "error": ("error", "Hmm, I couldn't open that file. It looks like it was moved. Want me to look for it?"),
    "warning": ("warning", "Hey. This is Likki's PC. Please don't touch it."),
}
# The film's lines, placed by scripts/film_mix.py
FILM_LINES = {
    "film-working": ("working", "On it."),
    "film-confirm": ("confirming", "Found it. Send it to Arjun?"),
    "film-sent": ("done", "Sent!"),
    "film-end": ("greeting", "I'm VEM. Your laptop, from anywhere."),
}


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


if __name__ == "__main__":
    models = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "models" / "kokoro"
    speaker = KokoroSpeaker("am_puck", models)
    OUT.mkdir(parents=True, exist_ok=True)
    FILM.mkdir(parents=True, exist_ok=True)
    for name, (mood, line) in SITE.items():
        wav = speaker.render(line, mood)
        subprocess.run([ffmpeg(), "-loglevel", "error", "-y", "-i", "pipe:0", "-b:a", "96k", str(OUT / f"{name}.mp3")],
                       input=wav, check=True)
        print("wrote", OUT / f"{name}.mp3")
    for name, (mood, line) in FILM_LINES.items():
        (FILM / f"{name}.wav").write_bytes(speaker.render(line, mood))
        with wave.open(io.BytesIO((FILM / f"{name}.wav").read_bytes())) as w:
            print("wrote", FILM / f"{name}.wav", f"{w.getnframes() / w.getframerate():.2f}s")
