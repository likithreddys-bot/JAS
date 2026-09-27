"""File, folder, clipboard and VS Code tools for coding help.

Access is limited to one root folder (the user's home by default), never AppData or key
folders, and never secret files (.env, private keys) — their contents would be sent to the LLM.
Overwrites ask first and keep a backup; deletes ask first and go to the Recycle Bin.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from send2trash import send2trash

from app.tools.base import Risk, Tool, ToolResult
from app.tools.computer import keyboard, windows

MAX_READ_CHARS = 60_000
BLOCKED_DIRS = {"appdata", ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker"}
SKIP_WHEN_SEARCHING = BLOCKED_DIRS | {"node_modules", ".git", ".venv", "venv", "__pycache__", ".cache", "site-packages"}
SECRET_FILE = re.compile(r"^(\.env(\..+)?|id_(rsa|ed25519|ecdsa)(\.pub)?|.*\.(pem|key|pfx|p12|kdbx)|credentials(\..+)?)$", re.I)
_NO_WINDOW = subprocess.CREATE_NO_WINDOW


class FileAccessError(Exception):
    pass


class FileAccess:
    def __init__(self, root: Path, backups: Path, notes: Path) -> None:
        self.root = root.resolve()
        self.backups = backups
        self.notes = notes
        # Files JARVIS wrote itself. Rewriting its own work is not a risk worth interrupting the
        # user for, and asking made it invent "_v2" names instead of editing what it had made.
        self.written: set[Path] = set()

    def resolve(self, path: str) -> Path:
        candidate = Path(os.path.expandvars(os.path.expanduser(path.strip().strip('"'))))
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise FileAccessError(f"I can only work inside {self.root}.")
        if any(part.lower() in BLOCKED_DIRS for part in candidate.relative_to(self.root).parts):
            raise FileAccessError("That folder is off limits for safety (app data / keys).")
        return candidate

    def check_not_secret(self, path: Path) -> None:
        if SECRET_FILE.match(path.name):
            raise FileAccessError(f"For safety I don't read or change secret files like {path.name}.")


VSCODE_STATE = Path(os.path.expandvars(r"%APPDATA%\Code\User\globalStorage\storage.json"))


def vscode_folders(state_file: Path = VSCODE_STATE) -> dict[str, Path]:
    """Project folders of VS Code's open windows, by folder name (as shown in window titles)."""
    try:
        state = json.loads(state_file.read_text(encoding="utf-8")).get("windowsState", {})
    except (OSError, ValueError):
        return {}
    folders = {}
    for window in [state.get("lastActiveWindow", {}), *state.get("openedWindows", [])]:
        uri = window.get("folder")
        if uri and uri.startswith("file:"):
            path = Path(unquote(urlparse(uri).path).lstrip("/"))
            folders[path.name] = path
    return folders


def parse_vscode_title(title: str) -> tuple[str, str, bool] | None:
    """"● schemas.py - AI-Tester - Visual Studio Code" -> ("schemas.py", "AI-Tester", unsaved=True)."""
    title = title.removesuffix(" - Visual Studio Code")
    unsaved = title.startswith(("\u25cf", "\u2022"))
    parts = title.lstrip("\u25cf\u2022 ").split(" - ")
    name = parts[0]
    if "." not in name.strip(".") or " " in name:  # "Claude Code", "Welcome", "Settings" aren't files
        return None
    return name, parts[-1] if len(parts) > 1 else "", unsaved


def vscode_cli() -> str | None:
    found = shutil.which("code.cmd") or shutil.which("code")
    default = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"))
    return found or (str(default) if default.exists() else None)


def file_tools(access: FileAccess) -> list[Tool]:
    def guarded(action):
        def run(**kwargs) -> ToolResult:
            try:
                return action(**kwargs)
            except (FileAccessError, OSError) as exc:
                return ToolResult(False, error=str(exc))
        return run

    def read_text(path: Path) -> dict:
        access.check_not_secret(path)
        if not path.is_file():
            raise FileAccessError(f"{path} is not a file.")
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"path": str(path), "content": text[:MAX_READ_CHARS], "truncated": len(text) > MAX_READ_CHARS,
                "lines": text.count("\n") + 1}

    def read_file(path: str) -> ToolResult:
        return ToolResult(True, read_text(access.resolve(path)))

    def read_open_file() -> ToolResult:
        # Front-most VS Code window whose active tab is a file; its title names the file and project.
        code_windows = [w for w in windows.list_windows() if w.process.lower() == "code"]
        if not code_windows:
            return ToolResult(False, error="VS Code isn't open.")
        folders = vscode_folders()
        for window in code_windows:
            parsed = parse_vscode_title(window.title)
            if parsed is None:
                continue
            name, project, unsaved = parsed
            folder = folders.get(project)
            if folder is None:
                continue
            matches = _find_by_name(access.resolve(str(folder)), name)
            if not matches:
                continue
            path = max(matches, key=lambda p: p.stat().st_mtime)  # same name twice: the one edited last
            result = read_text(access.resolve(str(path)))
            if unsaved:
                result["note"] = "The file has unsaved changes in VS Code; this is the saved version."
            if len(matches) > 1:
                result["other_files_with_same_name"] = [str(m) for m in matches if m != path][:5]
            return ToolResult(True, result)
        titles = ", ".join(w.title for w in code_windows)
        return ToolResult(False, error=f"No code file is the active tab in VS Code (windows: {titles}).")

    def list_folder(path: str = "") -> ToolResult:
        folder = access.resolve(path or str(access.root))
        if not folder.is_dir():
            return ToolResult(False, error=f"{folder} is not a folder.")
        entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:200]
        return ToolResult(True, {"folder": str(folder), "entries": [p.name + ("/" if p.is_dir() else "") for p in entries]})

    def _find_by_name(folder: Path, name: str) -> list[Path]:
        found = []
        for current, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_WHEN_SEARCHING and not d.startswith(".")]
            found += [Path(current, f) for f in files if f == name]
        return found

    def find_files(name: str, folder: str = "") -> ToolResult:
        start = access.resolve(folder or str(access.root))
        pattern, found, deadline = name.lower(), [], time.monotonic() + 6
        for current, dirs, files in os.walk(start):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_WHEN_SEARCHING and not d.startswith(".")]
            found += [str(Path(current, f)) for f in files if pattern in f.lower()]
            if len(found) >= 20 or time.monotonic() > deadline:
                break
        return ToolResult(True, {"matches": found[:20], "searched": str(start)})

    def create_folder(path: str) -> ToolResult:
        folder = access.resolve(path)
        folder.mkdir(parents=True, exist_ok=True)
        return ToolResult(True, {"created": str(folder)})

    def write_file(path: str, content: str) -> ToolResult:
        target = access.resolve(path)
        access.check_not_secret(target)
        backup = None
        if target.exists():
            access.backups.mkdir(parents=True, exist_ok=True)
            backup = access.backups / f"{datetime.now():%Y%m%d-%H%M%S}-{target.name}"
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if target.read_text(encoding="utf-8") != content:
            return ToolResult(False, error="The file didn't save correctly.")
        access.written.add(target)
        return ToolResult(True, {"saved": str(target), "lines": content.count("\n") + 1,
                                 "backup": str(backup) if backup else None})

    def delete_path(path: str) -> ToolResult:
        target = access.resolve(path)
        if target == access.root:
            return ToolResult(False, error="I won't delete your whole home folder.")
        if not target.exists():
            return ToolResult(False, error=f"{target} doesn't exist.")
        send2trash(str(target))
        return ToolResult(True, {"moved_to_recycle_bin": str(target)})

    def open_in_vscode(path: str, line: int = 0) -> ToolResult:
        target = access.resolve(path)
        cli = vscode_cli()
        if cli is None:
            return ToolResult(False, error="VS Code's 'code' command isn't installed.")
        arg = [str(target)] if target.is_dir() or not line else ["-g", f"{target}:{line}"]
        subprocess.Popen(["cmd", "/c", cli, *arg], creationflags=_NO_WINDOW)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if any(w.process.lower() == "code" and target.name in w.title for w in windows.list_windows()):
                return ToolResult(True, {"opened": str(target)})
        return ToolResult(False, error=f"Asked VS Code to open {target.name}, but I couldn't see it open.")

    def show_document(title: str, text: str) -> ToolResult:
        access.notes.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "note"
        path = access.notes / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}.md"
        path.write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
        cli = vscode_cli()
        if cli:
            subprocess.Popen(["cmd", "/c", cli, str(path)], creationflags=_NO_WINDOW)
        else:
            os.startfile(path)
        return ToolResult(True, {"shown_in": str(path)})

    def read_clipboard() -> ToolResult:
        return ToolResult(True, {"text": (keyboard.get_clipboard_text() or "")[:MAX_READ_CHARS]})

    def copy_to_clipboard(text: str) -> ToolResult:
        keyboard.set_clipboard_text(text)
        return ToolResult(True, {"copied_characters": len(text)})

    def write_risk(path: str, content: str = "") -> Risk:
        try:
            target = access.resolve(path)
            if target in access.written:
                return Risk.LOW  # JARVIS's own file: it still keeps a backup, it just doesn't ask
            return Risk.MEDIUM if target.exists() else Risk.LOW
        except FileAccessError:
            return Risk.LOW  # write_file will refuse it anyway

    path_param = {"type": "string", "description": "Absolute path, or relative to the user's home folder"}

    return [
        Tool("read_open_file", "Read the file currently open in VS Code (path and full contents). Use for "
             "'explain this code', 'debug this', 'what does this file do'.",
             {"type": "object", "properties": {}}, guarded(read_open_file), lambda: "Reading the open file"),
        Tool("read_file", "Read a text/code file.", {"type": "object", "properties": {"path": path_param}, "required": ["path"]},
             guarded(read_file), lambda path: f"Reading {Path(path).name}"),
        Tool("find_files", "Find files by (part of) their name, e.g. 'schemas.py', in the home folder or a given folder.",
             {"type": "object", "properties": {"name": {"type": "string"}, "folder": path_param}, "required": ["name"]},
             guarded(find_files), lambda name, folder="": f"Searching for {name}"),
        Tool("list_folder", "List the files and folders in a folder (default: home folder).",
             {"type": "object", "properties": {"path": path_param}}, guarded(list_folder),
             lambda path="": f"Listing {Path(path).name or 'home'}"),
        Tool("create_folder", "Create a folder (and any missing parent folders).",
             {"type": "object", "properties": {"path": path_param}, "required": ["path"]},
             guarded(create_folder), lambda path: f"Creating folder {Path(path).name}"),
        Tool("write_file", "Create or overwrite a text/code file with the complete new content. To change a file "
             "you already made, write the SAME path again - never invent a second file. Overwriting someone "
             "else's file asks them first; either way a backup is kept.",
             {"type": "object", "properties": {"path": path_param, "content": {"type": "string"}}, "required": ["path", "content"]},
             guarded(write_file), lambda path, content="": f"Saving {Path(path).name}", risk=write_risk,
             confirm_question=lambda path, content="": f"Should I overwrite {Path(path).name}? I'll keep a backup."),
        Tool("delete_path", "Move a file or folder to the Recycle Bin (always asks the user first).",
             {"type": "object", "properties": {"path": path_param}, "required": ["path"]},
             guarded(delete_path), lambda path: f"Deleting {Path(path).name}", risk=Risk.HIGH,
             confirm_question=lambda path: f"Should I move {Path(path).name} to the Recycle Bin?"),
        Tool("open_in_vscode", "Open a file (optionally at a line) or a folder in VS Code.",
             {"type": "object", "properties": {"path": path_param, "line": {"type": "integer"}}, "required": ["path"]},
             guarded(open_in_vscode), lambda path, line=0: f"Opening {Path(path).name} in VS Code"),
        Tool("show_document", "Show a long answer (code explanation, review, steps) as a document in VS Code, "
             "instead of reading it all aloud. Use Markdown.",
             {"type": "object", "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
              "required": ["title", "text"]},
             guarded(show_document), lambda title, text="": f"Showing “{title}”"),
        Tool("read_clipboard", "Read the text currently copied to the clipboard.", {"type": "object", "properties": {}},
             guarded(read_clipboard), lambda: "Reading the clipboard"),
        Tool("copy_to_clipboard", "Copy text to the clipboard so the user can paste it.",
             {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
             guarded(copy_to_clipboard), lambda text: "Copying to clipboard"),
    ]
