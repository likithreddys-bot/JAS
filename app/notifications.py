"""Native Windows toast notifications."""
from __future__ import annotations

import logging

log = logging.getLogger("jarvis.notifications")

_toaster = None


def notify(title: str, text: str) -> bool:
    """Show a Windows notification. Returns False (and logs) if it couldn't be shown."""
    global _toaster
    try:
        # Imported lazily: WinRT must not load before Qt (COM apartment clash, see media.py).
        from windows_toasts import Toast, WindowsToaster

        if _toaster is None:
            _toaster = WindowsToaster("JARVIS")
        toast = Toast()
        toast.text_fields = [title, text]
        _toaster.show_toast(toast)
        return True
    except Exception:
        log.exception("Couldn't show notification %r", title)
        return False
