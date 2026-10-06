/* State names and plain-word labels. No three.js import: safe for the main bundle. */

/** The nine visual states of the VEM core. Source: JAS-Frontend-Spec.md §6. */
export const CORE_STATES = [
  "standby",
  "listening",
  "thinking",
  "executing",
  "confirming",
  "responding",
  "success",
  "error",
  "paused",
] as const;
export type CoreState = (typeof CORE_STATES)[number];

/** Plain-words label per state: shown under the core and read by screen readers. */
export const STATE_LABEL: Record<CoreState, string> = {
  standby: "Standing by",
  listening: "Listening",
  thinking: "Thinking",
  executing: "Working on it",
  confirming: "Waiting for your yes or no",
  responding: "Speaking",
  success: "Done",
  error: "Something went wrong",
  paused: "Paused",
};
