import { useRef, useState } from "react";
import { FILM } from "../content";
import { Section } from "./Section";

const base = import.meta.env.BASE_URL;

/** The film, presented the way a product page presents its launch film: big, framed, click to play. */
export function Film() {
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  return (
    <Section id="film" state="standby" anchor="hidden" label="The film" className="py-24 md:py-36">
      <div className="text-center">
        <p className="text-sm font-medium text-sun">The film</p>
        <h2 data-reveal className="mt-3 text-5xl md:text-7xl font-semibold tracking-[-0.04em]">
          {FILM.title}
        </h2>
      </div>
      <div data-reveal className="relative mt-12 overflow-hidden rounded-[28px] border border-ink/[0.08] bg-coal shadow-[0_50px_120px_-60px_rgb(28_25_21/0.45)]">
        <video
          ref={video}
          className="block w-full aspect-video"
          src={`${base}${FILM.src}`}
          poster={`${base}${FILM.poster}`}
          controls={playing}
          playsInline
          preload="metadata"
          onPlay={() => setPlaying(true)}
          onEnded={() => setPlaying(false)}
          data-testid="film"
        />
        {!playing && (
          <button
            onClick={() => video.current?.play()}
            className="absolute inset-0 grid place-items-center group"
            aria-label="Play the film"
          >
            <span className="grid place-items-center size-20 md:size-24 rounded-full bg-ink/90 text-bg shadow-2xl transition-transform group-hover:scale-105">
              <svg viewBox="0 0 24 24" className="size-8 md:size-10 translate-x-0.5" fill="currentColor" aria-hidden>
                <path d="M8 5.5v13l11-6.5z" />
              </svg>
            </span>
          </button>
        )}
      </div>
      <p className="mt-5 text-center text-sm text-muted">{FILM.caption}</p>
    </Section>
  );
}
