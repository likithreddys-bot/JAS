# Phase 5 — Manual Tests (Computer Control)

Say "Hey Jarvis" before each request. Watch the orb: amber (thinking) → orange with a ✓ checklist (working) → violet (speaking).

| ID | Say | Expected | Result |
|---|---|---|---|
| TEST 050 | "Open Notepad" | Notepad opens; orb shows ✓ Opening notepad; "Done, Notepad is open." | |
| TEST 051 | "Type hello from Jarvis" | Text appears in Notepad (JARVIS's orb never steals the typing) | |
| TEST 052 | "Close Notepad" | JARVIS asks "Should I close …?" → say **yes** → Notepad shows its own save prompt; JARVIS says it may be asking to save | |
| TEST 053 | "Close Notepad" → say **no** | Nothing closes; JARVIS just acknowledges | |
| TEST 054 | "Open Calculator" then "Minimize it" | Calculator opens, then minimizes | |
| TEST 055 | "Switch to Chrome" | Chrome comes to the front | |
| TEST 056 | "Turn the volume up" / "Pause the music" | Volume changes / media pauses | |
| TEST 057 | "Take a screenshot" | File saved in Pictures\JARVIS; JARVIS says so | |
| TEST 058 | "Open Photoshop" (not installed) | Says it can't find it; does NOT open something else | |
| TEST 059 | "Click the blue button" | Says it can't click or see the screen yet | |
| TEST 060 | While a task runs: right-click orb → Pause | Task stops, orb grey, nothing more happens | |
