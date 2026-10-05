import { HIGHLIGHTS } from "../content";
import { Section } from "./Section";

/** "Highlights": big numbers, one fact each, in a tight grid. Every figure is from the documentation. */
export function Highlights() {
  return (
    <Section id="highlights" state="standby" anchor="hidden" label="Highlights" className="py-24 md:py-36">
      <h2 data-reveal className="text-center text-5xl md:text-7xl font-semibold tracking-[-0.04em]">
        Get the highlights.
      </h2>
      <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {HIGHLIGHTS.map((h) => (
          <li key={h.label} data-reveal data-tilt className="rounded-[28px] bg-coal border border-ink/[0.06] p-8 md:p-10 min-h-[15rem] flex flex-col">
            <p className="font-display text-6xl md:text-7xl font-semibold tracking-[-0.05em] gold-text">{h.big}</p>
            <p className="mt-4 text-xl font-display font-semibold leading-snug text-ink">{h.label}</p>
            <p className="mt-auto pt-6 text-sm text-muted">{h.note}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}
