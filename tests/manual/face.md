# The face (manual tests)

JARVIS's face is modelled on the Sphere in Las Vegas (`ui/sphere.webp`): a big pale lit sphere, two round
white eyes, thin curved brows, no mouth. Look at the orb while you do these — you should be able to tell what
it is doing **without reading the label**.

---

## TEST F.1 — It's alive
1. Just watch the orb for 20 seconds without saying anything.
2. Expect: a calm blue sphere, level brows, and a **blink** every few seconds (irregular, not clockwork).

## TEST F.2 — The eyes follow you
1. Move your mouse slowly in a big circle around the orb.
2. Expect: both pupils track the cursor. Far away = eyes fully turned; close to the orb = barely move.

## TEST F.3 — Listening
1. Say **"Hey Jarvis"** and keep talking.
2. Expect: the sphere turns green, brows lift, **pupils widen as you speak** and settle when you stop.

## TEST F.4 — Thinking
1. Ask something that takes a while: **"Hey Jarvis, what's the weather and my next meeting?"**
2. Expect: amber sphere, brows tilt inward, eyes narrow and **look up and away**, drifting slowly — they stop
   following the mouse while it thinks.

## TEST F.5 — Speaking
1. While it answers you, watch the eyes.
2. Expect: purple sphere and the eyes become **smiling arcs** ⌒ ⌒.

## TEST F.6 — Something wrong
1. Say: **"Hey Jarvis, open notepadd"** (a misspelt app).
2. Expect: red sphere, brows angled hard inward, small pupils.

## TEST F.7 — Resting
1. Say: **"Hey Jarvis, go offline."**
2. Expect: indigo sphere, eyes closed to gentle curves, and the eyes stop following the mouse.
3. Say **"wake up Jarvis"** — the eyes open again.

## TEST F.8 — It watches what it clicks
1. Open Calculator, leave it in front.
2. Say: **"Hey Jarvis, click the 7 button."**
3. Expect: as the mouse travels to the button, **the eyes follow it there**.

---

### Notes
- There is **no mouth** — you asked for eyes and brows only. The Sphere photo has a thin smile line; say the
  word and I'll add one that curves with the mood.
- The sphere is warm white washed with the state colour, so it stays pale and friendly but you can still read
  the state from across the room.
- Cost of the whole orb UI, measured on its own with nothing else running: **1.12% CPU**, of which the face
  is 0.09%. (A measurement taken while JARVIS was transcribing speech and playing music showed 7–16% — that
  was the work, not the face.)
