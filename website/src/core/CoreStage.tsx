import { useLayoutEffect, type RefObject } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import type { PerspectiveCamera } from "three";
import { JasCore } from "./JasCore";
import type { CoreState } from "./states";
import { useReducedMotion } from "./useReducedMotion";

const FOV = 35;
/** World-space extent that must always fit: halo radius is 2.0, so 4.2 leaves a margin. */
const FIT = 4.2;

/** Moves the camera back on tall/narrow canvases so the halo never clips at the edge. */
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

interface CoreStageProps {
  state: CoreState;
  className?: string;
  levelRef?: RefObject<number>;
}

/** A self-contained canvas that renders the JAS core. Transparent: the page shows through. */
export function CoreStage({ state, className, levelRef }: CoreStageProps) {
  const reduced = useReducedMotion();
  return (
    <Canvas
      className={className}
      flat
      dpr={[1, 1.75]}
      frameloop={reduced ? "demand" : "always"}
      camera={{ fov: FOV, position: [0, 0, 7] }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      aria-hidden
    >
      <CameraRig />
      <JasCore state={state} reduced={reduced} levelRef={levelRef} />
    </Canvas>
  );
}
