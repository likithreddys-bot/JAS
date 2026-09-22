# JARVIS

Personal desktop AI agent for Windows 11. See [JARVIS.md](JARVIS.md) for the full vision, architecture and roadmap.

**Current status:** Phase 1 (Foundation) — floating orb UI, system tray, state machine, event bus, config and logging. No voice or AI yet.

## Setup

Requires **Python 3.12** (some audio/ML packages used in later phases don't support 3.14 yet).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env     # optional in Phase 1
```

## Run

```powershell
.\.venv\Scripts\python.exe run.py
```

The orb appears bottom-right. Drag to move. Use the tray icon to show/hide, pause/resume, or exit.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Manual test scripts live in `tests/manual/`.

## Layout

```text
app/config/        settings (.env) and JSON logging
app/core/events/   event bus + event types
app/core/state/    states, legal transitions, state machine
app/core/jarvis.py core: lifecycle, pause/resume
ui/                Qt bridge, theme, tray, QML orb
tests/             unit + manual tests
logs/, data/       runtime output (gitignored)
```
