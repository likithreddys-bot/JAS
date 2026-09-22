"""Start JARVIS automatically when you sign in to Windows (per-user, no admin needed).

Usage:
    .venv\\Scripts\\python.exe scripts\\autostart.py install
    .venv\\Scripts\\python.exe scripts\\autostart.py uninstall
    .venv\\Scripts\\python.exe scripts\\autostart.py status
"""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "JARVIS"


def command() -> str:
    pythonw = ROOT / ".venv" / "Scripts" / "pythonw.exe"  # no console window
    return f'"{pythonw}" "{ROOT / "run.py"}"'


def current() -> str | None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        try:
            return winreg.QueryValueEx(key, VALUE_NAME)[0]
        except FileNotFoundError:
            return None


def install() -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())


def uninstall() -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    elif action != "status":
        print(__doc__)
        return 2
    value = current()
    print(f"Autostart: {'ON  -> ' + value if value else 'OFF'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
