"""JAS's face on the Windows lock screen.

No application can draw on the lock screen itself — it runs on Winlogon's secure desktop, which
only Microsoft's own UI and registered credential providers may touch. What an ordinary app *can*
do is set the lock screen **image**, so JAS is at least present and watching while you are away.

The picture is drawn here rather than grabbed from the orb, because the orb lives on the Qt UI
thread and this runs from the lock watcher's thread.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("jarvis.ui")

WIDTH, HEIGHT = 1920, 1080
BACKDROP = (8, 7, 6)  # the brand's warm black, the same as the website

# JAS's face is the glass orb from the website: rendered once from the same 3D code
# (website/studio, website/scripts/orb_assets.py) into transparent frames shipped with the app.
ORB_DIR = Path(__file__).parent / "assets" / "orb"
ORB_SIZE = 1176  # puts the sphere about 420 px across, the same size the old face was
INK = (247, 241, 230)
MUTED = (166, 156, 141)

MOODS = {
    # orb frame, message template, message colour
    # ("{name}" is substituted with the real name in draw_face - this was hardcoded as a literal
    # name before, so the angry warning always said "Likki"/"Alex" regardless of who was configured).
    "watchful": ("standby", "", MUTED),
    "angry": ("error", "Don't touch {name}'s PC", (234, 110, 92)),
    # The same orb a moment later: its rings have moved on and its light has breathed. Windows
    # redraws the lock screen live when the image file changes even while already locked (confirmed:
    # Windows Spotlight does the same thing), so cycling this against "watchful" every few seconds
    # gives the lock screen real, not simulated, motion. (It was a near-shut blink when JAS had eyes.)
    "blink": ("standby-b", "", MUTED),
}


def _font(size: int):
    for name in ("segoeuivariabledisplay.ttf", "segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=4)
def _orb(frame: str) -> Image.Image | None:
    """One transparent orb frame, scaled for the lock screen. None (and a logged error) if missing."""
    path = ORB_DIR / f"jas-orb-{frame}.png"
    try:
        return Image.open(path).convert("RGBA").resize((ORB_SIZE, ORB_SIZE), Image.LANCZOS)
    except OSError:
        log.exception("Lock-screen orb frame is missing: %s", path)
        return None


def draw_face(mood: str, name: str = "Alex", assistant: str = "JAS",
              with_text: bool = True) -> Image.Image:
    """JAS's glowing orb. The wallpaper wants just the orb; the lock screen wants words."""
    frame, warning, tone = MOODS.get(mood, MOODS["watchful"])
    warning = warning.format(name=name) if warning else warning
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKDROP)

    cx, cy, radius = WIDTH // 2, int(HEIGHT * 0.44), 210
    orb = _orb(frame)
    if orb is not None:
        image.paste(orb, (cx - ORB_SIZE // 2, cy - ORB_SIZE // 2), orb)

    if not with_text:
        return image

    canvas = ImageDraw.Draw(image)
    title = _font(64)
    small = _font(34)
    label = f"{name}'s PC"
    canvas.text((cx, cy + radius + 125), label, font=title, fill=INK, anchor="mm")
    canvas.text((cx, cy + radius + 200), warning or f"{assistant} is watching", font=small, fill=tone, anchor="mm")
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
