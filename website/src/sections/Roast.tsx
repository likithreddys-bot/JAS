import { useEffect, useRef, useState } from "react";
import { ROAST } from "../content";
import { useReducedMotion } from "../core/useReducedMotion";
import { Section } from "./Section";

/** "Not Siri. Not Gemini. Just VEM." Four 3D cards flip from the usual assistant to VEM. */
export function Roast() {
  const reduced = useReducedMotion();
  const grid = useRef<HTMLUListElement>(null);
  const [flipped, setFlipped] = useState<boolean[]>(() => ROAST.cards.map(() => false));

  // Cards flip on their own, one after another, the first time they scroll into view.
  useEffect(() => {
    const el = grid.current;
    if (!el || reduced) return;
    const timers: number[] = [];
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        ROAST.cards.forEach((_, i) =>
          timers.push(window.setTimeout(() => setFlipped((f) => f.map((v, j) => (j === i ? true : v))), 700 + i * 380)),
        );
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      timers.forEach(clearTimeout);
    };
  }, [reduced]);

  const toggle = (i: number) => setFlipped((f) => f.map((v, j) => (j === i ? !v : v)));

  return (
    <Section id="not-siri" state="responding" anchor="hidden" label="Why VEM" className="py-28 md:py-40">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted">{ROAST.eyebrow}</p>
      <h2 className="mt-5 text-5xl md:text-7xl lg:text-8xl font-semibold leading-[0.95] tracking-[-0.035em]">
        <span data-reveal className="block text-ink/45 line-through decoration-ink/30 decoration-[3px]">
          {ROAST.title[0]}
        </span>
        <span data-reveal className="block text-ink/45 line-through decoration-ink/30 decoration-[3px]">
          {ROAST.title[1]}
        </span>
        <span data-reveal className="block gold-text">
          {ROAST.title[2]}
        </span>
      </h2>
      <p data-reveal className="mt-8 max-w-2xl text-lg md:text-xl text-ink/70">
        {ROAST.body}
      </p>

      <ul ref={grid} className="mt-14 grid gap-5 sm:grid-cols-2" aria-label="The usual assistant versus VEM">
        {ROAST.cards.map((c, i) => (
          <li key={c.them} className="flip-scene">
            <button
              type="button"
              onClick={() => toggle(i)}
              aria-pressed={flipped[i]}
              aria-label={`The usual assistant: “${c.them}” VEM: ${c.jas}`}
              className={`flip-card ${flipped[i] ? "is-flipped" : ""} ${reduced ? "is-static" : ""}`}
            >
              <span className="flip-face flip-front glass" aria-hidden>
                <span className="text-[11px] uppercase tracking-[0.18em] text-muted">The usual assistant</span>
                <span className="mt-4 block text-2xl md:text-[1.7rem] font-display leading-snug text-ink/55">
                  “{c.them}”
                </span>
                <span className="mt-auto pt-6 text-xs text-muted">Tap to hand it to VEM →</span>
              </span>
              <span className="flip-face flip-back glass" aria-hidden>
                <span className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-sun">
                  <span className="size-2 rounded-full bg-sun shadow-[0_0_12px_rgb(232_190_118/0.9)]" /> VEM
                </span>
                <span className="mt-4 block text-xl md:text-2xl font-display leading-snug text-ink">{c.jas}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>

      <p data-reveal className="mt-10 max-w-3xl text-[15px] leading-relaxed text-muted">
        {ROAST.disclosure}
      </p>
    </Section>
  );
}
