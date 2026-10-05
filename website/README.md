# JAS website

The public marketing site for JAS. A single scroll-driven page with one live 3D JAS core that changes
state as you move through the story, plus a simulated confirm-gate demo.

Built from `JAS-Frontend-Spec.md` (states, motion, accessibility) and the JAS client documentation
(all copy). The palette is luxury black and champagne gold with no blue anywhere, chosen over the
spec's navy/teal (ADR-090). See ADR-089 and ADR-090 in `../JARVIS.md`.

## Run

```bash
cd website
npm install
npm run dev        # http://localhost:5173
npm run build      # typecheck + production build into dist/
npm run preview    # serve dist/
```

`?dev` in the URL shows an fps meter. `?force3d` keeps the 3D core even when the device is too slow
(the site normally switches to a 2D core then); use it for screenshots on machines without a GPU.

## Test

```bash
npx playwright install chromium   # once, or set CHROMIUM_PATH to an existing Chromium
npm test                          # 12 tests x desktop + phone
```

Covers: no console errors, no third-party requests, every section present, no sideways scroll,
confirm card yes / no / Enter / Esc / 60 s timeout to No, low-risk command answers without asking,
Pause motion, reduced motion (content visible, core static), axe scan with no serious violations.

## Structure

| Path | What |
|---|---|
| `src/content.ts` | All copy. Every claim comes from the client documentation. Contact details live here. |
| `src/core/` | The 3D core (`JasCore`), its nine states (`states.ts`), the page-wide canvas (`CoreLayer`), the 2D fallback. |
| `src/story/director.ts` | Tiny store: which state and position the core should have right now. |
| `src/sections/` | One file per page section. `Roast.tsx` is "Not Siri. Not Gemini. Just JAS." |
| `src/core/GoldDust.tsx` | The floating gold dust behind the page. |
| `src/ui/useTilt.ts` | 3D tilt + gold sheen for any element with `data-tilt`. |
| `src/demo/` | The scripted, simulated demo commands. |
| `public/lock/` | Lock-screen faces rendered by the real `app/lockart.py`. |

## The film

`film/` is the source of the 20-second ad (HR needs an urgent report sent; JAS does it from her phone
in seconds). Every frame is a pure function of time, so it renders frame by frame into a smooth video:

```bash
npx vite --port 5173 &                       # serves film/ at /film/
CHROMIUM_PATH=/path/to/chromium node scripts/render-film.mjs   # writes public/film/jas-film.mp4 + poster
```

Open http://localhost:5173/film/ to watch it play live. Encoding needs an ffmpeg with libx264
(`FFMPEG=/path/to/ffmpeg`, or `pip install imageio-ffmpeg`). The storyboard and brand tokens are also
in Figma: https://www.figma.com/design/b2tEZDVLI0SlNS5nHeAzMj

## Adding Higgsfield footage

Put a short, silent `.mp4` loop in `public/` and set `HERO_LOOP_SRC` in `src/content.ts`. It plays at
30% opacity behind the hero. Keep it under ~3 MB.

## Deploy

`dist/` is a static site: Vercel, Netlify, Cloudflare Pages or GitHub Pages all work with
build command `npm run build` and output directory `dist`. Set the `og:image` in `index.html` to an
absolute URL once the domain is known (some link previews ignore relative URLs).

## Manual checks (not possible in CI)

1. Open the site on the real Android phone. Scroll the whole page: it should feel smooth, and the
   hero core should breathe and blink.
2. On the phone, run the "Email the Q3 report" demo. Tap **Yes, do it**, then run it again and tap
   **No, cancel**. Both should end with the right message.
3. On the PC with a real GPU, open `?dev` and scroll to "How it works": the fps meter should read
   close to your screen's refresh rate.
4. Turn on *Reduce motion* (Windows: Settings → Accessibility → Visual effects → Animation effects
   off). Reload: nothing should move, and all text should be visible.
5. Click **Get in touch**: your mail app should open, addressed to Likki.
