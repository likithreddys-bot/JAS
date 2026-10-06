"""Original score for the 20-second VEM film, synthesised from scratch (no samples, no licences).

Timed to the film's beats (see film/film.ts):
  0.0-6.8 s   urgency: a dark A-minor pad and a ticking clock
  6.8-12.8 s  VEM arrives: the harmony warms (Fmaj7 -> G) and a plucked arpeggio rises
  12.8 s      "Sent.": a bell, the clock stops, the music resolves to C major
  12.8-20 s   relief: a warm Cmaj9 under "Done in seconds." and the end card, fading out

Then VEM's own voice (rendered by scripts/render_voice.py with the app's speaker) is laid over it at
the film's beats, with the music dipped under each line so the words stay clear.

Usage: python3 scripts/film_music.py out.wav      (needs numpy)
"""
from __future__ import annotations

import sys
import wave

import numpy as np

SR = 48_000
DUR = 20.0
N = int(SR * DUR)
rng = np.random.default_rng(7)  # fixed seed: the same score every render


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def env(length: int, attack: float, release: float) -> np.ndarray:
    """Linear-in, exponential-ish-out envelope over `length` samples."""
    e = np.ones(length)
    a = min(length, int(attack * SR))
    r = min(length, int(release * SR))
    if a:
        e[:a] = np.linspace(0, 1, a) ** 1.5
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** 2
    return e


def add(buf: np.ndarray, sig: np.ndarray, t0: float, pan: float = 0.0) -> None:
    """Mix a mono signal into the stereo buffer at time t0 with constant-power pan (-1..1)."""
    i = int(t0 * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    left = np.cos((pan + 1) * np.pi / 4)
    right = np.sin((pan + 1) * np.pi / 4)
    buf[0, i : i + len(sig)] += sig * left
    buf[1, i : i + len(sig)] += sig * right


def pad(buf, notes, t0, t1, amp, bright=1.0, attack=1.4, release=1.8):
    """Warm additive pad: soft harmonics, three slightly detuned voices per side for width."""
    length = int((t1 - t0 + release) * SR)
    t = np.arange(length) / SR
    e = env(length, attack, release)
    for side, pan in ((0, -0.6), (1, 0.6)):
        sig = np.zeros(length)
        for n in notes:
            f = midi(n)
            for d in (-0.0016, 0.0, 0.0016) if side == 0 else (-0.0011, 0.0004, 0.0019):
                for h in range(1, 7):
                    if f * h > 6000:
                        break
                    a = (1 / h**1.7) * (bright if h > 2 else 1.0)
                    sig += a * np.sin(2 * np.pi * f * (1 + d) * h * t + rng.uniform(0, 2 * np.pi))
        sig *= e * amp / (len(notes) * 3)
        add(buf, sig, t0, pan)


def pluck(buf, n, t0, amp, pan=0.0, decay=0.996, length_s=1.8):
    """Karplus-Strong plucked string: a soft, glassy harp-like note."""
    f = midi(n)
    period = int(SR / f)
    length = int(length_s * SR)
    line = rng.uniform(-1, 1, period)
    out = np.empty(length)
    idx = 0
    for i in range(length):
        nxt = (idx + 1) % period
        out[i] = line[idx]
        line[idx] = decay * 0.5 * (line[idx] + line[nxt])
        idx = nxt
    out *= env(length, 0.004, 0.6) * amp
    add(buf, out, t0, pan)


def bell(buf, n, t0, amp, pan=0.0):
    """Struck bell: inharmonic partials, each with its own decay."""
    f = midi(n)
    length = int(4.5 * SR)
    t = np.arange(length) / SR
    sig = np.zeros(length)
    for ratio, a, tau in ((1.0, 1.0, 2.2), (2.0, 0.55, 1.4), (2.76, 0.4, 0.9), (5.4, 0.22, 0.5), (8.93, 0.12, 0.25)):
        sig += a * np.exp(-t / tau) * np.sin(2 * np.pi * f * ratio * t)
    sig *= env(length, 0.002, 0.3) * amp
    add(buf, sig, t0, pan)


def tick(buf, t0, amp, pan=0.0):
    """Clock tick: a tiny, high, filtered noise click."""
    length = int(0.03 * SR)
    noise = rng.uniform(-1, 1, length)
    click = np.diff(np.concatenate([[0], noise]))  # crude high-pass
    click *= np.exp(-np.arange(length) / (0.004 * SR)) * amp
    add(buf, click, t0, pan)


def sub(buf, n, t0, t1, amp):
    length = int((t1 - t0 + 1.2) * SR)
    t = np.arange(length) / SR
    sig = np.sin(2 * np.pi * midi(n) * t) * env(length, 0.8, 1.2) * amp
    add(buf, sig, t0)


def riser(buf, t0, t1, amp):
    """Air swelling into the moment of sending: noise, low-passed by an opening filter."""
    length = int((t1 - t0) * SR)
    noise = rng.uniform(-1, 1, length)
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(length, 1 / SR)
    spec *= 1 / (1 + (freqs / 2500) ** 2)
    sig = np.fft.irfft(spec, length)
    sig /= np.max(np.abs(sig)) + 1e-9
    sig *= np.linspace(0, 1, length) ** 3 * amp
    add(buf, sig, t0, 0.0)


def reverb(buf, mix=0.28, seconds=2.6):
    """Convolution with a synthetic decaying-noise hall, a different tail per channel."""
    length = int(seconds * SR)
    t = np.arange(length) / SR
    out = np.empty_like(buf)
    for ch in range(2):
        ir = rng.normal(0, 1, length) * np.exp(-t / 0.55)
        ir[: int(0.012 * SR)] = 0  # pre-delay
        ir /= np.sqrt(np.sum(ir**2))
        size = N + length
        wet = np.fft.irfft(np.fft.rfft(buf[ch], size) * np.fft.rfft(ir, size), size)[:N]
        out[ch] = (1 - mix) * buf[ch] + mix * wet
    return out


def score() -> np.ndarray:
    buf = np.zeros((2, N))
    # 0-6.8 s: urgency. A minor (add9), low and dim; a clock ticking.
    pad(buf, [45, 52, 57, 59], 0.0, 6.9, 0.42, bright=0.55, attack=1.6)
    sub(buf, 33, 0.0, 6.8, 0.16)
    t = 0.45
    while t < 12.8:
        tick(buf, t, 0.09 if int(t * 2) % 2 == 0 else 0.06, pan=0.25)
        t += 0.5
    # 6.8-10.4 s: VEM appears. Fmaj7 warms the room; a plucked arpeggio starts.
    pad(buf, [41, 48, 52, 57, 64], 6.8, 10.5, 0.45, bright=0.8)
    sub(buf, 29, 6.8, 10.4, 0.18)
    arp_f = [65, 69, 72, 76, 72, 69]
    for i, step in enumerate(np.arange(6.9, 10.4, 0.3)):
        pluck(buf, arp_f[i % len(arp_f)], step, 0.18 + 0.08 * (step - 6.9) / 3.5, pan=-0.35 if i % 2 else 0.35)
    # 10.4-12.8 s: it finds the file and asks. G, brighter, the arpeggio climbs.
    pad(buf, [43, 50, 55, 59, 62], 10.4, 12.9, 0.5, bright=0.95)
    sub(buf, 31, 10.4, 12.8, 0.2)
    arp_g = [67, 71, 74, 79, 74, 71, 74, 79]
    for i, step in enumerate(np.arange(10.4, 12.75, 0.3)):
        pluck(buf, arp_g[i % len(arp_g)], step, 0.26 + 0.06 * (step - 10.4) / 2.4, pan=-0.35 if i % 2 else 0.35)
    riser(buf, 11.6, 12.8, 0.06)
    # 12.8 s: "Sent." A bell; the clock stops; resolve to C major.
    bell(buf, 84, 12.8, 0.16, pan=-0.2)
    bell(buf, 91, 12.82, 0.08, pan=0.3)
    pad(buf, [36, 43, 52, 59, 62, 64], 12.8, 20.0, 0.55, bright=1.0, attack=0.25, release=2.4)
    sub(buf, 24, 12.8, 19.0, 0.22)
    for i, n in enumerate([72, 76, 79, 83, 86]):
        pluck(buf, n, 12.85 + i * 0.09, 0.16, pan=-0.4 + 0.2 * i, length_s=2.4)
    # 17.6 s: the end card. One last, softer bell.
    bell(buf, 88, 17.8, 0.09, pan=0.15)
    return buf


def master(buf: np.ndarray) -> np.ndarray:
    buf = reverb(buf)
    fade_in = int(0.5 * SR)
    buf[:, :fade_in] *= np.linspace(0, 1, fade_in)
    fade_out = int(2.0 * SR)
    buf[:, -fade_out:] *= np.linspace(1, 0, fade_out) ** 1.5
    buf = np.tanh(buf * 1.4) / np.tanh(1.4)  # gentle saturation, glues the mix
    return buf / (np.max(np.abs(buf)) + 1e-9) * 0.89  # peak about -1 dBFS


# VEM's lines: (file in film/voice, start in seconds). Timed to film/film.ts: it finds the file and
# asks while the steps and the confirm card appear (10.55-12.2, before her tap at 12.2), says "Sent!"
# with the bell, and introduces itself on the end card.
VOICE_LINES = [("film-confirm", 10.55), ("film-sent", 12.86), ("film-end", 17.95)]
VOICE_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "film" / "voice"


def read_mono(path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
        return data, w.getframerate()


def add_voice(buf: np.ndarray) -> np.ndarray:
    """Lay VEM's lines over the score and duck the music beneath them. A missing clip is an error."""
    duck = np.ones(N)
    voice = np.zeros(N)
    for name, t0 in VOICE_LINES:
        clip, rate = read_mono(VOICE_DIR / f"{name}.wav")
        clip = np.interp(np.arange(int(len(clip) * SR / rate)) * rate / SR, np.arange(len(clip)), clip)
        i = int(t0 * SR)
        clip = clip[: N - i]
        voice[i : i + len(clip)] += clip * 0.95
        # music down ~8 dB from just before the line to just after, with soft edges
        a, b = max(0, i - int(0.15 * SR)), min(N, i + len(clip) + int(0.25 * SR))
        duck[a:b] = 0.4
    kernel = np.hanning(int(0.12 * SR))
    duck = np.convolve(duck, kernel / kernel.sum(), mode="same")
    return np.stack([buf[0] * duck + voice, buf[1] * duck + voice])


def write_wav(path: str, buf: np.ndarray) -> None:
    pcm = (np.clip(buf.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "film-music.wav"
    write_wav(out, np.clip(add_voice(master(score())), -0.98, 0.98))
    print("wrote", out)
