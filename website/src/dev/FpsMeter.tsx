import { useEffect, useState } from "react";

/** Dev-only frame-rate readout, averaged over one second. */
export function FpsMeter() {
  const [fps, setFps] = useState(0);
  useEffect(() => {
    let frames = 0;
    let last = performance.now();
    let id = 0;
    const loop = (now: number) => {
      frames++;
      if (now - last >= 1000) {
        setFps(Math.round((frames * 1000) / (now - last)));
        frames = 0;
        last = now;
      }
      id = requestAnimationFrame(loop);
    };
    id = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(id);
  }, []);
  return (
    <div data-testid="fps" className="fixed top-4 right-4 font-mono text-xs text-muted glass px-3 py-1.5">
      {fps} fps
    </div>
  );
}
