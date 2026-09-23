# Phase 10 — Clicking in apps and web pages (manual tests)

JARVIS now looks at the **active window**, finds what you describe, and clicks it.
Say things the way you would to a person: "click the blue Send button", "click the search box".

Restart JARVIS first so the new tools are loaded.

---

## TEST 10.1 — Click a button in an app
1. Open Calculator yourself and leave it in front.
2. Say: **"Hey Jarvis, click the 7 button, then plus, then 3, then equals."**
3. Expect: the orb shows "Clicking …" for each step; the display reads **10**.

Pass if all four clicks land on the right keys.

## TEST 10.2 — Click in your own Chrome
1. Open Chrome on any page with a search box.
2. Say: **"Hey Jarvis, click the search box"**, then **"type hello there"**.
3. Expect: the cursor lands in the box and the text appears there.

## TEST 10.3 — Confirmation before a risky click
1. Open any page or mail window that has a **Send**, **Delete** or **Buy** button.
2. Say: **"Hey Jarvis, click the Send button."**
3. Expect: JARVIS **asks first** — "Should I click the Send button?" — and clicks only after you say **yes**.
4. Repeat and say **no**: nothing is clicked and JARVIS says so.

## TEST 10.4 — Something that isn't there
1. Say: **"Hey Jarvis, click the purple submit button."** (with no such button on screen)
2. Expect: JARVIS says it can't see it — it does **not** click anywhere at random.

## TEST 10.5 — Outside the active window
1. Say: **"Hey Jarvis, click the Start button on the taskbar."**
2. Expect: JARVIS looks at the whole screen for this one and the Start menu opens.

## TEST 10.6 — A window jumps in front
1. Say: **"Hey Jarvis, click the 7 button"** on Calculator, then immediately click another window yourself.
2. Expect: JARVIS refuses — "… came to the front while I was looking …, so I didn't click" — and nothing is
   clicked in the wrong app.

## TEST 10.7 — Scrolling
1. Put the mouse over a long page.
2. Say: **"Hey Jarvis, scroll down."**
3. Expect: the page scrolls.

---

### Known limits
- Each click costs one vision call: **5–10 seconds** on the free Gemini tier, and it can hit the 429 quota
  during heavy use. A paid key makes this 1–2 s.
- JARVIS looks at the window that is **in front**. If the thing you want is in another window, say where it is
  ("on the taskbar", "on the desktop") or bring that window forward first.
