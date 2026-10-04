import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { DEMO_SCENARIOS } from "../demo/scenarios";
import { PHASE_TO_CORE, useDemo } from "../demo/useDemo";
import { ConfirmCard } from "../ui/ConfirmCard";
import { director } from "../story/director";
import { STATE_LABEL } from "../core/labels";
import { Eyebrow, H2, Section } from "./Section";

const ease = [0.22, 1, 0.36, 1] as const;

/** Simulated end-to-end command: listen → think → act → confirm → done. Drives the real core. */
export function Demo() {
  const { view, start, answer } = useDemo();
  const panel = useRef<HTMLDivElement>(null);
  const core = PHASE_TO_CORE[view.phase];

  // The demo owns the core while it runs and is on screen. Scrolling away only hands the core
  // back to the page: a pending confirmation keeps its timeout and still resolves to No.
  const [inView, setInView] = useState(false);
  useEffect(() => {
    director.set({ override: inView ? core : null });
  }, [core, inView]);
  useEffect(() => {
    const el = panel.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting));
    io.observe(el);
    return () => {
      io.disconnect();
      director.set({ override: null });
    };
  }, []);

  const busy = view.phase !== "idle" && view.phase !== "done" && view.phase !== "cancelled";

  return (
    <Section id="demo" state="standby" anchor="right" label="Interactive demo" className="py-28 md:py-40">
      <div className="md:w-[52%]">
        <Eyebrow>Try it</Eyebrow>
        <H2>Say it once. Watch it happen.</H2>
        <p data-reveal className="mt-6 text-lg text-ink/70">
          Pick a command. JAS hears it, decides, works through the steps — and stops to ask before anything consequential.
        </p>

        <div data-reveal className="mt-8 flex flex-wrap gap-2" role="group" aria-label="Demo commands">
          {DEMO_SCENARIOS.map((s) => (
            <button
              key={s.id}
              onClick={() => start(s)}
              disabled={busy}
              data-testid={`demo-${s.id}`}
              className="px-4 py-2.5 rounded-full border border-white/12 text-sm text-ink hover:border-sun/60 hover:text-sun disabled:opacity-40 disabled:hover:border-white/12 disabled:hover:text-ink transition-colors"
            >
              {s.label}
            </button>
          ))}
        </div>

        <div ref={panel} className="glass mt-6 p-5 md:p-6 min-h-[300px]" data-testid="demo-panel">
          <div className="flex items-center justify-between text-xs text-muted">
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className={`size-2 rounded-full ${view.phase === "listening" ? "bg-alert animate-pulse" : "bg-white/20"}`}
              />
              {view.phase === "listening" ? "Mic on (simulated)" : "Mic off"}
            </span>
            <span className="rounded-full border border-white/10 px-2.5 py-0.5">Simulated demo · no mic · nothing is sent</span>
          </div>

          <p aria-live="polite" className="sr-only">
            {core ? STATE_LABEL[core] : ""}
          </p>

          {view.phase === "idle" && !view.heard ? (
            <p className="mt-10 text-center text-muted">Choose a command above to start.</p>
          ) : (
            <>
              <p className="mt-5 text-xl md:text-2xl font-display leading-snug" data-testid="demo-heard">
                {view.heard}
                {view.phase === "listening" && <span className="ml-1 inline-block w-0.5 h-6 align-middle bg-sun animate-pulse" />}
              </p>
              {view.phase === "thinking" && <p className="mt-4 text-sm text-muted">Choosing a tool…</p>}

              <ul className="mt-5 space-y-2.5" aria-label="Steps">
                <AnimatePresence initial={false}>
                  {view.steps.map((s) => (
                    <motion.li
                      key={s.label}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      className="flex items-center gap-3 text-[15px]"
                      data-status={s.status}
                    >
                      <StepIcon status={s.status} />
                      <span className={s.status === "pending" ? "text-muted" : "text-ink"}>{s.label}</span>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>

              <div className="mt-5">
                <AnimatePresence>
                  {view.phase === "confirming" && view.question && (
                    <ConfirmCard key="confirm" question={view.question} onAnswer={(yes) => answer(yes)} />
                  )}
                  {view.reply && view.phase !== "confirming" && (
                    <motion.p
                      key={view.reply}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4, ease }}
                      data-testid="demo-reply"
                      className={`text-lg ${view.phase === "cancelled" ? "text-muted" : "text-earth"}`}
                    >
                      “{view.reply}”
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            </>
          )}
        </div>
      </div>
    </Section>
  );
}

function StepIcon({ status }: { status: "pending" | "active" | "done" }) {
  if (status === "done")
    return (
      <span aria-label="done" className="grid place-items-center size-5 rounded-full bg-earth/20 text-earth">
        <svg viewBox="0 0 16 16" className="size-3" fill="none" stroke="currentColor" strokeWidth="2.2">
          <path d="M3.5 8.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  if (status === "active")
    return <span aria-label="in progress" className="size-5 rounded-full border-2 border-sun/80 animate-pulse" />;
  return <span aria-label="pending" className="size-5 rounded-full border border-white/20" />;
}
