# Phase 6 — Manual Tests (Browser)

Say "Hey Jarvis" first (follow-ups within ~6 s don't need it).

| ID | Say | Expected | Result |
|---|---|---|---|
| TEST 070 | "Open Chrome in my Alex profile" | Your own Chrome opens in the Alex profile (no profile picker) | |
| TEST 071 | "Open Gmail in my alexsmith profile" | That profile opens at Gmail | |
| TEST 072 | "Play Sahiba on YouTube Music" | JARVIS's Chrome window opens (first time ~5 s) and Sahiba plays; if an ad plays first, JARVIS says so | |
| TEST 073 | "Pause" / "Resume" / "Next song" | Music pauses / resumes / skips; JARVIS names the new song | |
| TEST 074 | "Play lofi hip hop on YouTube" | A YouTube video plays | |
| TEST 075 | "What's the weather in London today?" | A real answer (temperature/conditions), not "check a website" | |
| TEST 076 | "Open Wikipedia and search for Charminar" | Wikipedia opens and shows the Charminar article | |
| TEST 077 | "Play zzqqxx" (nonsense) | JARVIS says it's the closest match / may not be what you wanted | |
| TEST 078 | Close JARVIS's Chrome window, then "Play Sahiba" | The window reopens by itself and plays | |

Optional: log in to YouTube Music once in JARVIS's Chrome window (no ads with Premium, your playlists) — it stays logged in.
