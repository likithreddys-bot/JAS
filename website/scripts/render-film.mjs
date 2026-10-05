// Renders film/index.html frame by frame (deterministic, 30 fps), adds the synthesised score
// (scripts/film_music.py) and encodes public/film/luffy-film.mp4.
// Usage: npx vite --port 5173 & node scripts/render-film.mjs
// Needs: Chromium (set CHROMIUM_PATH if Playwright's own is not installed) and an ffmpeg with libx264
// (FFMPEG env var, or `pip install imageio-ffmpeg`, whose binary is found automatically).
import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const FPS = 30;
const URL_ = process.env.FILM_URL || "http://localhost:5173/film/?capture";
const out = path.resolve("public/film");
const frames = fs.mkdtempSync(path.join(os.tmpdir(), "luffy-film-"));
const ffmpeg =
  process.env.FFMPEG ||
  execFileSync("python3", ["-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"]).toString().trim();

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(URL_);
await page.waitForFunction(() => window.__render);
await page.evaluate(() => document.fonts.ready);
const duration = await page.evaluate(() => window.__duration);
const total = Math.round(duration * FPS);
for (let i = 0; i < total; i++) {
  await page.evaluate((t) => window.__render(t), i / FPS);
  await page.screenshot({ path: path.join(frames, `${String(i).padStart(4, "0")}.jpg`), type: "jpeg", quality: 94 });
  if (i % 60 === 0) console.log(`frame ${i}/${total}`);
}
// Poster: a frame from the end card.
await page.evaluate((t) => window.__render(t), 19.5);
fs.mkdirSync(out, { recursive: true });
await page.screenshot({ path: path.join(out, "luffy-film-poster.jpg"), type: "jpeg", quality: 88 });
await browser.close();

// The score: synthesised by scripts/film_music.py (needs numpy), timed to the film's beats.
const music = path.join(frames, "music.wav");
execFileSync("python3", [path.resolve("scripts/film_music.py"), music], { stdio: "inherit" });

execFileSync(ffmpeg, [
  "-y", "-loglevel", "error", "-framerate", String(FPS), "-i", path.join(frames, "%04d.jpg"), "-i", music,
  "-map", "0:v", "-map", "1:a",
  "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p",
  "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
  path.join(out, "luffy-film.mp4"),
]);
fs.rmSync(frames, { recursive: true, force: true });
console.log("wrote", path.join(out, "luffy-film.mp4"));
