import { useLayoutEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { FLOW } from "../content";
import type { CoreState } from "../core/labels";
import { director } from "../story/director";
import { useReducedMotion } from "../core/useReducedMotion";
import { Eyebrow } from "./Section";

const STEP_STATE: CoreState[] = ["listening", "listening", "thinking", "confirming", "executing"];

/** Pinned while you scroll through the five steps; the core acts out each one. */
export function HowItWorks() {
  const root = useRef<HTMLElement>(null);
  const [step, setStep] = useState(0);
  const reduced = useReducedMotion();

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const st = ScrollTrigger.create({
      trigger: el,
      start: "top top",
      end: () => `+=${window.innerHeight * 3}`,
      pin: true,
      onUpdate: (self) => {
        const i = Math.min(FLOW.length - 1, Math.floor(self.progress * FLOW.length));
        setStep(i);
        director.set({ section: self.progress > 0.985 ? "success" : STEP_STATE[i], anchor: "how" });
      },
      onToggle: (self) => {
        // Claim the core on entry, including a jump straight to the pin start (no scroll update yet).
        if (self.isActive) {
          const i = Math.min(FLOW.length - 1, Math.floor(self.progress * FLOW.length));
          director.set({ section: STEP_STATE[i], anchor: "how" });
        }
      },
    });
    // Claim the core while the section scrolls up into place, before the pin starts.
    const approach = ScrollTrigger.create({
      trigger: el,
      start: "top 70%",
      end: "top top",
      onToggle: (self) => {
        if (self.isActive) director.set({ section: STEP_STATE[0], anchor: "how" });
      },
    });
    return () => {
      st.kill();
      approach.kill();
    };
  }, []);

  useLayoutEffect(() => {
    if (reduced) return;
    gsap.fromTo(".how-active", { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.45, ease: "expo.out" });
  }, [step, reduced]);

  return (
    <section ref={root} id="how" aria-label="How it works" className="relative h-[100svh] px-6 md:px-16 overflow-hidden">
      <div className="mx-auto max-w-6xl h-full flex items-center">
        <div className="w-full md:ml-auto md:w-[50%] pt-[30svh] md:pt-0">
          <Eyebrow>How a command flows</Eyebrow>
          <h2 className="mt-4 text-3xl md:text-5xl font-semibold leading-tight">Five steps. In order. Every time.</h2>

          <ol className="mt-8 flex gap-1.5" aria-hidden>
            {FLOW.map((_, i) => (
              <li key={i} className="h-1 flex-1 rounded-full bg-white/10 overflow-hidden">
                <span
                  className="block h-full bg-sun origin-left transition-transform duration-500"
                  style={{ transform: `scaleX(${i <= step ? 1 : 0})` }}
                />
              </li>
            ))}
          </ol>

          <ol className="mt-8 space-y-3">
            {FLOW.map((f, i) => (
              <li
                key={f.title}
                aria-current={i === step ? "step" : undefined}
                className={`glass p-5 transition-colors duration-500 ${i === step ? "" : "hidden md:block !bg-transparent"}`}
              >
                <div className="flex items-baseline gap-4">
                  <span className={`font-mono text-sm ${i <= step ? "text-sun" : "text-muted"}`}>0{i + 1}</span>
                  <div>
                    <h3 className={`text-lg md:text-xl font-semibold ${i === step ? "text-ink" : "text-ink/55"}`}>{f.title}</h3>
                    {i === step && <p className="how-active mt-2 text-ink/70 leading-relaxed">{f.body}</p>}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
