import { useLayoutEffect, useRef } from "react";
import { gsap } from "gsap";
import { HERO, HERO_LOOP_SRC } from "../content";
import { useReducedMotion } from "../core/useReducedMotion";
import { Section } from "./Section";

/** Centred hero: the name, one large statement, the ensō beneath it; ルフィ runs down the side in brush script. */
export function Hero() {
  const copy = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  // As the page scrolls, the headline drifts up and fades while the circle holds its place.
  useLayoutEffect(() => {
    if (reduced || !copy.current) return;
    const tween = gsap.to(copy.current, {
      yPercent: -35,
      opacity: 0,
      ease: "none",
      scrollTrigger: { trigger: "#top", start: "top top", end: "45% top", scrub: true },
    });
    return () => {
      tween.scrollTrigger?.kill();
      tween.kill();
    };
  }, [reduced]);
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
      {/* Tategaki: the name written top to bottom, in brush script, down the left of the sheet. */}
      <div
        aria-hidden
        className="hero-in tate pointer-events-none absolute left-2 md:left-6 top-24 md:top-28 hidden sm:flex items-start gap-4 font-brush text-[clamp(3.5rem,7vw,6.5rem)] leading-none text-ink"
        style={{ animationDelay: "40ms" }}
      >
        ルフィ
        <span className="font-display text-[13px] tracking-[0.5em] text-muted">あなたの相棒</span>
      </div>
      <div ref={copy} className="pt-28 md:pt-32 text-center">
        <p className="hero-in flex items-center justify-center gap-3 font-display text-xl md:text-2xl font-bold text-ink" style={{ animationDelay: "80ms" }}>
          <span aria-hidden className="seal h-12 w-7 text-[13px]">ルフィ</span>
          Luffy
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
      {/* The ensō lives in the page-wide canvas; this is the space it sits in. */}
      <div data-core-slot className="h-[40svh] md:h-[44svh]" aria-hidden />
      <div className="text-center">
        <p
          className="hero-in mx-auto max-w-2xl text-lg md:text-[21px] leading-relaxed text-ink/70"
          style={{ animationDelay: "460ms" }}
        >
          {HERO.body}
        </p>
        <div className="hero-in mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3" style={{ animationDelay: "600ms" }}>
          <a href="#demo" className="px-6 py-3 bg-ink text-bg font-medium tracking-[0.08em] hover:bg-ink/85 transition">
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
            <span aria-hidden className="size-1.5 rotate-45 bg-alert" />
            {c}
          </li>
        ))}
      </ul>
    </Section>
  );
}
