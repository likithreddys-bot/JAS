import { useLayoutEffect, useRef } from "react";
import { gsap } from "gsap";
import { THESIS } from "../content";
import { Section } from "./Section";
import { useReducedMotion } from "../core/useReducedMotion";

/** One idea, revealed word by word as you scroll. */
export function Thesis() {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  useLayoutEffect(() => {
    if (reduced || !ref.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        ".thesis-word",
        { opacity: 0.12 },
        {
          opacity: 1,
          stagger: 0.08,
          ease: "none",
          scrollTrigger: { trigger: ref.current, start: "top 75%", end: "bottom 55%", scrub: true },
        },
      );
    }, ref);
    return () => ctx.revert();
  }, [reduced]);

  const words = (s: string, cls: string) =>
    s.split(" ").map((w, i) => (
      <span key={i} className={`thesis-word inline-block mr-[0.25em] ${cls}`}>
        {w}
      </span>
    ));

  return (
    <Section id="thesis" state="standby" anchor="hidden" label="The idea" className="py-32 md:py-48">
      <div ref={ref} className="max-w-5xl">
        <p className="text-3xl sm:text-4xl md:text-6xl font-display font-medium leading-[1.12] tracking-tight text-muted">
          {words(THESIS.before, "line-through decoration-alert/60 decoration-2")}
        </p>
        <p className="mt-6 text-4xl sm:text-5xl md:text-7xl font-display font-semibold leading-[1.05] tracking-tight">
          {words(THESIS.after, "text-sun")}
        </p>
        <p data-reveal className="mt-10 max-w-2xl text-lg text-ink/70">
          The information and the tools you need already exist — on a machine that is reachable in principle, but not in
          the moment. That gap is exactly what JAS closes.
        </p>
      </div>
    </Section>
  );
}
