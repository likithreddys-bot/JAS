import { EXAMPLES } from "../content";
import { Eyebrow, H2, Section } from "./Section";

export function Examples() {
  return (
    <Section id="say" state="responding" anchor="right" label="What you can say" className="py-28 md:py-40">
      <div className="md:w-[56%]">
        <Eyebrow>What you can actually say</Eyebrow>
        <H2>Fast for the common case. Careful for the consequential one.</H2>
        <p data-reveal className="mt-6 text-lg text-ink/70">
          Each line maps to a tool that is registered and callable in the running system today.
        </p>
        <div data-reveal className="mt-6 flex flex-wrap gap-4 text-sm">
          <RiskBadge risk="instant" /> <span className="text-muted -ml-2">Read-only or harmless — answered immediately</span>
        </div>
        <div data-reveal className="mt-2 flex flex-wrap gap-4 text-sm">
          <RiskBadge risk="asks" /> <span className="text-muted -ml-2">Sends, shares, moves or remembers — confirmed first</span>
        </div>

        <ul className="mt-10 divide-y divide-ink/8 border-y border-ink/8">
          {EXAMPLES.map((e) => (
            <li key={e.say} data-reveal className="py-5 grid gap-2 sm:grid-cols-[1fr_auto] sm:gap-6">
              <div>
                <p className="text-lg font-display">“{e.say}”</p>
                <p className="mt-1.5 text-[15px] text-ink/70">{e.happens}</p>
              </div>
              <div className="sm:pt-1">
                <RiskBadge risk={e.risk} />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}

export function RiskBadge({ risk }: { risk: "instant" | "asks" }) {
  return risk === "asks" ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-sun/12 text-sun px-3 py-1 text-xs font-medium whitespace-nowrap">
      <span aria-hidden className="size-1.5 rounded-full bg-sun" /> Asks first
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-earth/12 text-earth px-3 py-1 text-xs font-medium whitespace-nowrap">
      <span aria-hidden className="size-1.5 rounded-full bg-earth" /> Instant
    </span>
  );
}
