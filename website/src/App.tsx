import { useState } from "react";
import { CoreStage } from "./core/CoreStage";
import { CORE_STATES, STATE_LABEL, type CoreState } from "./core/states";
import { FpsMeter } from "./dev/FpsMeter";

/** `?dev` in the URL shows the state switcher and fps meter, in any build. */
const DEV = import.meta.env.DEV || new URLSearchParams(location.search).has("dev");

export default function App() {
  const [state, setState] = useState<CoreState>("standby");
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-6 px-6 py-10">
      <CoreStage state={state} className="!w-[min(80vw,560px)] !h-[min(80vw,560px)]" />
      <p aria-live="polite" className="text-muted text-lg" data-testid="state-label">
        {STATE_LABEL[state]}
      </p>
      {DEV && (
        <>
          <div className="flex flex-wrap justify-center gap-2 max-w-2xl" role="group" aria-label="Core state">
            {CORE_STATES.map((s) => (
              <button
                key={s}
                data-state={s}
                onClick={() => setState(s)}
                aria-pressed={s === state}
                className={`glass px-4 py-2 text-sm transition-colors ${
                  s === state ? "text-sun" : "text-muted hover:text-ink"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <FpsMeter />
        </>
      )}
    </main>
  );
}
