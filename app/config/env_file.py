"""Read and update the .env file from the Settings screen, keeping comments and order intact."""
from __future__ import annotations

import re
from pathlib import Path

_LINE = re.compile(r"^\s*([A-Z0-9_]+)\s*=(.*)$")


def read_values(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if match := _LINE.match(line):
            values[match.group(1)] = match.group(2).strip()
    return values


def update_values(env_file: Path, changes: dict[str, str]) -> list[str]:
    """Write `changes` into .env (updating existing keys in place, appending new ones).

    Returns the keys that actually changed.
    """
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    changed, seen = [], set()
    for index, line in enumerate(lines):
        match = _LINE.match(line)
        if not match or match.group(1) not in changes:
            continue
        key = match.group(1)
        seen.add(key)
        new = str(changes[key]).strip()
        if match.group(2).strip() != new:
            lines[index] = f"{key}={new}"
            changed.append(key)
    missing = [(k, str(v).strip()) for k, v in changes.items() if k not in seen]
    if missing:
        lines += ["", "# Added from the JARVIS settings screen"] + [f"{k}={v}" for k, v in missing]
        changed += [k for k, _ in missing]
    if changed:
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed
