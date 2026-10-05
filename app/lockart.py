"""The assistant's face on the Windows lock screen: an ink-brush ensō.

No application can draw on the lock screen itself — it runs on Winlogon's secure desktop, which
only Microsoft's own UI and registered credential providers may touch. What an ordinary app *can*
do is set the lock screen **image**, so JAS is at least present and watching while you are away.

The picture is drawn here rather than grabbed from the orb, because the orb lives on the Qt UI
thread and this runs from the lock watcher's thread.
"""
from __future__ import annotations

import logging
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("jarvis.ui")

WIDTH, HEIGHT = 1920, 1080
BACKDROP = (15, 13, 11)  # black lacquer, the dark ground of the website's ink style

# The face is an ensō, the Zen brush circle, drawn stroke by stroke from a fixed seed. The website
# (website/src/core/enso.ts) uses the same generator, so the PC and the site draw the same stroke.
ENSO_SIZE = 680  # canvas side; the circle itself is about 0.68 of it, ~460 px across
SUPERSAMPLE = 2
INK = (239, 231, 216)
MUTED = (169, 159, 144)
CREAM = (226, 211, 180)
SHU = (217, 84, 58)  # seal vermilion
GOLD = (210, 167, 90)
KATAKANA = {"luffy": "ルフィ"}  # names the seal can write in Japanese; anything else gets its initial

MOODS = {
    # ink colour, glow colour, turn in degrees, message template, message colour
    # ("{name}" is substituted with the real name in draw_face - this was hardcoded as a literal
    # name before, so the angry warning always said "Likki"/"Alex" regardless of who was configured).
    "watchful": (CREAM, GOLD, 0, "", MUTED),
    "angry": (SHU, SHU, 0, "Don't touch {name}'s PC", SHU),
    # The same circle a moment later, turned a few degrees. Windows redraws the lock screen live when
    # the image file changes even while already locked (confirmed: Windows Spotlight does the same
    # thing), so cycling this against "watchful" every few seconds gives the lock screen real, not
    # simulated, motion. (It was a near-shut blink when the face had eyes.)
    "blink": (CREAM, GOLD, 9, "", MUTED),
}


def _font(size: int, names=("yumindb.ttf", "georgiab.ttf", "segoeuib.ttf", "arialbd.ttf",
                            "DejaVuSerif-Bold.ttf")):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _jp_font(size: int):
    """A face with katakana for the seal (Windows ships Yu Mincho and MS Mincho). None if absent."""
    for name in ("yumindb.ttf", "yumin.ttf", "msmincho.ttc", "YuGothB.ttc", "ipag.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return None


def enso_dabs(seed: int = 7) -> list[tuple[float, float, float, float, float]]:
    """The brush stroke as bristle dabs: (angle, radius factor, dab size, alpha, progress 0-1).

    A port of strokeDabs() in website/src/core/enso.ts - same LCG, same order of draws - so both
    draw the identical circle: a heavy press at the start, thinning, dry-brush streaks at the end.
    """
    state = seed & 0xFFFFFFFF

    def rnd() -> float:
        nonlocal state
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        return state / 4294967296

    steps, bristles = 520, 26
    start, sweep = -math.pi * 0.58, math.pi * 1.86
    wob = [rnd() * 6, rnd() * 6, rnd() * 6]
    dry = [0.55 + rnd() * 0.45 for _ in range(bristles)]
    dabs = []
    for i in range(steps):
        u = i / (steps - 1)
        a = start + u * sweep
        press = min(1.0, u * 14) * (1 - u ** 2.4 * 0.82)
        w = 0.085 * press + 0.012
        rr = 1 + 0.018 * math.sin(a * 2 + wob[0]) + 0.01 * math.sin(a * 5 + wob[1])
        for b in range(bristles):
            if u > dry[b] and rnd() < (u - dry[b]) * 5:
                continue
            off = (b / (bristles - 1) - 0.5) * w * 2
            alpha = (0.55 + rnd() * 0.45) * (1 - (u - 0.9) * 6 if u > 0.9 else 1)
            dabs.append((a, rr + off, 0.0042 + rnd() * 0.0035, max(0.0, alpha), u))
    return dabs


@lru_cache(maxsize=1)
def _enso_mask() -> Image.Image:
    """Ink coverage of the stroke (L mode), alpha-composited dab over dab like a canvas would."""
    size = ENSO_SIZE * SUPERSAMPLE
    cover = np.zeros((size, size), np.float32)
    c, rad = size / 2, size * 0.34
    for a, r, d, alpha, _ in enso_dabs():
        x, y, rd = c + math.cos(a) * rad * r, c + math.sin(a) * rad * r, d * size
        x0, x1 = int(x - rd - 1), int(x + rd + 2)
        y0, y1 = int(y - rd - 1), int(y + rd + 2)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        disc = np.clip(rd + 0.5 - np.hypot(xx - x, yy - y), 0, 1) * alpha
        patch = cover[y0:y1, x0:x1]
        patch[:] = 1 - (1 - patch) * (1 - disc)
    mask = Image.fromarray((cover * 255).astype(np.uint8), "L")
    return mask.resize((ENSO_SIZE, ENSO_SIZE), Image.LANCZOS)


def _glow(color: tuple[int, int, int], strength: float) -> Image.Image:
    """A soft radial wash of colour behind the circle, as RGBA."""
    size = ENSO_SIZE
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.hypot(xx - size / 2, yy - size / 2) / (size * 0.5)
    alpha = np.clip(1 - d, 0, 1) ** 1.6 * strength * 255
    layer = np.zeros((size, size, 4), np.uint8)
    layer[..., :3] = color
    layer[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(layer, "RGBA")


def _spaced(canvas: ImageDraw.ImageDraw, centre: tuple[int, int], text: str, font, fill,
            tracking: int) -> None:
    """Letter-spaced text centred on `centre` (Pillow has no tracking of its own)."""
    widths = [canvas.textlength(ch, font=font) for ch in text]
    x = centre[0] - (sum(widths) + tracking * (len(text) - 1)) / 2
    for ch, w in zip(text, widths):
        canvas.text((x, centre[1]), ch, font=font, fill=fill, anchor="lm")
        x += w + tracking


def _seal(image: Image.Image, assistant: str) -> None:
    """The vermilion name seal in the top-right corner, written top to bottom."""
    text = KATAKANA.get(assistant.lower(), assistant[:1].upper())
    font = _jp_font(34) if text != assistant[:1].upper() else _font(40)
    if font is None:  # no Japanese font on this machine: fall back to the initial, and say so
        log.error("No font with katakana found for the lock-screen seal; using the initial")
        text, font = assistant[:1].upper(), _font(40)
    seal = Image.new("RGBA", (78, 46 + 40 * len(text)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(seal)
    draw.rectangle((2, 2, seal.width - 3, seal.height - 3), outline=SHU + (235,), width=4)
    for i, ch in enumerate(text):
        draw.text((seal.width / 2, 43 + i * 40), ch, font=font, fill=SHU + (235,), anchor="mm")
    seal = seal.rotate(-6, resample=Image.BICUBIC, expand=True)
    image.paste(seal, (WIDTH - 150 - seal.width // 2, 96), seal)


def draw_face(mood: str, name: str = "Alex", assistant: str = "JAS",
              with_text: bool = True) -> Image.Image:
    """The ensō on black lacquer. The wallpaper wants just the circle; the lock screen wants words."""
    ink, glow, turn, warning, tone = MOODS.get(mood, MOODS["watchful"])
    warning = warning.format(name=name) if warning else warning
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKDROP)

    cx, cy = WIDTH // 2, int(HEIGHT * 0.43)
    corner = (cx - ENSO_SIZE // 2, cy - ENSO_SIZE // 2)
    halo = _glow(glow, 0.2 if mood == "angry" else 0.13)
    image.paste(halo, corner, halo)
    mask = _enso_mask().rotate(-turn, resample=Image.BICUBIC) if turn else _enso_mask()
    image.paste(Image.new("RGB", mask.size, ink), corner, mask)

    if not with_text:
        return image

    _seal(image, assistant)
    canvas = ImageDraw.Draw(image)
    base = cy + int(ENSO_SIZE * 0.36)
    canvas.text((cx, base + 70), f"{name}'s PC", font=_font(60), fill=INK, anchor="mm")
    line = warning or f"{assistant} is watching".upper()
    if warning:
        canvas.text((cx, base + 140), line, font=_font(36), fill=tone, anchor="mm")
    else:
        _spaced(canvas, (cx, base + 140), line, _font(24, ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")),
                tone, 9)
    return image


def set_wallpaper(mood: str, where: Path, name: str = "Alex", assistant: str = "JAS") -> bool:
    """Put JAS's face on the desktop. Just the circle — the desktop already has your icons on it."""
    import ctypes

    where.mkdir(parents=True, exist_ok=True)
    path = where / f"wallpaper-{mood}.jpg"
    draw_face(mood, name, assistant, with_text=False).save(path, "JPEG", quality=92)
    SPI_SETDESKWALLPAPER, UPDATE_AND_SAVE = 0x0014, 0x03
    ok = bool(ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, str(path), UPDATE_AND_SAVE))
    log.info("Wallpaper set to %s (%s)", path.name, "ok" if ok else "refused")
    return ok


def set_lock_screen(mood: str, where: Path, name: str = "Alex", assistant: str = "JAS") -> bool:
    """Draw the face and make it the Windows lock screen. False if Windows refused."""
    where.mkdir(parents=True, exist_ok=True)  # `where` is the folder, not the file
    path = where / f"lock-{mood}.jpg"
    draw_face(mood, name, assistant).save(path, "JPEG", quality=90)
    return _apply(path)


def _apply(path: Path) -> bool:
    try:
        import asyncio

        from winrt.windows.storage import StorageFile
        from winrt.windows.system.userprofile import LockScreen

        async def go() -> None:
            file = await StorageFile.get_file_from_path_async(str(path))
            await LockScreen.set_image_file_async(file)

        asyncio.new_event_loop().run_until_complete(go())
        log.info("Lock screen set to %s", path.name)
        return True
    except Exception:
        log.exception("Could not set the lock screen image")
        return False
