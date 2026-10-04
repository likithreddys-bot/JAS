import { LOOKS, type CoreState } from "./states";
import type { Anchor } from "../story/director";

/** 2D core for devices without WebGL or that can't hold frame rate. Same colours, same face. */
export function CoreFallback({ state, anchor, narrow }: { state: CoreState; anchor: Anchor; narrow: boolean }) {
  const look = LOOKS[state];
  const body = `#${look.body.getHexString()}`;
  const edge = `#${look.edge.getHexString()}`;
  const halo = `#${look.halo.getHexString()}`;
  const open = Math.max(0.08, Math.min(1.1, look.open));
  const x = narrow || anchor === "center" ? "50%" : anchor === "left" || anchor === "how" ? "24%" : "70%";
  const y = narrow && anchor !== "center" ? "28%" : "50%";
  return (
    <div className="absolute inset-0" style={{ transition: "opacity 400ms" }}>
      <svg
        viewBox="-200 -200 400 400"
        className="absolute w-[min(60vw,440px)] -translate-x-1/2 -translate-y-1/2 transition-[left,top] duration-700"
        style={{ left: x, top: y }}
      >
        <defs>
          <radialGradient id="fb-halo">
            <stop offset="45%" stopColor={halo} stopOpacity={look.haloI * 0.8} />
            <stop offset="100%" stopColor={halo} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="fb-body" cx="40%" cy="35%">
            <stop offset="0%" stopColor={body} />
            <stop offset="100%" stopColor={edge} />
          </radialGradient>
        </defs>
        <circle r="200" fill="url(#fb-halo)" />
        <circle r="100" fill="url(#fb-body)" />
        {[-1, 1].map((side) => (
          <g key={side} transform={`translate(${side * 32} -2)`}>
            <ellipse rx="20" ry={20 * open} fill="#FBFBF8" />
            {open > 0.2 && <circle r="10" fill="#0B0E14" />}
            <rect
              x="-17"
              y={-34 - look.browLift * 100}
              width="34"
              height="4"
              rx="2"
              fill="#0B0E14"
              transform={`rotate(${((side * look.browTilt * 180) / Math.PI) * -1} 0 ${-32 - look.browLift * 100})`}
            />
          </g>
        ))}
      </svg>
    </div>
  );
}
