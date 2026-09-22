# Phase 3 — Manual Tests (Voice)

| ID | Steps | Expected | Result |
|---|---|---|---|
| TEST 020 | Say **"Hey Jarvis"** | Orb green, JARVIS **says "Yes?"** out loud (instantly) | |
| TEST 021 | After "Yes?", say "How are you today" and stop | Orb reacts to your voice while you talk; stops listening ~1 s after you finish; shows “how are you today”; says **"You said: how are you today"**; back to Ready | |
| TEST 022 | Say "Hey Jarvis", then stay silent | After ~5 s returns to Ready without saying anything | |
| TEST 023 | Say a long sentence (~10 s) | Whole sentence captured and repeated | |
| TEST 024 | Say "Hey Jarvis", then while it's talking, right-click → Pause | Speech stops immediately; orb grey | |
| TEST 025 | Speak with a fan/music in background | Still ends listening when you stop (may take a little longer) | |
| TEST 026 | 10 different short sentences | Note how many were transcribed correctly | |

Note: Phase 3 only **repeats** what you said. Real answers come with the LLM in Phase 4.
