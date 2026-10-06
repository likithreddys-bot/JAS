"""Train the "Hey VEM" wake-word model for openWakeWord, without a GPU or downloaded datasets.

Why this approach: openWakeWord's own training notebook needs PyTorch, a GPU and ~20 GB of
datasets hosted on Hugging Face. None of that is required here: openWakeWord's frozen feature
extractor (melspectrogram + embedding model, shipped with the package) turns any audio into
96-dim embeddings, and only a small classifier on top of 16 of them (1.28 s) has to be learned.

Data, all synthetic:
  * positives  "Hey VEM" in every Kokoro voice plus random blends of voices (more speakers),
               at several speeds and punctuations; Hindi-English voices add an Indian accent.
  * negatives  near-misses ("hey Ben", "hey them", "VEM" alone, "hey Jarvis"...), ordinary
               sentences, and noise alone.
  * augmentation  background noise at 0-20 dB SNR (white/pink/brown, babble from other speech),
               room echo, phone-band filtering, quiet speech (low gain): the noisy places the
               user asked for. Real traffic recordings are not available here.

Evaluation uses the real openWakeWord streaming Model (80 ms frames, as the app runs it) on
voices held out from training: detection rate on held-out "Hey VEM", and false activations per
hour on held-out negative speech. Synthetic voices are NOT the user's voice (see ADR-048): the
model must also be measured on real recordings with scripts/try_wake_words.py before it ships
as the default.

Usage:  python3 scripts/train_wake_word.py KOKORO_DIR OUT.onnx
        (KOKORO_DIR holds kokoro-v1.0.fp16.onnx and voices-v1.0.bin)
Needs:  kokoro-onnx, openwakeword==0.6.0, scikit-learn, onnx, numpy, scipy
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

SR = 16000
CLIP = 32000  # 2 s per training example -> 16 embedding frames
SEED = 7
rng = np.random.default_rng(SEED)

POSITIVE_TEXTS = ["Hey VEM", "Hey, VEM.", "Hey VEM!", "Hey VEM?", "hey vem", "Hey, VEM!"]
CONFUSABLE = [
    "Hey Ben", "Hey them", "Hey Jim", "Hey Ken", "Hey man", "Hey Fam", "Hey Gem", "Hey mum",
    "Hey when", "Hey friend", "Hey Siri", "Hey Jarvis", "VEM", "Hey", "Hey you", "Hey hem",
    "Hey Venus", "Have them", "Hey Pam", "Hey Tim", "Okay then", "Hey, where?", "Hey, Wendy",
]
SENTENCES = [
    "Can you send the report to my manager?", "What's the weather like in Hyderabad today?",
    "I'll be back in ten minutes.", "Let's meet at the station at six.", "Turn the music down a bit.",
    "The meeting has been moved to Thursday.", "Did you finish the slides for the client?",
    "We need more milk and bread.", "Call me when you reach home.", "This traffic is terrible today.",
    "Have you seen my phone anywhere?", "The train is running late again.", "Open the window please.",
    "I think we should leave early tomorrow.", "Where did you put the car keys?", "Thanks, that was helpful.",
    "Every morning I go for a run in the park.", "The quarterly numbers look much better.",
    "Please remind me to pay the electricity bill.", "My cousin's wedding is next week.",
    "Hello, how are you doing?", "The movie starts at nine thirty.", "Let me check my calendar.",
    "Hey there, long time no see!", "Hey everyone, welcome to the call.", "Hey, can you hear me?",
    "Them and their friends went to Goa.", "Ben said he would come later.", "When will the order arrive?",
    "Remember to save the file before closing.", "The venue is near the main road.",
    "I have a dentist appointment at four.", "Venkat sent the invoice yesterday.", "Hem the trousers a little.",
    "Gem stores are closed on Sunday.", "That's a very good point.", "Let's order biryani tonight.",
]


# ---------------------------------------------------------------- synthesis (Kokoro, 24 kHz -> 16 kHz)
def kokoro_speakers(k):
    """Every Kokoro voice plus random blends of two, as (name, style vector)."""
    names = sorted(k.get_voices())
    speakers = [(n, k.get_voice_style(n)) for n in names]
    for i in range(70):
        a, b = rng.choice(names, 2, replace=False)
        w = rng.uniform(0.25, 0.75)
        speakers.append((f"{a}+{b}@{w:.2f}", k.get_voice_style(a) * w + k.get_voice_style(b) * (1 - w)))
    return speakers


def to16k(audio: np.ndarray, sr: int) -> np.ndarray:
    from scipy.signal import resample_poly

    g = np.gcd(sr, SR)
    return resample_poly(audio, SR // g, sr // g).astype(np.float32)


def say(k, style, text: str, speed: float) -> np.ndarray:
    audio, sr = k.create(text, voice=style, speed=speed, lang="en-us")
    return to16k(audio, sr)


# ---------------------------------------------------------------- augmentation
def colored_noise(n: int, kind: str) -> np.ndarray:
    white = rng.standard_normal(n)
    if kind == "white":
        return white
    spec = np.fft.rfft(white)
    f = np.maximum(np.fft.rfftfreq(n), 1 / n)
    spec /= np.sqrt(f) if kind == "pink" else f  # pink 1/f power, brown 1/f^2
    out = np.fft.irfft(spec, n)
    return out / (np.std(out) + 1e-9)


def reverb(x: np.ndarray) -> np.ndarray:
    t = np.arange(int(SR * rng.uniform(0.15, 0.6))) / SR
    ir = rng.standard_normal(len(t)) * np.exp(-t / rng.uniform(0.04, 0.2))
    ir[0] = 1.0
    y = np.convolve(x, ir)[: len(x)]
    return y / (np.max(np.abs(y)) + 1e-9) * np.max(np.abs(x))


def phone_band(x: np.ndarray) -> np.ndarray:
    from scipy.signal import butter, sosfilt

    return sosfilt(butter(4, [300, 3400], btype="band", fs=SR, output="sos"), x)


def augment(x: np.ndarray, babble_pool: list[np.ndarray]) -> np.ndarray:
    x = x.astype(np.float64)
    if rng.random() < 0.35:
        x = reverb(x)
    if rng.random() < 0.25:
        x = phone_band(x)
    speech_rms = np.sqrt(np.mean(x**2)) + 1e-9
    if rng.random() < 0.85:
        snr = rng.uniform(0, 20)  # 0 dB: the noise as loud as the voice (street, traffic)
        if babble_pool and rng.random() < 0.35:
            noise = sum(np.resize(babble_pool[rng.integers(len(babble_pool))], len(x)) for _ in range(3))
            noise = noise / (np.std(noise) + 1e-9)
        else:
            noise = colored_noise(len(x), rng.choice(["white", "pink", "brown", "brown"]))
        x = x + noise * speech_rms / (10 ** (snr / 20))
    gain = 10 ** (rng.uniform(-28, -3) / 20)  # quiet voices too, down to -28 dBFS peaks
    return np.clip(x / (np.max(np.abs(x)) + 1e-9) * gain, -1, 1)


def place(word: np.ndarray, tail_s: float) -> np.ndarray:
    """A 2 s clip with the utterance ending `tail_s` before the end (how the detector sees it)."""
    clip = np.zeros(CLIP)
    tail = int(tail_s * SR)
    word = word[-(CLIP - tail) :]
    clip[CLIP - tail - len(word) : CLIP - tail] = word
    return clip


def windows(stream: np.ndarray, hop: int = 8000) -> list[np.ndarray]:
    return [stream[i : i + CLIP] for i in range(0, len(stream) - CLIP + 1, hop)]


def to_int16(x: np.ndarray) -> np.ndarray:
    return (np.clip(x, -1, 1) * 32767).astype(np.int16)


# ---------------------------------------------------------------- features, model, export
def embed(clips: list[np.ndarray]) -> np.ndarray:
    from openwakeword.utils import AudioFeatures

    feats = AudioFeatures(inference_framework="onnx")
    x = np.stack([to_int16(c) for c in clips])
    emb = feats.embed_clips(x, batch_size=64)  # (N, frames, 96)
    return emb[:, -16:, :].astype(np.float32)


def export_onnx(mlp, out: Path, mean: np.ndarray, std: np.ndarray) -> None:
    """The sklearn MLP as an ONNX graph with openWakeWord's contract: [1,16,96] -> [1,1]."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    inits = [numpy_helper.from_array(mean.astype(np.float32), "mean"),
             numpy_helper.from_array((1 / std).astype(np.float32), "inv_std"),
             numpy_helper.from_array(np.array([1, 16 * 96], dtype=np.int64), "flat_shape")]
    nodes = [helper.make_node("Reshape", ["x", "flat_shape"], ["flat"]),
             helper.make_node("Sub", ["flat", "mean"], ["c"]),
             helper.make_node("Mul", ["c", "inv_std"], ["h0"])]
    h = "h0"
    for i, (w, b) in enumerate(zip(mlp.coefs_, mlp.intercepts_)):
        inits += [numpy_helper.from_array(w.astype(np.float32), f"W{i}"),
                  numpy_helper.from_array(b.astype(np.float32), f"B{i}")]
        nodes.append(helper.make_node("Gemm", [h, f"W{i}", f"B{i}"], [f"z{i}"]))
        last = i == len(mlp.coefs_) - 1
        nodes.append(helper.make_node("Sigmoid" if last else "Relu", [f"z{i}"], ["score" if last else f"h{i + 1}"]))
        h = f"h{i + 1}"
    graph = helper.make_graph(
        nodes, "hey_vem",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 16, 96])],
        [helper.make_tensor_value_info("score", TensorProto.FLOAT, [1, 1])], inits)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], producer_name="vem-wakeword")
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, str(out))


def stream_eval(model_path: Path, audio: np.ndarray, threshold: float) -> int:
    """Activations of the real streaming detector (80 ms frames, 1.5 s refractory) over `audio`."""
    from openwakeword.model import Model

    m = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
    key = next(iter(m.models))
    pcm, hits, last = to_int16(audio), 0, -10**9
    for i in range(0, len(pcm) - 1280 + 1, 1280):
        if m.predict(pcm[i : i + 1280])[key] >= threshold and i - last > 1.5 * SR:
            hits, last = hits + 1, i
    return hits


def main(kokoro_dir: Path, out: Path) -> None:
    from kokoro_onnx import Kokoro
    from sklearn.neural_network import MLPClassifier

    t0 = time.time()
    k = Kokoro(str(kokoro_dir / "kokoro-v1.0.fp16.onnx"), str(kokoro_dir / "voices-v1.0.bin"))
    speakers = kokoro_speakers(k)
    order = rng.permutation(len(speakers))
    held = {speakers[i][0] for i in order[:16]}  # 16 speakers never seen in training
    print(f"{len(speakers)} speakers, {len(held)} held out")

    pos = {"train": [], "test": []}
    neg = {"train": [], "test": []}
    for name, style in speakers:
        split = "test" if name in held else "train"
        for text in rng.choice(POSITIVE_TEXTS, 4, replace=False):
            pos[split].append(say(k, style, text, rng.uniform(0.8, 1.3)))
        for text in rng.choice(CONFUSABLE, 6, replace=False):
            neg[split].append(say(k, style, text, rng.uniform(0.85, 1.25)))
        for text in rng.choice(SENTENCES, 3, replace=False):
            neg[split].append(say(k, style, text, rng.uniform(0.9, 1.2)))
    print(f"synthesised {sum(map(len, pos.values()))} positives, {sum(map(len, neg.values()))} negatives "
          f"in {time.time() - t0:.0f}s")
    babble = [c for c in neg["train"] if len(c) > SR]

    def build(split: str, copies_pos: int, copies_neg: int):
        clips, labels = [], []
        for w in pos[split]:
            for _ in range(copies_pos):
                clips.append(augment(place(w, rng.uniform(0.0, 0.35)), babble))
                labels.append(1)
        neg_stream = np.concatenate([np.concatenate([c, np.zeros(int(rng.uniform(0.1, 0.6) * SR))]) for c in neg[split]])
        for wdw in windows(neg_stream):
            for _ in range(copies_neg):
                clips.append(augment(wdw, babble))
                labels.append(0)
        for _ in range(len(pos[split]) * 2):  # noise alone
            clips.append(augment(np.zeros(CLIP) + 1e-4 * rng.standard_normal(CLIP), babble))
            labels.append(0)
        return clips, np.array(labels)

    clips, y = build("train", 8, 1)
    print(f"training clips: {int(y.sum())} positive, {int((1 - y).sum())} negative; embedding...")
    x = embed(clips).reshape(len(clips), -1)
    mean, std = x.mean(0), x.std(0) + 1e-6
    xs = (x - mean) / std
    # balance: repeat positives so both classes weigh about the same
    rep = max(1, int((1 - y).sum() // max(1, y.sum())))
    xb = np.concatenate([xs, np.repeat(xs[y == 1], rep - 1, axis=0)])
    yb = np.concatenate([y, np.ones(int(y.sum()) * (rep - 1), dtype=int)])
    mlp = MLPClassifier(hidden_layer_sizes=(128, 64), alpha=1e-3, batch_size=256, max_iter=60,
                        early_stopping=True, validation_fraction=0.1, random_state=SEED)
    mlp.fit(xb, yb)
    print(f"trained in {time.time() - t0:.0f}s total; best validation score {mlp.best_validation_score_:.4f}")
    out.parent.mkdir(parents=True, exist_ok=True)
    export_onnx(mlp, out, mean, std)

    # ---- held-out evaluation through the real streaming detector
    report = {"speakers": len(speakers), "held_out_speakers": sorted(held)}
    pos_clean = np.concatenate([np.concatenate([np.zeros(SR), w, np.zeros(SR)]) for w in pos["test"]])
    pos_noisy = np.concatenate([np.concatenate([np.zeros(SR), augment(np.concatenate([w, np.zeros(SR // 2)]), babble), np.zeros(SR // 2)])
                                for w in pos["test"]])
    neg_test = np.concatenate([np.concatenate([augment(c, babble) if rng.random() < 0.5 else c, np.zeros(SR // 3)])
                               for c in neg["test"]])
    hours = len(neg_test) / SR / 3600
    for thr in (0.3, 0.5, 0.7, 0.9):
        report[f"threshold_{thr}"] = {
            "detected_clean": f"{stream_eval(out, pos_clean, thr)}/{len(pos['test'])}",
            "detected_noisy": f"{stream_eval(out, pos_noisy, thr)}/{len(pos['test'])}",
            "false_activations_on_held_out_speech": stream_eval(out, neg_test, thr),
            "held_out_negative_minutes": round(hours * 60, 1),
        }
    print(json.dumps(report, indent=2))
    out.with_suffix(".eval.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
