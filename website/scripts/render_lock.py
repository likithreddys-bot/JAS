"""Render the website's lock-screen pictures from the app's own lock-screen code.

The site's lock-screen showcase must be what the PC really shows, so its images are drawn by
app/lockart.py itself, never redrawn here. Text is left off (with_text=False) and laid over the
image as HTML at the same positions, so it stays sharp at any size and does not depend on which
fonts this machine has (the app uses Windows fonts).

Usage (from website/):  python3 scripts/render_lock.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.lockart import draw_face  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "public" / "lock"

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for mood in ("watchful", "blink", "angry"):
        img = draw_face(mood, with_text=False).resize((1280, 720))
        img.save(OUT / f"{mood}.webp", "WEBP", quality=88, method=6)
        print("wrote", OUT / f"{mood}.webp")
