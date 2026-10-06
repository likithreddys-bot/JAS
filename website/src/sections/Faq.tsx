import { FAQ } from "../content";
import { Section } from "./Section";

/** Plain questions, plain answers. Native <details>, so it works without JavaScript and with a keyboard. */
export function Faq() {
  return (
    <Section id="faq" state="standby" anchor="hidden" label="Questions" className="py-24 md:py-36">
      <h2 data-reveal className="text-center text-5xl md:text-7xl font-semibold tracking-[-0.04em]">
        Questions, answered.
      </h2>
      <div className="mx-auto mt-14 max-w-3xl divide-y divide-white/[0.08] border-y border-white/[0.08]">
        {FAQ.map((f) => (
          <details key={f.q} className="group py-6" data-testid="faq-item">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-6 text-xl md:text-2xl font-display font-semibold tracking-tight [&::-webkit-details-marker]:hidden">
              {f.q}
              <span
                aria-hidden
                className="grid size-8 shrink-0 place-items-center rounded-full border border-white/15 text-sun transition-transform duration-300 group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <p className="mt-4 max-w-2xl text-[17px] leading-relaxed text-ink/70">{f.a}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}
