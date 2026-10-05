// Renders the JAS orb (studio/) into raw frames for the brand asset pack:
//   stills/<state>-black.png + <state>-white.png   (matted to transparency by orb_assets.py)
//   loops/<state>/%04d.png                          (7 s at 30 fps on the brand black)
// Usage: npx vite --port 5173 &  node scripts/render-orb-assets.mjs <outDir>
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve(process.argv[2] || "orb-frames");
const BASE = process.env.STUDIO_URL || "http://localhost:5173/studio/";
const SIZE = 1024;
const FPS = 30;
const STATES = ["standby", "listening", "thinking", "executing", "confirming", "responding", "success", "error", "paused"];
// When each still is taken: after the cross-fade into the state has settled. Success is a moment
// (ring at 0-0.6 s, back to standby after 1.6 s), so its still is taken while it is still green.
const STILL_AT = { success: 0.9 };

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: SIZE, height: SIZE } });
const open = async (state, bg) => {
  await page.goto(`${BASE}?state=${state}&size=${SIZE}&bg=${encodeURIComponent(bg)}`);
  await page.waitForFunction(() => window.__ready);
};
const shot = async (t, file) => {
  await page.evaluate((t) => window.__frame(t), t);
  await page.screenshot({ path: file });
};

fs.mkdirSync(path.join(OUT, "stills"), { recursive: true });
for (const state of STATES) {
  const t = STILL_AT[state] ?? 3.0;
  for (const bg of ["#000000", "#ffffff"]) {
    await open(state, bg);
    // Warm the clock up to t so cross-fades and the success ring are where they should be.
    for (let w = 0; w <= t; w += 1 / FPS) await page.evaluate((x) => window.__frame(x), w);
    await shot(t, path.join(OUT, "stills", `${state}-${bg === "#000000" ? "black" : "white"}.png`));
  }
  // Loops: 7 s on the brand black; orb_assets.py cross-fades the last second into the first.
  const dir = path.join(OUT, "loops", state);
  fs.mkdirSync(dir, { recursive: true });
  await open(state, "#080706");
  const start = state === "success" ? 0 : 1.0;
  for (let i = 0; i < 7 * FPS; i++) await shot(start + i / FPS, path.join(dir, `${String(i).padStart(4, "0")}.png`));
  console.log("rendered", state);
}
await browser.close();
