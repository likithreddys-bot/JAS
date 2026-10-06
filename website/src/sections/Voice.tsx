import { useEffect, useRef, useState } from "react";
import type { CoreState } from "../core/labels";
import { director } from "../story/director";
import { useReducedMotion } from "../core/useReducedMotion";
import { Eyebrow, H2, Section } from "./Section";

/** The real voice: each clip was rendered by the app's own speaker code (scripts/render_voice.py),
 *  so this is exactly how VEM sounds on the PC. Playing one sets the core to the matching state. */
const CLIPS: { id: string; mood: string; line: string; state: CoreState }[] = [
  { id: "greeting", mood: "Greeting", line: "Hey Likki! I'm here. What do you need?", state: "responding" },
  { id: "working", mood: "On it", line: "On it! Opening the Q3 report now.", state: "executing" },
  { id: "confirming", mood: "Asking first", line: "I'm about to send the Q3 attrition report to Arjun Rao. Should I send it?", state: "confirming" },
  { id: "done", mood: "Done", line: "Done! It's sent. Arjun has it. Anything else?", state: "success" },
  { id: "error", mood: "Something went wrong", line: "Hmm, I couldn't open that file. It looks like it was moved. Want me to look for it?", state: "error" },
  { id: "warning", mood: "Guarding the PC", line: "Hey. This is Likki's PC. Please don't touch it.", state: "error" },
];

export function Voice() {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const reduced = useReducedMotion();

  const stop = () => {
    audio.current?.pause();
    setPlaying(null);
    director.set({ override: null });
  };
  useEffect(() => stop, []);

  const play = (c: (typeof CLIPS)[number]) => {
    if (playing === c.id) return stop();
    audio.current?.pause();
    const a = new Audio(`${import.meta.env.BASE_URL}voice/${c.id}.mp3`);
    audio.current = a;
    setProblem(null);
    setPlaying(c.id);
    director.set({ override: c.state });
    a.onended = stop;
    a.play().catch((e: Error) => {
      setProblem(`Couldn't play the clip: ${e.message}`);
      stop();
    });
  };

  return (
    <Section id="voice" state="responding" anchor="right" label="VEM's voice" className="py-28 md:py-40">
      <div className="md:max-w-[52%]">
        <Eyebrow>Hear VEM</Eyebrow>
        <H2>Quick when it's good news. Careful when it matters.</H2>
        <p data-reveal className="mt-6 max-w-xl text-lg text-ink/70">
          VEM speaks in a natural, upbeat voice that runs on your own PC, and changes its pace with the moment: bright
          when it greets you, slower and clearer when it asks before sending, calm when something fails.
        </p>
        <ul className="mt-10 grid gap-2.5" aria-label="Voice samples">
          {CLIPS.map((c) => {
            const on = playing === c.id;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => play(c)}
                  aria-pressed={on}
                  data-testid={`voice-${c.id}`}
                  className={`group w-full glass flex items-center gap-4 px-4 py-3.5 text-left transition-colors ${
                    on ? "!border-sun/60" : "hover:!border-sun/30"
                  }`}
                >
                  <span
                    aria-hidden
                    className={`grid size-10 shrink-0 place-items-center rounded-full ${on ? "bg-sun text-bg" : "bg-sun/12 text-sun"}`}
                  >
                    {on ? (
                      <span className="flex h-3.5 items-end gap-[3px]">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="w-[3px] rounded-full bg-bg"
                            style={{ height: reduced ? "70%" : undefined, animation: reduced ? undefined : `voice-bar 0.9s ${i * 0.15}s ease-in-out infinite` }}
                          />
                        ))}
                      </span>
                    ) : (
                      <svg viewBox="0 0 12 12" className="size-3.5 translate-x-[1px]" fill="currentColor">
                        <path d="M2 1.2v9.6L10.4 6z" />
                      </svg>
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs font-medium uppercase tracking-[0.16em] text-muted">{c.mood}</span>
                    <span className="block text-[15px] md:text-base text-ink leading-snug">“{c.line}”</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
        {problem && (
          <p role="alert" className="mt-4 text-sm text-alert">
            {problem}
          </p>
        )}
        <p className="mt-6 text-sm text-muted">
          Rendered by the app's own speech code (Kokoro, voice “Puck”, running on the laptop) — not a studio recording.
        </p>
      </div>
    </Section>
  );
}
