import { CONTACT } from "../content";
import { Section } from "./Section";

export function Contact() {
  return (
    <>
      <Section id="contact" state="listening" anchor="hidden" label="Contact" className="py-32 md:py-48">
        <div className="glass relative overflow-hidden px-6 py-16 md:px-16 md:py-24 text-center">
          <div
            aria-hidden
            className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 size-[520px] rounded-full bg-sun/20 blur-[120px]"
          />
          <p className="relative text-xs font-medium uppercase tracking-[0.2em] text-sun">Leave the laptop at home</p>
          <h2 data-reveal className="relative mt-5 text-4xl md:text-6xl font-semibold leading-[1.05] text-balance">
            Your PC, one sentence away.
          </h2>
          <p data-reveal className="relative mx-auto mt-6 max-w-xl text-lg text-ink/70">
            VEM is a working system today. If you'd like a walkthrough, early access, or to talk about using it, write to{" "}
            {CONTACT.name.split(" ")[0]} directly.
          </p>
          <div data-reveal className="relative mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <a
              href={`mailto:${CONTACT.email}?subject=VEM%20%E2%80%94%20I'd%20like%20to%20know%20more`}
              className="px-7 py-4 rounded-full bg-sun text-bg font-medium hover:brightness-105 transition"
              data-testid="contact-cta"
            >
              Email {CONTACT.name}
            </a>
            <span className="text-sm text-muted break-all">{CONTACT.email}</span>
          </div>
        </div>
      </Section>
      <footer className="relative px-6 md:px-16 pt-12 pb-10 text-[13px] text-muted">
        <div className="mx-auto max-w-6xl border-t border-white/[0.08] pt-10">
          <div className="grid gap-8 sm:grid-cols-3">
            <FooterCol title="See it" links={[["#film", "The film"], ["#demo", "Try the demo"], ["#how", "How it works"], ["#states", "Every state"]]} />
            <FooterCol title="Trust" links={[["#trust", "Security"], ["#roadmap", "Limitations and roadmap"], ["#faq", "Questions"]]} />
            <div>
              <p className="font-medium text-ink">Contact</p>
              <p className="mt-3">{CONTACT.name}</p>
              <p className="mt-1 break-all select-all">{CONTACT.email}</p>
            </div>
          </div>
          <div className="mt-10 flex flex-col md:flex-row gap-3 md:items-center md:justify-between border-t border-white/[0.06] pt-6">
            <p>
              <span className="font-display text-ink font-semibold">VEM</span> (VEMMAI) · Built by {CONTACT.name} · © 2026
            </p>
            <p>No cookies. No trackers. No analytics. Fonts are self-hosted.</p>
          </div>
        </div>
      </footer>
    </>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <p className="font-medium text-ink">{title}</p>
      <ul className="mt-3 space-y-2">
        {links.map(([href, label]) => (
          <li key={href}>
            <a href={href} className="hover:text-ink transition-colors">
              {label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
