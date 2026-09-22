# Phase 2 — Manual Tests (Wake Word)

| ID | Steps | Expected | Result |
|---|---|---|---|
| TEST 010 | Say **"Hey Jarvis"** at normal volume, ~1 m from the laptop | Within ~0.5 s the orb turns **green** and says **"Yes?"**, then returns to blue **Ready** after ~3 s | |
| TEST 011 | Repeat "Hey Jarvis" 10 times (wait for Ready between) | At least 9 / 10 detected | |
| TEST 012 | Talk normally / play a YouTube video for 5 minutes | No (or very rare) false "Yes?" | |
| TEST 013 | Hide the orb, then say "Hey Jarvis" | Orb reappears showing "Yes?" | |
| TEST 014 | Pause JARVIS, say "Hey Jarvis" | Nothing happens. Windows mic-in-use icon disappears from the taskbar | |
| TEST 015 | Resume, say "Hey Jarvis" | Works again | |
| TEST 016 | While hidden, run `.venv\Scripts\python.exe run.py` | The existing orb reappears (no second copy) | |
| TEST 017 | Sign out and back in (or restart) | JARVIS starts by itself: orb shows "Starting" then "Ready" | |
| TEST 018 | Settings → Privacy → Microphone → turn off mic access for desktop apps | Orb turns red: "Microphone unavailable…". Turn access back on → returns to Ready within ~5 s | |

**Tuning:** if detection is weak or too eager, close JARVIS and run
`.venv\Scripts\python.exe scripts\wake_monitor.py` to see live scores, then set `WAKE_WORD_THRESHOLD` in `.env`.

**Autostart off:** `.venv\Scripts\python.exe scripts\autostart.py uninstall`
