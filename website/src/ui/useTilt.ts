import { useEffect } from "react";

const MAX_DEG = 7;

/**
 * 3D tilt + gold sheen for any element marked data-tilt. One listener for the whole page.
 * Off for touch, reduced motion and "Pause motion" (body[data-paused]).
 */
export function useTilt(enabled: boolean) {
  useEffect(() => {
    if (!enabled || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    let active: HTMLElement | null = null;
    let raf = 0;
    const reset = (el: HTMLElement) => {
      el.style.transform = "";
      el.style.removeProperty("--mx");
      el.style.removeProperty("--my");
    };
    const onMove = (e: PointerEvent) => {
      const el = (e.target as Element | null)?.closest<HTMLElement>("[data-tilt]") ?? null;
      if (active && active !== el) reset(active);
      active = el;
      if (!el || document.body.dataset.paused) return;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width;
        const y = (e.clientY - r.top) / r.height;
        el.style.transform = `perspective(900px) rotateX(${(0.5 - y) * MAX_DEG}deg) rotateY(${(x - 0.5) * MAX_DEG}deg) translateZ(0)`;
        el.style.setProperty("--mx", `${x * 100}%`);
        el.style.setProperty("--my", `${y * 100}%`);
      });
    };
    const onLeave = () => active && reset(active);
    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", onLeave);
      if (active) reset(active);
    };
  }, [enabled]);
}
