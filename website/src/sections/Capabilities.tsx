import { useEffect, useState } from "react";
import { CAPABILITIES, CONTACT } from "../content";
import { useReducedMotion } from "../core/useReducedMotion";
import { useDirector } from "../story/director";
import { Eyebrow, H2, Section } from "./Section";

type Mood = "watchful" | "blink" | "angry";

/** The real lock screen, drawn by the app's own app/lockart.py, shown on a laptop. It swaps between
 *  two frames of the circle on the app's own timing (app/lockscreen.py: a 3-7 s gap, the alternate frame held
 *  1 s); "Try wrong unlocks" shows what repeated wrong unlock attempts do. */
function LockScreen() {
  const reduced = useReducedMotion();
  const { paused } = useDirector();
  const [mood, setMood] = useState<Mood>("watchful");
  const [angry, setAngry] = useState(false);

  useEffect(() => {
    if (angry || reduced || paused) return;
    let t: number;
    const loop = () => {
      t = window.setTimeout(() => {
        setMood("blink");
        t = window.setTimeout(() => {
          setMood("watchful");
          loop();
        }, 1000);
      }, 3000 + Math.random() * 4000);
    };
    loop();
    return () => window.clearTimeout(t);
  }, [angry, reduced, paused]);

  useEffect(() => {
    if (!angry) return;
    setMood("angry");
    const t = window.setTimeout(() => {
      setAngry(false);
      setMood("watchful");
    }, 3500);
    return () => window.clearTimeout(t);
  }, [angry]);

  const first = CONTACT.name.split(" ")[0];
  return (
    <figure>
      {/* the laptop */}
      <div className="relative mx-auto w-full">
        <div className="rounded-t-[20px] border border-ink/10 bg-[#0d0b09] p-[2.2%] shadow-[0_50px_120px_-50px_rgb(28_25_21/0.5)]">
          <div className="relative aspect-video overflow-hidden rounded-[6px] bg-lacquer">
            {(["watchful", "blink", "angry"] as Mood[]).map((m) => (
              <img
                key={m}
                src={`${import.meta.env.BASE_URL}lock/${m}.webp`}
                alt={m === "watchful" ? `${first}'s PC, locked, with the Luffy ensō on the lock screen` : ""}
                aria-hidden={m !== "watchful"}
                width={1280}
                height={720}
                loading="lazy"
                decoding="async"
                className="absolute inset-0 size-full object-cover transition-opacity duration-300"
                style={{ opacity: mood === m ? 1 : 0 }}
              />
            ))}
            {/* The app draws these over the picture; positions and colours match app/lockart.py. */}
            <span
              aria-hidden
              className="tate absolute right-[5.5%] top-[9%] grid place-items-center border-[2px] border-[#d9543a] px-[0.35em] py-[0.5em] font-display text-[clamp(0.55rem,1.25vw,0.95rem)] font-bold leading-[1.15] text-[#d9543a] rotate-[6deg]"
            >
              ルフィ
            </span>
            <div className="absolute inset-x-0 top-[68.5%] text-center leading-tight text-[#efe7d8]">
              <p className="font-display text-[clamp(0.95rem,2.6vw,1.75rem)] font-bold">{first}'s PC</p>
              <p
                className={`mt-[0.7em] text-[clamp(0.6rem,1.25vw,0.85rem)] ${
                  mood === "angry" ? "font-display font-bold text-[#d9543a] text-[clamp(0.7rem,1.6vw,1.05rem)]" : "uppercase tracking-[0.32em] text-[#a99f90]"
                }`}
                aria-live="polite"
              >
                {mood === "angry" ? `Don't touch ${first}'s PC` : "Luffy is watching"}
              </p>
            </div>
          </div>
        </div>
        <div className="relative mx-[-4%] h-3 rounded-b-[14px] bg-gradient-to-b from-[#2a241d] to-[#16120e]">
          <div className="absolute left-1/2 top-0 h-1.5 w-[14%] -translate-x-1/2 rounded-b-md bg-[#0d0b09]" />
        </div>
      </div>
      <figcaption className="mt-6 flex flex-wrap items-center justify-between gap-4 text-sm text-muted">
        <span>Drawn by the app's own lock-screen code — not a mockup.</span>
        <button
          onClick={() => setAngry(true)}
          disabled={angry}
          className="shrink-0 rounded-full border border-alert/40 text-alert px-3 py-1.5 hover:bg-alert/10 disabled:opacity-40 transition"
        >
          Try wrong unlocks
        </button>
      </figcaption>
    </figure>
  );
}

export function Capabilities() {
  return (
    <Section id="capabilities" state="executing" anchor="hidden" label="Capabilities" className="py-28 md:py-40">
      <Eyebrow tone="earth">Built and working today</Eyebrow>
      <H2 className="max-w-3xl">The laptop's real capabilities, reachable by voice.</H2>
      <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map((c) => (
          <li key={c.title} data-reveal data-tilt className="glass p-6">
            <h3 className="text-lg font-semibold">{c.title}</h3>
            <p className="mt-2 text-[15px] leading-relaxed text-ink/65">{c.body}</p>
          </li>
        ))}
      </ul>

      <div id="locked" className="mt-28 md:mt-36 text-center">
        <p className="text-sm font-medium text-sun">見張り · Present while locked</p>
        <h3 data-reveal className="mt-3 text-4xl md:text-6xl font-semibold tracking-[-0.04em]">
          Lock it. Luffy keeps watch.
        </h3>
        <p data-reveal className="mx-auto mt-5 max-w-2xl text-lg text-ink/70">
          Windows only lets apps set the lock-screen <em>image</em>. Luffy swaps it every few seconds, and Windows redraws
          it live — so the brush circle really turns while the PC is locked. Repeated wrong unlock attempts turn it vermilion.
        </p>
      </div>
      <div data-reveal className="mx-auto mt-12 max-w-4xl">
        <LockScreen />
      </div>
    </Section>
  );
}
