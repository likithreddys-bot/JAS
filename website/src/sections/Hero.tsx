import { HERO, HERO_LOOP_SRC } from "../content";
import { Section } from "./Section";

/** Centred, product-page hero: one line of name, one huge statement, the orb beneath it. */
export function Hero() {
  return (
    <Section id="top" state="standby" anchor="hero" label="Introduction" className="min-h-[100svh]">
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
      <div className="pt-28 md:pt-32 text-center">
        <p className="hero-in font-display text-xl md:text-2xl font-semibold text-ink" style={{ animationDelay: "80ms" }}>
          JAS
        </p>
        <h1 className="mt-3 font-display font-semibold tracking-[-0.045em] leading-[0.95] text-[clamp(3rem,8.4vw,7.5rem)]">
          <span className="hero-in block" style={{ animationDelay: "180ms" }}>
            {HERO.title[0]}
          </span>
          {/* Fade-in and gold shimmer are separate animations, so they sit on separate elements. */}
          <span className="hero-in block" style={{ animationDelay: "320ms" }}>
            <span className="gold-text">{HERO.title[2]}</span>
          </span>
        </h1>
      </div>
      {/* The orb lives in the page-wide canvas; this is the space it sits in. */}
      <div className="h-[40svh] md:h-[44svh]" aria-hidden />
      <div className="text-center">
        <p
          className="hero-in mx-auto max-w-2xl text-lg md:text-[21px] leading-relaxed text-ink/70"
          style={{ animationDelay: "460ms" }}
        >
          {HERO.body}
        </p>
        <div className="hero-in mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3" style={{ animationDelay: "600ms" }}>
          <a href="#demo" className="px-6 py-3 rounded-full bg-sun text-bg font-medium hover:brightness-105 transition">
            Try the demo
          </a>
          <a href="#film" className="text-sun text-lg hover:underline underline-offset-4">
            Watch the film <span aria-hidden>›</span>
          </a>
        </div>
      </div>
      <ul className="mt-10 pb-14 flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-muted">
        {HERO.chips.map((c) => (
          <li key={c} className="flex items-center gap-2">
            <span aria-hidden className="size-1.5 rounded-full bg-earth" />
            {c}
          </li>
        ))}
      </ul>
    </Section>
  );
}
