import { LIMITATIONS, ROADMAP } from "../content";
import { Eyebrow, H2, Section } from "./Section";

export function Honest() {
  return (
    <Section id="roadmap" state="standby" anchor="hidden" label="Limitations and roadmap" className="py-28 md:py-40">
      <Eyebrow tone="muted">Honest by design</Eyebrow>
      <H2 className="max-w-4xl">What Luffy can't do yet — and the real path forward.</H2>
      <p data-reveal className="mt-6 max-w-2xl text-lg text-ink/70">
        An honest account of the limits is as important as the list of features. These are real and current, not hedging.
      </p>

      <ul className="mt-12 grid gap-3 sm:grid-cols-2">
        {LIMITATIONS.map((l) => (
          <li key={l.what} data-reveal className="rounded-[20px] border border-ink/8 bg-ink/[0.02] p-6">
            <h3 className="text-[17px] font-semibold">{l.what}</h3>
            <p className="mt-2 text-[15px] leading-relaxed text-ink/70">{l.why}</p>
          </li>
        ))}
      </ul>

      <div className="mt-20 grid gap-4 md:grid-cols-3">
        <Column title="Available now" tone="earth" items={ROADMAP.now} />
        <Column title="In development" tone="sun" items={ROADMAP.next} />
        <Column title="Future" tone="muted" items={ROADMAP.later} />
      </div>
    </Section>
  );
}

function Column({ title, tone, items }: { title: string; tone: "earth" | "sun" | "muted"; items: string[] }) {
  const dot = tone === "earth" ? "bg-earth" : tone === "sun" ? "bg-sun" : "bg-muted";
  return (
    <div data-reveal data-tilt className="glass p-6">
      <h3 className="flex items-center gap-2.5 text-sm font-medium uppercase tracking-[0.16em] text-ink/80">
        <span aria-hidden className={`size-2 rounded-full ${dot}`} />
        {title}
      </h3>
      <ul className="mt-5 space-y-3">
        {items.map((i) => (
          <li key={i} className="text-[15px] leading-relaxed text-ink/75">
            {i}
          </li>
        ))}
      </ul>
    </div>
  );
}
