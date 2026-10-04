import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { PerformanceMonitor } from "@react-three/drei";
import type { Group, PerspectiveCamera } from "three";
import { JasCore } from "./JasCore";
import { CoreFallback } from "./CoreFallback";
import { GoldDust } from "./GoldDust";
import { useReducedMotion } from "./useReducedMotion";
import { effectiveState, useDirector, type Anchor } from "../story/director";

const FOV = 35;
const FIT = 4.2;

function CameraRig() {
  const camera = useThree((s) => s.camera) as PerspectiveCamera;
  const { width, height } = useThree((s) => s.size);
  useLayoutEffect(() => {
    const aspect = width / Math.max(1, height);
    const half = FIT / 2 / Math.min(1, aspect);
    camera.position.set(0, 0, half / Math.tan(((FOV / 2) * Math.PI) / 180));
    camera.updateProjectionMatrix();
  }, [camera, width, height]);
  return null;
}

/** Target placement for each anchor, in world units relative to the visible viewport. */
function placement(anchor: Exclude<Anchor, "hidden">, w: number, h: number, narrow: boolean) {
  if (narrow) {
    if (anchor === "hero") return { x: 0, y: h * 0.28, s: 0.74 };
    if (anchor === "center") return { x: 0, y: 0, s: 0.85 };
    return { x: 0, y: h * 0.3, s: 0.55 };
  }
  switch (anchor) {
    case "hero":
      return { x: w * 0.24, y: 0, s: 0.95 };
    case "center":
      return { x: 0, y: -h * 0.02, s: 0.72 };
    case "left":
    case "how":
      return { x: -w * 0.26, y: 0, s: 0.85 };
    case "right":
      return { x: w * 0.26, y: 0, s: 0.85 };
  }
}

/** Glides the core between anchors (transform only, damped ~600 ms). */
function Mover({ anchor, narrow, reduced, children }: { anchor: Anchor; narrow: boolean; reduced: boolean; children: ReactNode }) {
  const g = useRef<Group>(null);
  const viewport = useThree((s) => s.viewport);
  const invalidate = useThree((s) => s.invalidate);
  const first = useRef(true);
  useEffect(() => invalidate(), [anchor, invalidate]);
  useFrame((_, dt) => {
    if (!g.current) return;
    // "hidden" shrinks the core away where it stands instead of flying it across the text.
    const p =
      anchor === "hidden"
        ? { x: g.current.position.x, y: g.current.position.y, s: 0.001 }
        : placement(anchor, viewport.width, viewport.height, narrow);
    if (first.current) {
      // Entrance: the core materialises in place, unless motion is reduced.
      g.current.position.set(p.x, p.y, 0);
      g.current.scale.setScalar(reduced ? p.s : 0.001);
      first.current = false;
    }
    const k = reduced ? 1 : 1 - Math.exp(-(g.current.scale.x < p.s * 0.6 ? 2.6 : 6) * Math.min(dt, 0.05));
    g.current.position.x += (p.x - g.current.position.x) * k;
    g.current.position.y += (p.y - g.current.position.y) * k;
    const s = g.current.scale.x + (p.s - g.current.scale.x) * k;
    g.current.scale.setScalar(s);
  });
  return <group ref={g}>{children}</group>;
}

function hasWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
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

/**
 * The one core for the whole page: a fixed, full-viewport, click-through canvas behind the
 * content. Falls back to a 2D core when WebGL is missing or the device can't hold frame rate.
 */
export default function CoreLayer() {
  const d = useDirector();
  const state = effectiveState(d);
  const reducedPref = useReducedMotion();
  const reduced = reducedPref || d.paused;
  const narrow = useNarrow();
  const [dpr, setDpr] = useState(1.75);
  const [fallback, setFallback] = useState(() => !hasWebGL());

  // On phones there is no side column: the core steps out of side-anchored sections
  // rather than sitting behind their text.
  const offstage = d.anchor === "hidden" || (narrow && (d.anchor === "left" || d.anchor === "right"));
  const [coreVisible, setCoreVisible] = useState(true);
  useEffect(() => setCoreVisible(!offstage), [offstage]);

  return (
    <div
      aria-hidden
      className="fixed inset-0 z-0 pointer-events-none transition-opacity duration-700"
      data-core-visible={coreVisible}
      data-testid="core-layer"
      data-core-state={state}
      data-core-anchor={d.anchor}
    >
      {fallback ? (
        <div className="transition-opacity duration-500" style={{ opacity: offstage ? 0 : 1 }}>
          <CoreFallback state={state} anchor={d.anchor} narrow={narrow} />
        </div>
      ) : (
        <Canvas
          flat
          dpr={[1, dpr]}
          frameloop={reduced ? "demand" : "always"}
          camera={{ fov: FOV, position: [0, 0, 7] }}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        >
          {/* Measured, not guessed: drop resolution if fps falls, go 2D if it stays low. */}
          <PerformanceMonitor
            bounds={() => [40, 70]}
            flipflops={3}
            onDecline={() => setDpr(1)}
            onFallback={() => setFallback(true)}
          />
          <CameraRig />
          <GoldDust reduced={reduced} dim={narrow ? 0.6 : 1} />
          <Mover anchor={offstage ? "hidden" : d.anchor} narrow={narrow} reduced={reduced}>
            <JasCore state={state} reduced={reduced} />
          </Mover>
        </Canvas>
      )}
    </div>
  );
}
