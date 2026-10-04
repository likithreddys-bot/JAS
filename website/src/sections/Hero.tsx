import { HERO, HERO_LOOP_SRC, CONTACT } from "../content";
import { Section } from "./Section";

export function Hero() {
  return (
    <Section id="top" state="standby" anchor="hero" label="Introduction" className="min-h-[100svh] flex items-center">
      {HERO_LOOP_SRC && (
        <video
          className="absolute inset-0 -z-10 h-full w-full object-cover opacity-30"
          src={HERO_LOOP_SRC}
          autoPlay
          muted
          loop
          playsInline
          aria-hidden
        />
      )}
      <div className="pt-[46svh] md:pt-24 pb-16 md:w-[58%]">
        <p className="hero-in text-xs font-medium uppercase tracking-[0.2em] text-sun" style={{ animationDelay: "100ms" }}>
          {HERO.eyebrow}
        </p>
        <h1 className="mt-5 text-[clamp(2.75rem,6vw,5.25rem)] font-semibold leading-[0.98] tracking-[-0.035em]">
          {HERO.title.map((line, i) => (
            <span key={line} className="hero-in block whitespace-nowrap" style={{ animationDelay: `${200 + i * 120}ms` }}>
              {i === HERO.title.length - 1 ? <span className="gold-text">{line}</span> : line}
            </span>
          ))}
        </h1>
        <p className="hero-in mt-7 max-w-xl text-lg md:text-xl text-ink/75 leading-relaxed" style={{ animationDelay: "600ms" }}>
          {HERO.body}
        </p>
        <div className="hero-in mt-9 flex flex-wrap gap-3" style={{ animationDelay: "720ms" }}>
          <a href="#demo" className="px-6 py-3.5 rounded-full bg-sun text-bg font-medium hover:brightness-105 transition">
            Try the demo
          </a>
          <a
            href={`mailto:${CONTACT.email}?subject=JAS`}
            className="px-6 py-3.5 rounded-full border border-white/15 text-ink hover:bg-white/5 transition"
          >
            Talk to {CONTACT.name.split(" ")[0]}
          </a>
        </div>
        <ul className="hero-in mt-10 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted" style={{ animationDelay: "840ms" }}>
          {HERO.chips.map((c) => (
            <li key={c} className="flex items-center gap-2">
              <span aria-hidden className="size-1.5 rounded-full bg-earth" />
              {c}
            </li>
          ))}
        </ul>
      </div>
      <a
        href="#thesis"
        aria-label="Scroll to continue"
        className="hidden md:flex absolute bottom-8 left-1/2 -translate-x-1/2 flex-col items-center gap-2 text-xs text-muted"
      >
        <span className="scroll-cue block h-10 w-px bg-gradient-to-b from-transparent via-muted to-transparent" />
      </a>
    </Section>
  );
}
