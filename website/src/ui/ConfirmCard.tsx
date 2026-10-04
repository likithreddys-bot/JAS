import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

export const CONFIRM_TIMEOUT_S = 60;

interface ConfirmCardProps {
  question: string;
  onAnswer: (yes: boolean, reason: "user" | "timeout") => void;
}

/**
 * The shared confirm card (spec §7.3): one sentence, two buttons, Enter / Esc,
 * resolves to *No* after 60 s, never auto-confirms.
 */
export function ConfirmCard({ question, onAnswer }: ConfirmCardProps) {
  const [left, setLeft] = useState(CONFIRM_TIMEOUT_S);
  const done = useRef(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const answer = (yes: boolean, reason: "user" | "timeout") => {
    if (done.current) return;
    done.current = true;
    onAnswer(yes, reason);
  };

  useEffect(() => {
    // Focus the card, not a button: Enter means yes (spec §7.3), Esc means no.
    cardRef.current?.focus({ preventScroll: true });
    const started = Date.now();
    const id = window.setInterval(() => {
      const remaining = Math.max(0, CONFIRM_TIMEOUT_S - Math.floor((Date.now() - started) / 1000));
      setLeft(remaining);
      if (remaining === 0) answer(false, "timeout");
    }, 250);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") answer(false, "user");
      else if (e.key === "Enter" && !(e.target instanceof HTMLButtonElement)) answer(true, "user");
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <motion.div
      ref={cardRef}
      tabIndex={-1}
      role="alertdialog"
      aria-modal="false"
      aria-labelledby="confirm-q"
      data-testid="confirm-card"
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 12, opacity: 0 }}
      transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
      className="glass p-5 border-sun/30 outline-none"
    >
      <p className="text-xs uppercase tracking-[0.18em] text-sun">JAS needs your yes</p>
      <p id="confirm-q" className="mt-2 text-lg text-ink">
        {question}
      </p>
      <div className="mt-4 flex gap-3">
        <button
          onClick={() => answer(true, "user")}
          data-testid="confirm-yes"
          className="flex-1 min-h-14 rounded-2xl bg-sun text-bg font-medium hover:brightness-105 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sun"
        >
          Yes, do it
        </button>
        <button
          onClick={() => answer(false, "user")}
          data-testid="confirm-no"
          className="flex-1 min-h-14 rounded-2xl border border-white/15 text-ink hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          No, cancel
        </button>
      </div>
      <div className="mt-4 h-0.5 rounded-full bg-white/10 overflow-hidden" aria-hidden>
        <div className="h-full bg-sun/70 origin-left confirm-countdown" />
      </div>
      <p className="mt-2 text-xs text-muted" data-testid="confirm-timer">
        Becomes “No” in {left} s · Enter = yes · Esc = no
      </p>
    </motion.div>
  );
}
