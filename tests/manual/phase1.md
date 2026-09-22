# Phase 1 — Manual Tests

Run: `.venv\Scripts\python.exe run.py`

| ID | Steps | Expected | Result |
|---|---|---|---|
| TEST 001 | Start JARVIS | Blue orb appears bottom-right, label **Ready**, orb breathes slowly, arc orbits slowly. Tray icon is a blue orb. | |
| TEST 002 | Drag the orb panel | Window moves smoothly with the mouse | |
| TEST 003 | Hover the orb | Orb lifts slightly (subtle scale) | |
| TEST 004 | Tray → **Pause JARVIS** | Orb fades to grey, label **Paused**, arc stops. Tray icon turns grey. Menu now says **Resume JARVIS** | |
| TEST 005 | Tray → **Resume JARVIS** | Back to blue / Ready | |
| TEST 006 | Left-click tray icon (or **Hide JARVIS**) | Orb hides; click again shows it | |
| TEST 007 | Run `run.py` a second time while running | Second copy exits immediately; log says "already running" | |
| TEST 008 | Tray → **Exit** | Orb and tray icon disappear; `logs/jarvis.log` ends with "JARVIS stopped" | |
| TEST 009 | Leave idle 1 minute, check Task Manager (python.exe) | CPU well under 3% total; RAM ~170 MB | |
