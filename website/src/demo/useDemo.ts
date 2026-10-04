import { useCallback, useEffect, useRef, useState } from "react";
import type { CoreState } from "../core/labels";
import type { DemoScenario } from "./scenarios";

export type StepStatus = "pending" | "active" | "done";
export type Phase = "idle" | "listening" | "thinking" | "executing" | "confirming" | "responding" | "done" | "cancelled";

export interface DemoView {
  phase: Phase;
  heard: string;
  steps: { label: string; status: StepStatus }[];
  question: string | null;
  reply: string | null;
}

const IDLE: DemoView = { phase: "idle", heard: "", steps: [], question: null, reply: null };

/** Core state for each demo phase (spec §6). */
export const PHASE_TO_CORE: Record<Phase, CoreState | null> = {
  idle: null,
  listening: "listening",
  thinking: "thinking",
  executing: "executing",
  confirming: "confirming",
  responding: "responding",
  done: "success",
  cancelled: "standby",
};

class Cancelled extends Error {}

/** Runs one scripted command at a time. Starting another, or unmounting, cancels the running one. */
export function useDemo() {
  const [view, setView] = useState<DemoView>(IDLE);
  const run = useRef(0);
  const answerRef = useRef<((yes: boolean) => void) | null>(null);

  useEffect(() => () => void (run.current++), []);

  const start = useCallback(async (sc: DemoScenario) => {
    const id = ++run.current;
    answerRef.current = null;
    const alive = () => {
      if (id !== run.current) throw new Cancelled();
    };
    const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms)).then(alive);
    const set = (patch: Partial<DemoView> | ((v: DemoView) => Partial<DemoView>)) => {
      alive();
      setView((v) => ({ ...v, ...(typeof patch === "function" ? patch(v) : patch) }));
    };
    const mark = (i: number, status: StepStatus) =>
      set((v) => ({ steps: v.steps.map((s, j) => (j === i ? { ...s, status } : s)) }));

    try {
      set({ ...IDLE, phase: "listening" });
      const words = sc.words.split(" ");
      for (let i = 0; i < words.length; i++) {
        await sleep(170);
        set({ heard: words.slice(0, i + 1).join(" ") });
      }
      await sleep(500);
      set({ phase: "thinking" });
      await sleep(1100);
      set({ phase: "executing", steps: sc.steps.map((label) => ({ label, status: "pending" })) });
      for (let i = 0; i < sc.steps.length; i++) {
        mark(i, "active");
        await sleep(750);
        mark(i, "done");
      }
      await sleep(250);

      if (sc.confirm) {
        const c = sc.confirm;
        set({ phase: "confirming", question: c.question });
        const yes = await new Promise<boolean>((resolve) => (answerRef.current = resolve));
        alive();
        answerRef.current = null;
        if (!yes) {
          set({ phase: "cancelled", question: null, reply: c.cancelled });
          return;
        }
        set((v) => ({ phase: "executing", question: null, steps: [...v.steps, { label: c.finalStep, status: "active" }] }));
        await sleep(900);
        mark(sc.steps.length, "done");
        set({ phase: "done", reply: c.done });
      } else {
        set({ phase: "responding", reply: sc.answer ?? "" });
        await sleep(2800);
        set({ phase: "done" });
      }
      await sleep(1700);
      set({ phase: "idle" });
    } catch (e) {
      if (!(e instanceof Cancelled)) throw e;
    }
  }, []);

  const answer = useCallback((yes: boolean) => answerRef.current?.(yes), []);

  return { view, start, answer };
}
