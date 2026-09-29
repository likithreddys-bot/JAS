"""JAS's face on the Windows lock screen.

No application can draw on the lock screen itself — it runs on Winlogon's secure desktop, which
only Microsoft's own UI and registered credential providers may touch. What an ordinary app *can*
do is set the lock screen **image**, so JAS is at least present and watching while you are away.

The picture is drawn here rather than grabbed from the orb, because the orb lives on the Qt UI
thread and this runs from the lock watcher's thread.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("jarvis.ui")

WIDTH, HEIGHT = 1920, 1080
BACKDROP = (11, 14, 20)

MOODS = {
    # sphere colour, eye openness, brow angle (degrees, inward-down is positive), message template
    # ("{name}" is substituted with the real name in draw_face - this was hardcoded as a literal
    # name before, so the angry warning always said "Likki"/"Alex" regardless of who was configured).
    "watchful": ((255, 196, 107), 1.00, 0, ""),
    "angry": ((232, 92, 84), 0.62, 20, "Don't touch {name}'s PC"),
    # A brief, near-shut frame. Windows redraws the lock screen live when the image file changes
    # even while already locked (confirmed: Windows Spotlight does the same thing), so cycling this
    # against "watchful" every few seconds gives the lock screen a real, not simulated, blink.
    "blink": ((255, 196, 107), 0.06, 0, ""),
}


def _font(size: int):
    for name in ("segoeuivariabledisplay.ttf", "segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_face(mood: str, name: str = "Alex", assistant: str = "JAS",
              with_text: bool = True) -> Image.Image:
    """JAS's sphere and its eyes. The wallpaper wants just the face; the lock screen wants words."""
    colour, openness, brow_tilt, warning = MOODS.get(mood, MOODS["watchful"])
    warning = warning.format(name=name) if warning else warning
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKDROP)
    canvas = ImageDraw.Draw(image, "RGBA")

    cx, cy, radius = WIDTH // 2, int(HEIGHT * 0.44), 210
    # A soft halo, drawn as widening translucent rings.
    for step in range(28, 0, -1):
        spread = radius + step * 9
        canvas.ellipse([cx - spread, cy - spread, cx + spread, cy + spread],
                       fill=(*colour, max(1, int(30 * (1 - step / 28)))))

    skin = tuple(int(c * 0.42 + 242 * 0.58) for c in colour)  # washed towards warm white
    canvas.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=skin)
    canvas.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                   outline=tuple(min(255, int(c * 1.25)) for c in colour), width=3)

    # Shading, so the sphere reads as lit rather than flat.
    for step in range(radius, 0, -6):
        shade = 1 - 0.35 * (1 - step / radius)
        canvas.ellipse([cx - step, cy - step, cx + step, cy + step],
                       fill=tuple(int(c * (2 - shade) / 1.0) if False else int(c * shade + 255 * (1 - shade) * 0.35)
                                  for c in skin))
    highlight = int(radius * 0.55)
    canvas.ellipse([cx - highlight - 40, cy - highlight - 40, cx + highlight - 90, cy + highlight - 90],
                   fill=(255, 255, 255, 26))

    eye_dx, eye_r = 84, 66
    for side in (-1, 1):
        ex, ey = cx + side * eye_dx, cy + 2
        eh = max(7, int(eye_r * openness))
        canvas.ellipse([ex - eye_r, ey - eh, ex + eye_r, ey + eh], fill=(255, 255, 255))
        pupil = min(34, eh)
        canvas.ellipse([ex - pupil, ey - pupil, ex + pupil, ey + pupil], fill=(18, 21, 30))
        canvas.ellipse([ex - pupil + 8, ey - pupil + 6, ex - pupil + 24, ey - pupil + 22],
                       fill=(255, 255, 255, 235))

        # Brows sit just above each eye. Inner ends drop when angry, level when calm.
        half, by = 62, ey - eh - 34
        tilt = int(half * brow_tilt / 45)
        canvas.line([(ex - half, by + tilt * side), (ex + half, by - tilt * side)],
                    fill=(18, 21, 30), width=15)

    if not with_text:
        return image

    title = _font(64)
    small = _font(34)
    label = f"{name}'s PC"
    canvas.text((cx, cy + radius + 90), label, font=title, fill=(232, 236, 244), anchor="mm")
    if warning:
        canvas.text((cx, cy + radius + 165), warning, font=small, fill=tuple(min(255, c + 20) for c in colour),
                    anchor="mm")
    else:
        canvas.text((cx, cy + radius + 165), f"{assistant} is watching", font=small,
                    fill=(140, 150, 170), anchor="mm")
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
