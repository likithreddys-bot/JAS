# Lock and unlock (manual test)

JARVIS now follows the lock screen. It cannot be tested without actually locking the PC, so this one is
yours to run.

---

## TEST L.1 — Lock by voice
1. Say: **"Hey Jarvis, lock my PC."**
2. Expect, in this order:
   - the screen locks straight away (no "On it", no confirmation, **it says nothing at all**)
   - the orb goes indigo (resting) with its eyes closed

Say it however you like — "lock my laptop", "lock the computer", "lock my screen" all work.

## TEST L.2 — Unlock
1. Sign back in (password or fingerprint).
2. Expect within about a second: **"Hey Likki, I'm ready."** — and then it listens for a moment in case you
   want to say something.
3. It must **not** give the morning briefing, the weather or the video.

## TEST L.3 — Locking by hand counts too
1. Press **Win + L** yourself.
2. Expect: JARVIS rests just the same, and greets you when you come back.

## TEST L.4 — It stops what it's doing
1. Ask for something slow ("what's the weather and my meetings?").
2. While it is still talking, say **"Hey Jarvis, lock my PC"** — or press Win + L.
3. Expect: it stops mid-sentence, locks, and rests. Nothing is left talking to a locked screen.

---

### What was verified and what wasn't
- Verified by tests: the rest-on-lock and greet-on-unlock behaviour, that locking interrupts work in
  progress, and that "lock my pc" is an instant command returning no speech.
- Verified against the real Windows API: `is_locked()` reports False while the PC is in use.
- **Not verified:** the real lock/unlock cycle, because testing it means locking your screen mid-session.
  That's TEST L.1 and L.2 above. If the greeting doesn't come, tell me and check `logs/jarvis.log` for
  "Screen unlocked".
