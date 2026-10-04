import { useRef, type ReactNode } from "react";
import type { CoreState } from "../core/labels";
import { useCoreSection, type Anchor } from "../story/director";

interface SectionProps {
  id?: string;
  state: CoreState;
  anchor: Anchor;
  className?: string;
  label?: string;
  children: ReactNode;
}

/** A page section that tells the core what to be while it is on screen. */
export function Section({ id, state, anchor, className = "", label, children }: SectionProps) {
  const ref = useRef<HTMLElement>(null);
  useCoreSection(ref, state, anchor);
  return (
    <section id={id} ref={ref} aria-label={label} className={`relative px-6 md:px-16 ${className}`}>
      <div className="mx-auto w-full max-w-6xl">{children}</div>
    </section>
  );
}

export function Eyebrow({ children, tone = "sun" }: { children: ReactNode; tone?: "sun" | "earth" | "muted" }) {
  const c = tone === "sun" ? "text-sun" : tone === "earth" ? "text-earth" : "text-muted";
  return <p className={`text-xs font-medium uppercase tracking-[0.2em] ${c}`}>{children}</p>;
}

export function H2({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <h2 data-reveal className={`mt-4 text-4xl md:text-6xl font-semibold leading-[1.05] text-balance ${className}`}>
      {children}
    </h2>
  );
}
