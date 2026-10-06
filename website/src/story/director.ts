import { useLayoutEffect, useSyncExternalStore, type RefObject } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import type { CoreState } from "../core/labels";

gsap.registerPlugin(ScrollTrigger);

/** Where the single, page-wide core sits. */
/** "how" = left on desktop, but stays visible above the steps on phones. */
export type Anchor = "hero" | "center" | "left" | "right" | "how" | "hidden";

export interface DirectorState {
  /** State set by the section currently in view. */
  section: CoreState;
  anchor: Anchor;
  /** Set by interactive demos while they run; wins over the section state. */
  override: CoreState | null;
  /** Visitor pressed "Pause motion". */
  paused: boolean;
}

let current: DirectorState = { section: "standby", anchor: "hero", override: null, paused: false };
const listeners = new Set<() => void>();

/** A tiny store: the page is the only writer, the core layer is the reader. */
export const director = {
  get: () => current,
  set(patch: Partial<DirectorState>) {
    const next = { ...current, ...patch };
    if (
      next.section === current.section &&
      next.anchor === current.anchor &&
      next.override === current.override &&
      next.paused === current.paused
    )
      return;
    current = next;
    listeners.forEach((l) => l());
  },
  subscribe(l: () => void) {
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  },
};

export function useDirector(): DirectorState {
  return useSyncExternalStore(director.subscribe, director.get, director.get);
}

export function effectiveState(s: DirectorState): CoreState {
  return s.paused ? "paused" : (s.override ?? s.section);
}

/** While `ref` is the section in the middle of the screen, the core takes `state` at `anchor`. */
export function useCoreSection(ref: RefObject<HTMLElement | null>, state: CoreState, anchor: Anchor) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const st = ScrollTrigger.create({
      trigger: el,
      start: "top 55%",
      end: "bottom 45%",
      onToggle: (self) => {
        if (self.isActive) director.set({ section: state, anchor });
      },
    });
    return () => st.kill();
  }, [ref, state, anchor]);
}
