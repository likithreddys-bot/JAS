import { useEffect, useState } from "react";
import { CAPABILITIES, CONTACT } from "../content";
import { useReducedMotion } from "../core/useReducedMotion";
import { useDirector } from "../story/director";
import { Eyebrow, H2, Section } from "./Section";

type Mood = "watchful" | "blink" | "angry";

/** The real lock-screen face, rendered by JAS's own app/lockart.py, blinking on the same rhythm. */
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
        }, 180);
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
    <figure className="glass overflow-hidden p-0">
      <div className="relative aspect-square bg-bg">
        {(["watchful", "blink", "angry"] as Mood[]).map((m) => (
          <img
            key={m}
            src={`/lock/${m}.webp`}
            alt={m === "watchful" ? "JAS lock-screen face, watching" : ""}
            aria-hidden={m !== "watchful"}
            width={720}
            height={720}
            loading="lazy"
            decoding="async"
            className="absolute inset-0 size-full object-cover transition-opacity duration-150"
            style={{ opacity: mood === m ? 1 : 0 }}
          />
        ))}
        <div className="absolute inset-x-0 bottom-8 text-center">
          <p className="font-display text-xl font-semibold">{first}'s PC</p>
          <p className={`mt-1 text-sm ${mood === "angry" ? "text-alert" : "text-muted"}`} aria-live="polite">
            {mood === "angry" ? `Don't touch ${first}'s PC` : "JAS is watching"}
          </p>
        </div>
      </div>
      <figcaption className="flex items-center justify-between gap-4 px-5 py-4 text-sm text-muted">
        <span>Face rendered by JAS's own lock-screen code — not a mockup.</span>
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
      <div className="mt-14 grid gap-10 lg:grid-cols-[1.15fr_1fr] items-start">
        <ul className="grid gap-4 sm:grid-cols-2">
          {CAPABILITIES.map((c) => (
            <li key={c.title} data-reveal data-tilt className="glass p-6">
              <h3 className="text-lg font-semibold">{c.title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-ink/65">{c.body}</p>
            </li>
          ))}
        </ul>
        <div data-reveal>
          <LockScreen />
          <p className="mt-4 text-sm text-muted leading-relaxed">
            Windows only lets apps set the lock-screen <em>image</em>. JAS swaps it every few seconds, and Windows redraws
            it live — so the face really blinks while the PC is locked. Repeated wrong unlock attempts make it angry.
          </p>
        </div>
      </div>
    </Section>
  );
}
