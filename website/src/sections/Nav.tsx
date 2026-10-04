import { NAV, CONTACT } from "../content";
import { director, useDirector } from "../story/director";

export function Nav() {
  const { paused } = useDirector();
  return (
    <header className="fixed top-0 inset-x-0 z-50 px-4 md:px-8 pt-4">
      <nav
        aria-label="Main"
        className="glass mx-auto max-w-6xl flex items-center gap-4 px-4 md:px-6 py-2.5 !rounded-full"
      >
        <a href="#top" className="flex items-center gap-2.5 font-display text-lg font-semibold tracking-tight">
          <span aria-hidden className="relative inline-block size-3.5 rounded-full bg-sun shadow-[0_0_14px_2px_rgb(232_190_118/0.6)]" />
          JAS
        </a>
        <ul className="hidden lg:flex items-center gap-1 ml-6 text-sm text-muted">
          {NAV.map((n) => (
            <li key={n.href}>
              <a href={n.href} className="px-3 py-1.5 rounded-full hover:text-ink hover:bg-white/5 transition-colors">
                {n.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => director.set({ paused: !paused })}
            aria-pressed={paused}
            data-testid="pause-motion"
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm text-muted hover:text-ink hover:bg-white/5 transition-colors"
          >
            <span aria-hidden className={`size-2 rounded-full ${paused ? "bg-muted" : "bg-earth animate-pulse"}`} />
            {paused ? "Resume motion" : "Pause motion"}
          </button>
          <a
            href={`mailto:${CONTACT.email}?subject=JAS`}
            className="hidden sm:inline-flex px-4 py-1.5 rounded-full bg-sun text-bg text-sm font-medium hover:brightness-105 transition"
          >
            Get in touch
          </a>
        </div>
      </nav>
    </header>
  );
}
