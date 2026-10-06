import { useLayoutEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { Canvas, advance, useThree } from "@react-three/fiber";
import type { PerspectiveCamera } from "three";
import { JasCore } from "../src/core/JasCore";
import { CORE_STATES, type CoreState } from "../src/core/labels";

const q = new URLSearchParams(location.search);
const state = (CORE_STATES as readonly string[]).includes(q.get("state") ?? "") ? (q.get("state") as CoreState) : "standby";
const size = Number(q.get("size") ?? 1024);
const bg = q.get("bg") ?? "transparent";
document.body.style.background = bg === "transparent" ? "transparent" : bg;

const FOV = 35;
const FIT = 5.6; // world units visible: the whole glow (radius 2.7) fits, so nothing is cut at the edges

function Camera() {
  const camera = useThree((s) => s.camera) as PerspectiveCamera;
  useLayoutEffect(() => {
    camera.position.set(0, 0, FIT / 2 / Math.tan(((FOV / 2) * Math.PI) / 180));
    camera.updateProjectionMatrix();
  }, [camera]);
  return null;
}

declare global {
  interface Window {
    __frame: (t: number) => void;
    __ready: boolean;
  }
}

function Studio() {
  const clock = useRef(0);
  // Ready only once the canvas exists: before that, advance() has nothing to render.
  const onCreated = () => {
    window.__frame = (t: number) => {
      clock.current = t;
      advance(performance.now());
    };
    window.__ready = true;
  };
  return (
    <div style={{ width: size, height: size }}>
      <Canvas
        flat
        frameloop="never"
        dpr={1}
        camera={{ fov: FOV, position: [0, 0, 7] }}
        gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }}
        onCreated={onCreated}
      >
        <Camera />
        <JasCore state={state} clockRef={clock} />
      </Canvas>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<Studio />);
