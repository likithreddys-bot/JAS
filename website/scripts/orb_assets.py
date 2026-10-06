"""Turns the raw frames from render-orb-assets.mjs into the VEM orb asset pack.

  stills/jas-orb-<state>.png         1024x1024, transparent (difference matte: black vs white render)
  stills/jas-orb-<state>-black.png   1024x1024 on the brand black #080706
  loops/jas-orb-<state>.mp4          6 s seamless loop, 1024x1024, H.264 on #080706 (success: one-shot)
  lockscreen/jas-lock-<state>.png    1920x1080 lock-screen backgrounds (no text: the app draws its own)

Usage: python3 scripts/orb_assets.py <framesDir> <outDir>     (needs numpy, Pillow, imageio-ffmpeg)
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image

FPS = 30
LOOP = 6 * FPS  # frames in the finished loop
FADE = 1 * FPS  # frames cross-faded to hide the seam
BRAND_BLACK = (8, 7, 6)
STATES = ["standby", "listening", "thinking", "executing", "confirming", "responding", "success", "error", "paused"]


def matte(black: Path, white: Path) -> Image.Image:
    """Recover colour + alpha from the same frame rendered over black and over white.
    Over black: R_b = C.  Over white: R_w = C + (1 - A).  So A = 1 - (R_w - R_b), colour = C / A."""
    b = np.asarray(Image.open(black).convert("RGB"), dtype=np.float32) / 255
    w = np.asarray(Image.open(white).convert("RGB"), dtype=np.float32) / 255
    alpha = np.clip(1 - (w - b).mean(axis=2), 0, 1)
    colour = np.where(alpha[..., None] > 1e-3, b / np.maximum(alpha[..., None], 1e-3), 0)
    rgba = np.dstack([np.clip(colour, 0, 1), alpha])
    return Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")


def encode(frames_dir: Path, out: Path) -> None:
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-framerate", str(FPS),
         "-i", str(frames_dir / "%04d.png"), "-c:v", "libx264", "-preset", "slow", "-crf", "18",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        check=True,
    )


def loop(src: Path, out: Path, seamless: bool) -> None:
    frames = sorted(src.glob("*.png"))
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        if seamless:
            # out[i] = F[i] for FADE <= i < LOOP; the first FADE frames blend F[LOOP + i] into F[i],
            # so the last frame flows straight back into the first.
            for i in range(LOOP):
                img = Image.open(frames[i]).convert("RGB")
                if i < FADE:
                    tail = Image.open(frames[LOOP + i]).convert("RGB")
                    img = Image.blend(tail, img, i / FADE)
                img.save(tmpd / f"{i:04d}.png")
        else:
            for i, f in enumerate(frames[: 3 * FPS]):
                Image.open(f).convert("RGB").save(tmpd / f"{i:04d}.png")
        encode(tmpd, out)


def lockscreen(orb: Image.Image, out: Path) -> None:
    W, H = 1920, 1080
    bg = Image.new("RGBA", (W, H), BRAND_BLACK + (255,))
    size = 1180  # sphere about 420 px across, matching the app's lock-screen face
    o = orb.resize((size, size), Image.LANCZOS)
    bg.alpha_composite(o, ((W - size) // 2, int(H * 0.44) - size // 2))
    bg.convert("RGB").save(out)


def main(frames: Path, out: Path) -> None:
    for sub in ("stills", "loops", "lockscreen"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    for s in STATES:
        orb = matte(frames / "stills" / f"{s}-black.png", frames / "stills" / f"{s}-white.png")
        orb.save(out / "stills" / f"jas-orb-{s}.png", optimize=True)
        on_black = Image.new("RGBA", orb.size, BRAND_BLACK + (255,))
        on_black.alpha_composite(orb)
        on_black.convert("RGB").save(out / "stills" / f"jas-orb-{s}-black.png", optimize=True)
        name = f"jas-orb-{s}-oneshot.mp4" if s == "success" else f"jas-orb-{s}.mp4"
        loop(frames / "loops" / s, out / "loops" / name, seamless=(s != "success"))
        if s in ("standby", "listening", "error", "paused"):
            lockscreen(orb, out / "lockscreen" / f"jas-lock-{s}.png")
        print("packed", s)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
