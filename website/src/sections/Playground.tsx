import { useEffect, useRef, useState } from "react";
import { CORE_STATES, STATE_KANJI, STATE_LABEL, type CoreState } from "../core/labels";
import { director } from "../story/director";
import { Eyebrow, H2, Section } from "./Section";

const HOW: Record<CoreState, string> = {
  standby: "The ink circle breathes slowly on the paper.",
  listening: "Turns gold; ripples spread out like on still water.",
  thinking: "The circle turns while three drops of gold travel round it.",
  executing: "Matcha green; a gold arc tracks the work.",
  confirming: "Deepens to amber and waits for your yes.",
  responding: "Pulses with its own voice.",
  success: "A vermilion 済 seal is pressed in — only after a real success.",
  error: "Turns vermilion, shudders once, and it tells you why.",
  paused: "The ink fades and stops. One still dot remains.",
};

/** Every state the core can be in. Picking one takes over the page's core while in view. */
export function Playground() {
  const [pick, setPick] = useState<CoreState | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    director.set({ override: pick });
  }, [pick]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) {
        setPick(null);
        director.set({ override: null });
      }
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <Section id="states" state="standby" anchor="center" label="States" className="min-h-[100svh] flex flex-col">
      <div ref={ref} className="pt-28 md:pt-32 text-center">
        <Eyebrow>九つの気分 · Nine moods</Eyebrow>
        <H2 className="mx-auto max-w-3xl !text-3xl md:!text-5xl">You'll know what Luffy is doing without reading a word.</H2>
      </div>
      <div className="h-[42svh] md:h-[46svh]" aria-hidden />
      <div className="mx-auto max-w-3xl pb-16">
        <p aria-live="polite" className="text-center min-h-[3.5rem] text-ink/75" data-testid="playground-desc">
          {pick ? (
            <>
              <span className="text-ink font-medium">{STATE_LABEL[pick]}.</span> {HOW[pick]}
            </>
          ) : (
            "Pick a state."
          )}
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2" role="group" aria-label="Core states">
          {CORE_STATES.map((s) => (
            <button
              key={s}
              data-state={s}
              onClick={() => setPick(s)}
              aria-pressed={pick === s}
              className={`flex items-baseline gap-2 px-4 py-2 border text-sm capitalize transition-colors ${
                pick === s ? "border-alert text-ink bg-bg" : "border-ink/12 text-muted hover:text-ink bg-bg/60"
              }`}
            >
              <span className="font-display font-bold text-base text-ink" aria-hidden>{STATE_KANJI[s]}</span>
              {s}
            </button>
          ))}
        </div>
      </div>
    </Section>
  );
}
