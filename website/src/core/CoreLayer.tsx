import { useEffect, useRef, useState } from "react";
import { DABS, paintEnso, paintEnsoRange } from "./enso";
import { useReducedMotion } from "./useReducedMotion";
import { effectiveState, useDirector, type Anchor } from "../story/director";
import type { CoreState } from "./labels";

/** Ink colour per mood, as a theme token (index.css). */
const INK: Record<CoreState, string> = {
  standby: "--color-ink",
  listening: "--color-sun",
  thinking: "--color-ink",
  executing: "--color-earth",
  confirming: "--color-amber",
  responding: "--color-sun",
  success: "--color-earth",
  error: "--color-alert",
  paused: "--color-muted",
};

/** Where the circle sits for each anchor: centre (px) and diameter of the brush canvas (px). */
function placement(anchor: Exclude<Anchor, "hidden">, w: number, h: number, narrow: boolean) {
  const m = Math.min(w, h);
  if (narrow) {
    if (anchor === "hero") return { x: w / 2, y: h * 0.53, d: Math.min(w * 0.95, h * 0.5) };
    return { x: w / 2, y: h * 0.5, d: w * 0.9 };
  }
  switch (anchor) {
    case "hero":
      return { x: w / 2, y: h * 0.7, d: m * 0.5 };
    case "center":
      return { x: w / 2, y: h * 0.5, d: m * 0.56 };
    case "left":
    case "how":
      return { x: w * 0.24, y: h * 0.5, d: m * 0.8 };
    case "right":
      return { x: w * 0.76, y: h * 0.5, d: m * 0.8 };
  }
}

function useNarrow() {
  const q = "(max-width: 767px)";
  const [narrow, setNarrow] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.replace("#", "").slice(0, 6), 16);
  return Number.isNaN(n) ? `rgba(28,25,21,${a})` : `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${Math.max(0, a)})`;
};

/**
 * The one core for the whole page: Luffy's ensō, painted with the same brush as the lock screen, on
 * a fixed click-through canvas behind the content. It glides between section anchors and changes
 * mood with the story. 2D canvas, so it runs everywhere; with reduced motion (or Pause) it is drawn
 * only when something changes.
 */
export default function CoreLayer() {
  const d = useDirector();
  const state = effectiveState(d);
  const reduced = useReducedMotion() || d.paused;
  const narrow = useNarrow();
  const offstage = d.anchor === "hidden" || (narrow && (d.anchor === "left" || d.anchor === "right"));
  const canvas = useRef<HTMLCanvasElement>(null);
  // Live values for the draw loop, so it never restarts on a state change.
  const live = useRef({ state, anchor: d.anchor, offstage, narrow, reduced, changedAt: performance.now() });
  const redraw = useRef<() => void>(() => {});

  useEffect(() => {
    const l = live.current;
    if (l.state !== state) l.changedAt = performance.now();
    Object.assign(l, { state, anchor: d.anchor, offstage, narrow, reduced });
    redraw.current();
  }, [state, d.anchor, offstage, narrow, reduced]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    // The canvas can only use a font the page has loaded: fetch the glyph for the 済 seal up front.
    document.fonts?.load('700 40px "Luffy JP Display"', "済").catch((e) => console.warn("Seal font not loaded:", e));
    const ink = document.createElement("canvas");
    const ictx = ink.getContext("2d")!;
    const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    let W = 0, H = 0, dpr = 1, inkSize = 0, inkColor = "", raf = 0;
    const pos = { x: 0, y: 0, d: 0, first: true };
    let drawIn = live.current.reduced ? 1 : 0;
    const t0 = performance.now();
    // Gold leaf: a few flakes drifting slowly upward, behind everything.
    const flakes = Array.from({ length: 26 }, (_, i) => ({
      x: (i * 0.618) % 1, y: (i * 0.371) % 1, s: 2 + ((i * 7) % 5), v: 0.004 + ((i * 13) % 7) * 0.0012, r: i,
    }));

    const resize = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      W = window.innerWidth;
      H = window.innerHeight;
      cv.width = Math.round(W * dpr);
      cv.height = Math.round(H * dpr);
      draw(performance.now());
    };

    let painted = 0; // dabs already on the ink canvas while the stroke is drawn in
    const paintInk = (color: string, size: number) => {
      if (ink.width !== size) ink.width = ink.height = size;
      paintEnso(ictx, size, color, 1);
      inkColor = color;
      inkSize = size;
    };

    function draw(now: number) {
      const l = live.current, t = (now - t0) / 1000, still = l.reduced;
      const target = l.offstage || l.anchor === "hidden"
        ? { x: pos.x, y: pos.y, d: 0 }
        : placement(l.anchor as Exclude<Anchor, "hidden">, W, H, l.narrow);
      // In the hero the circle sits in the space the page reserved for it (so it never covers the
      // headline, whatever the window's shape) and scrolls away with the page.
      if (l.anchor === "hero" && !l.offstage) {
        const r = document.querySelector("[data-core-slot]")?.getBoundingClientRect();
        if (r && r.height > 0) Object.assign(target, { x: r.left + r.width / 2, y: r.top + r.height / 2, d: Math.min(r.height / 0.84, W * 0.95) });
      }
      if (pos.first) Object.assign(pos, target, { first: false });
      const k = still ? 1 : 0.09;
      pos.x += (target.x - pos.x) * k;
      pos.y = l.anchor === "hero" ? target.y : pos.y + (target.y - pos.y) * k;
      pos.d += (target.d - pos.d) * k;

      const id = l.state, color = css(INK[id]) || "#1c1915";
      const size = Math.max(64, Math.round(Math.max(pos.d, 1) * dpr / 64) * 64); // re-raster in steps
      if (drawIn < 1 && !still && color === inkColor && size === inkSize) {
        // Draw the stroke in: add the next dabs to the ink canvas, never repaint the old ones.
        drawIn = Math.min(1, drawIn + 0.016);
        const e = drawIn * drawIn * (3 - 2 * drawIn);
        painted = paintEnsoRange(ictx, size, color, painted, Math.round(e * DABS.length));
      } else if (drawIn < 1 && !still) {
        if (ink.width !== size) ink.width = ink.height = size;
        ictx.clearRect(0, 0, size, size);
        painted = 0;
        inkColor = color;
        inkSize = size;
      } else if (color !== inkColor || Math.abs(size - inkSize) >= 128 || painted < DABS.length) {
        drawIn = 1;
        painted = DABS.length;
        paintInk(color, size);
      }

      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx!.clearRect(0, 0, W, H);

      // gold leaf
      const gold = css("--color-sun");
      for (const f of flakes) {
        const y = ((f.y - (still ? 0 : t * f.v)) % 1 + 1) % 1;
        ctx!.save();
        ctx!.translate(f.x * W, y * H);
        ctx!.rotate(still ? f.r : t * 0.3 + f.r);
        ctx!.fillStyle = rgba(gold, 0.28);
        ctx!.fillRect(-f.s / 2, -f.s / 3, f.s, f.s * 0.66);
        ctx!.restore();
      }

      if (pos.d < 2) return;
      const c = { x: pos.x, y: pos.y }, D = pos.d;
      // a soft wash of colour behind the circle
      const glowA = ({ listening: 0.2, responding: 0.14 + 0.08 * Math.sin(t * 6), confirming: 0.14 + 0.06 * Math.sin(t * 2.2), error: 0.16, success: 0.16, paused: 0.03 } as Record<string, number>)[id] ?? 0.08;
      const g = ctx!.createRadialGradient(c.x, c.y, D * 0.05, c.x, c.y, D * 0.55);
      g.addColorStop(0, rgba(color, still ? glowA * 0.8 : glowA));
      g.addColorStop(1, rgba(color, 0));
      ctx!.fillStyle = g;
      ctx!.fillRect(c.x - D, c.y - D, D * 2, D * 2);

      // listening: ripples on still water
      if (id === "listening" && !still) {
        for (let i = 0; i < 3; i++) {
          const p = (t * 0.5 + i / 3) % 1;
          ctx!.strokeStyle = rgba(color, (1 - p) * 0.45);
          ctx!.lineWidth = Math.max(1, D * 0.003);
          ctx!.beginPath();
          ctx!.arc(c.x, c.y, D * (0.36 + p * 0.14), 0, Math.PI * 2);
          ctx!.stroke();
        }
      }

      // the circle
      const breath = still || id === "paused" ? 1
        : 1 + 0.012 * Math.sin(t * (id === "confirming" ? 2.2 : 1.6)) + (id === "responding" ? 0.02 * Math.abs(Math.sin(t * 7)) : 0);
      const shake = id === "error" && !still && now - l.changedAt < 600 ? Math.sin(now / 18) * D * 0.006 : 0;
      const spin = still ? 0 : id === "thinking" ? t * 0.6 : id === "executing" ? t * 0.25 : 0;
      ctx!.save();
      ctx!.translate(c.x + shake, c.y);
      ctx!.rotate(spin);
      ctx!.scale(breath, breath);
      ctx!.globalAlpha = id === "paused" ? 0.45 : 1;
      ctx!.drawImage(ink, -D / 2, -D / 2, D, D);
      ctx!.restore();
      ctx!.globalAlpha = 1;

      // thinking: three gold ink drops travel round the circle
      if (id === "thinking") {
        for (let i = 0; i < 3; i++) {
          const a = (still ? 0 : t * 1.8) + i * 2.094;
          ctx!.fillStyle = rgba(gold, 0.9);
          ctx!.beginPath();
          ctx!.arc(c.x + Math.cos(a) * D * 0.45, c.y + Math.sin(a) * D * 0.45, Math.max(2, D * 0.009), 0, Math.PI * 2);
          ctx!.fill();
        }
      }
      // executing: a gold arc tracks the work
      if (id === "executing") {
        const a = still ? 0 : t * 2.2;
        ctx!.strokeStyle = rgba(gold, 0.9);
        ctx!.lineWidth = Math.max(2, D * 0.006);
        ctx!.lineCap = "round";
        ctx!.beginPath();
        ctx!.arc(c.x, c.y, D * 0.45, a, a + 1.1);
        ctx!.stroke();
      }
      // success: the "done" seal is pressed into the middle
      if (id === "success") {
        const p = still ? 1 : Math.min(1, (now - l.changedAt) / 350), s = D * 0.11 * (1.4 - 0.4 * p);
        ctx!.save();
        ctx!.globalAlpha = p;
        ctx!.translate(c.x, c.y);
        ctx!.rotate(-0.06);
        ctx!.fillStyle = css("--color-alert");
        ctx!.fillRect(-s / 2, -s / 2, s, s);
        ctx!.fillStyle = css("--color-bg");
        ctx!.font = `700 ${s * 0.5}px ${css("--font-display") || "serif"}`;
        ctx!.textAlign = "center";
        ctx!.textBaseline = "middle";
        ctx!.fillText("済", 0, s * 0.03);
        ctx!.restore();
      }
      // paused: one still dot
      if (id === "paused") {
        ctx!.fillStyle = color;
        ctx!.beginPath();
        ctx!.arc(c.x, c.y + D * 0.46, Math.max(2, D * 0.008), 0, Math.PI * 2);
        ctx!.fill();
      }
    }

    // Motion: a frame loop. Still: draw on change, scroll and resize only.
    const loop = (now: number) => {
      draw(now);
      if (!live.current.reduced) raf = requestAnimationFrame(loop);
    };
    redraw.current = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(loop);
    };
    const onScroll = () => live.current.reduced && draw(performance.now());
    window.addEventListener("resize", resize);
    window.addEventListener("scroll", onScroll, { passive: true });
    resize();
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("scroll", onScroll);
      redraw.current = () => {};
    };
  }, []);

  return (
    <div
      aria-hidden
      className="fixed inset-0 z-0 pointer-events-none"
      data-core-visible={!offstage}
      data-testid="core-layer"
      data-core-state={state}
      data-core-anchor={d.anchor}
      data-dabs={DABS.length}
    >
      <canvas ref={canvas} className="block h-full w-full" />
    </div>
  );
}
