import { GLASS, LOOKS, type CoreState } from "./states";
import type { Anchor } from "../story/director";

/** 2D core for devices without WebGL or that can't hold frame rate. Same colours, same round eyes. */
export function CoreFallback({ state, anchor, narrow }: { state: CoreState; anchor: Anchor; narrow: boolean }) {
  const look = LOOKS[state];
  const hex = (c: { getHexString(): string }) => `#${c.getHexString()}`;
  const open = Math.max(0.08, Math.min(1.1, look.open));
  const r = 19 * look.eyeSize;
  const x = narrow || anchor === "center" ? "50%" : anchor === "left" || anchor === "how" ? "24%" : "70%";
  const y = narrow && anchor !== "center" ? "28%" : "50%";
  return (
    <div className="absolute inset-0">
      <svg
        viewBox="-200 -200 400 400"
        className="absolute w-[min(60vw,440px)] -translate-x-1/2 -translate-y-1/2 transition-[left,top] duration-700"
        style={{ left: x, top: y }}
      >
        <defs>
          <radialGradient id="fb-halo">
            <stop offset="45%" stopColor={hex(look.halo)} stopOpacity={look.haloI * 0.8} />
            <stop offset="100%" stopColor={hex(look.halo)} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="fb-body" cx="50%" cy="50%">
            <stop offset="0%" stopColor={hex(look.core)} />
            <stop offset="55%" stopColor={hex(look.swirl)} />
            <stop offset="100%" stopColor={hex(GLASS)} />
          </radialGradient>
          <filter id="fb-eyeglow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <circle r="200" fill="url(#fb-halo)" />
        <circle r="100" fill="url(#fb-body)" stroke={hex(look.rim)} strokeOpacity="0.5" strokeWidth="2" />
        {[-1, 1].map((side) =>
          look.smile > 0.5 ? (
            <path
              key={side}
              d={`M ${side * 31 - r} 2 A ${r} ${r} 0 0 1 ${side * 31 + r} 2`}
              fill="none"
              stroke={hex(look.eye)}
              strokeWidth="6"
              strokeLinecap="round"
              filter="url(#fb-eyeglow)"
            />
          ) : (
            <ellipse key={side} cx={side * 31} cy="-4" rx={r} ry={r * open} fill={hex(look.eye)} filter="url(#fb-eyeglow)" />
          ),
        )}
      </svg>
    </div>
  );
}
