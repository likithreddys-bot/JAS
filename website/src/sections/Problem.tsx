import { SCENARIOS } from "../content";
import { Eyebrow, H2, Section } from "./Section";

export function Problem() {
  return (
    <Section id="problem" state="thinking" anchor="hidden" label="The problem" className="py-28 md:py-40">
      <Eyebrow>The problem</Eyebrow>
      <H2 className="max-w-4xl">Work doesn't wait for you to get back to your desk.</H2>
      <p data-reveal className="mt-6 max-w-2xl text-lg text-ink/70">
        The same problem shows up in different clothes depending on who you are and where you happen to be.
      </p>
      <p data-reveal className="mt-3 text-sm text-muted">Illustrative scenarios — not client case studies.</p>

      <ul className="mt-14 grid gap-4 md:gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {SCENARIOS.map((s, i) => (
          <li key={s.name} data-reveal style={{ transitionDelay: `${i * 40}ms` }} className="glass group p-6 md:p-7 flex flex-col">
            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-sun/90">{s.condition}</p>
            <h3 className="mt-3 text-xl font-semibold">
              {s.name}
              <span className="ml-2 text-sm font-normal font-body text-muted">{s.role}</span>
            </h3>
            <p className="mt-3 text-[15px] leading-relaxed text-ink/70">{s.story}</p>
            <div className="mt-auto pt-5">
              <div className="h-px bg-white/8 mb-4" />
              <p className="flex gap-3 text-[15px] leading-relaxed text-ink">
                <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-full bg-earth shadow-[0_0_10px_rgb(70_199_176/0.7)]" />
                <span>
                  <span className="sr-only">With JAS: </span>
                  {s.solution}
                </span>
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}
