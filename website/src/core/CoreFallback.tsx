import { GLASS, LOOKS, type CoreState } from "./states";
import type { Anchor } from "../story/director";

/** 2D core for devices without WebGL or that can't hold frame rate. Same colours, same glowing orb. */
export function CoreFallback({ state, anchor, narrow }: { state: CoreState; anchor: Anchor; narrow: boolean }) {
  const look = LOOKS[state];
  const hex = (c: { getHexString(): string }) => `#${c.getHexString()}`;
  const x = narrow || anchor === "center" || anchor === "hero" ? "50%" : anchor === "left" || anchor === "how" ? "24%" : "70%";
  const y = anchor === "hero" ? "58%" : narrow && anchor !== "center" ? "28%" : "50%";
  return (
    <div className="absolute inset-0">
      <svg
        viewBox="-200 -200 400 400"
        className="absolute w-[min(60vw,440px)] -translate-x-1/2 -translate-y-1/2 transition-[left,top] duration-700"
        style={{ left: x, top: y }}
      >
        <defs>
          <radialGradient id="fb-halo">
            <stop offset="45%" stopColor={hex(look.halo)} stopOpacity={Math.min(1, look.haloI)} />
            <stop offset="100%" stopColor={hex(look.halo)} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="fb-body" cx="45%" cy="42%">
            <stop offset="0%" stopColor={hex(look.core)} />
            <stop offset="55%" stopColor={hex(look.swirl)} />
            <stop offset="100%" stopColor={hex(GLASS)} />
          </radialGradient>
        </defs>
        <circle r="200" fill="url(#fb-halo)" />
        <circle r="100" fill="url(#fb-body)" stroke={hex(look.rim)} strokeOpacity="0.6" strokeWidth="2" />
        <ellipse cx="-34" cy="-46" rx="16" ry="9" fill="#F7F1E6" opacity="0.5" transform="rotate(-30 -34 -46)" />
        {[140, 165].map((r) => (
          <ellipse key={r} rx={r} ry={r * 0.32} fill="none" stroke={hex(look.rim)} strokeOpacity={look.waves * 0.5} strokeWidth="1.5" transform="rotate(-18)" />
        ))}
      </svg>
    </div>
  );
}
