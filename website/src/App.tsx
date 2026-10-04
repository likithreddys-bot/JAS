import { lazy, Suspense, useLayoutEffect } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Nav } from "./sections/Nav";
import { Hero } from "./sections/Hero";
import { Thesis } from "./sections/Thesis";
import { Problem } from "./sections/Problem";
import { Demo } from "./sections/Demo";
import { HowItWorks } from "./sections/HowItWorks";
import { Examples } from "./sections/Examples";
import { Capabilities } from "./sections/Capabilities";
import { Trust } from "./sections/Trust";
import { Honest } from "./sections/Honest";
import { Playground } from "./sections/Playground";
import { Contact } from "./sections/Contact";
import { FpsMeter } from "./dev/FpsMeter";
import { useReducedMotion } from "./core/useReducedMotion";
import { STATE_LABEL } from "./core/labels";
import { effectiveState, useDirector } from "./story/director";

// three.js is ~800 kB: load it after the page has painted.
const CoreLayer = lazy(() => import("./core/CoreLayer"));

/** `?dev` shows the fps meter, in any build. */
const DEV = new URLSearchParams(location.search).has("dev");

export default function App() {
  const reduced = useReducedMotion();
  const d = useDirector();

  // Gentle reveal for anything marked data-reveal. Transform + opacity only.
  useLayoutEffect(() => {
    if (reduced) return;
    const ctx = gsap.context(() => {
      ScrollTrigger.batch("[data-reveal]", {
        start: "top 90%",
        once: true,
        onEnter: (els) =>
          gsap.fromTo(els, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.9, ease: "expo.out", stagger: 0.06 }),
      });
    });
    // Fonts and lazy images change layout: re-measure once they land.
    document.fonts?.ready.then(() => ScrollTrigger.refresh());
    window.addEventListener("load", () => ScrollTrigger.refresh(), { once: true });
    return () => ctx.revert();
  }, [reduced]);

  return (
    <>
      <a
        href="#demo"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] glass px-4 py-2"
      >
        Skip to the demo
      </a>
      <Suspense fallback={null}>
        <CoreLayer />
      </Suspense>
      <p className="sr-only" aria-live="polite">
        JAS core: {STATE_LABEL[effectiveState(d)]}
      </p>
      <Nav />
      <main className="relative z-10">
        <Hero />
        <Thesis />
        <Problem />
        <Demo />
        <HowItWorks />
        <Examples />
        <Capabilities />
        <Trust />
        <Honest />
        <Playground />
        <Contact />
      </main>
      {DEV && <FpsMeter />}
    </>
  );
}
