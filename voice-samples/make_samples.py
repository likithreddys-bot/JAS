# Renders the Luffy voice samples in this folder with Kokoro (pip install kokoro-onnx soundfile;
# model files kokoro-v1.0.onnx and voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx releases,
# placed next to this script). WAVs are written here; the MP3s were encoded from them with ffmpeg.
import time, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
k = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
# mood: (line, speed, gain) - mood is carried by pace, loudness and wording (Kokoro has no emotion knob)
MOODS = [
    ("Greeting",   "Hey Likki! I'm here. What do you need?",                                   1.12, 1.00),
    ("Working",    "On it! Opening the Q3 report now.",                                         1.15, 1.00),
    ("Confirming", "I'm about to send the Q3 attrition report to Arjun Rao. Should I send it?", 0.93, 0.95),
    ("Done",       "Done! It's sent. Arjun has it. Anything else?",                             1.18, 1.00),
    ("Error",      "Hmm, I couldn't open that file. It looks like it was moved. Want me to look for it?", 0.95, 0.85),
    ("Warning",    "Hey. This is Likki's PC. Please don't touch it.",                           0.86, 1.00),
]
VOICES = ["am_puck", "af_heart", "am_fenrir", "af_bella"]
for v in VOICES:
    parts, t0, sr = [], time.time(), 24000
    for name, line, speed, gain in MOODS:
        audio, sr = k.create(line, voice=v, speed=speed, lang="en-us")
        audio = audio / (np.max(np.abs(audio)) + 1e-9) * 0.85 * gain
        parts += [audio, np.zeros(int(sr * 0.9))]
    out = np.concatenate(parts).astype(np.float32)
    sf.write(f"luffy-voice-{v}.wav", out, sr)
    print(v, f"{len(out)/sr:.1f}s audio in {time.time()-t0:.1f}s")
