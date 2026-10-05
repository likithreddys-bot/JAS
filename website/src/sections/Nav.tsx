import { NAV, CONTACT } from "../content";
import { director, useDirector } from "../story/director";

/** A slim, full-width bar in the style of a premium product site: small type, translucent, quiet. */
export function Nav() {
  const { paused } = useDirector();
  return (
    <header className="fixed top-0 inset-x-0 z-50 bg-bg/70 backdrop-blur-xl border-b border-white/[0.06]">
      <nav aria-label="Main" className="mx-auto max-w-6xl h-12 px-4 md:px-6 flex items-center gap-6 text-[12.5px]">
        <a href="#top" className="flex items-center gap-2 font-display text-[15px] font-semibold tracking-tight text-ink">
          <span aria-hidden className="inline-block size-2.5 rounded-full bg-sun shadow-[0_0_12px_2px_rgb(232_190_118/0.6)]" />
          JAS
        </a>
        <ul className="hidden lg:flex items-center gap-7 mx-auto text-ink/70">
          {NAV.map((n) => (
            <li key={n.href}>
              <a href={n.href} className="hover:text-ink transition-colors">
                {n.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="ml-auto lg:ml-0 flex items-center gap-4">
          <button
            onClick={() => director.set({ paused: !paused })}
            aria-pressed={paused}
            data-testid="pause-motion"
            className="flex items-center gap-1.5 text-ink/70 hover:text-ink transition-colors"
          >
            <span aria-hidden className={`size-1.5 rounded-full ${paused ? "bg-muted" : "bg-earth"}`} />
            {paused ? "Resume motion" : "Pause motion"}
          </button>
          <a
            href={`mailto:${CONTACT.email}?subject=JAS`}
            className="hidden sm:inline-flex px-3 py-1 rounded-full bg-sun text-bg font-medium hover:brightness-105 transition"
          >
            Get in touch
          </a>
        </div>
      </nav>
    </header>
  );
}
