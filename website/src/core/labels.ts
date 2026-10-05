/* State names and plain-word labels. No three.js import: safe for the main bundle. */

/** The nine visual states of the Luffy core. Source: JAS-Frontend-Spec.md §6. */
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

/** The same nine states in Japanese, shown beside the English on the site. */
export const STATE_KANJI: Record<CoreState, string> = {
  standby: "待機",
  listening: "傾聴",
  thinking: "思考",
  executing: "実行",
  confirming: "確認",
  responding: "応答",
  success: "完了",
  error: "異常",
  paused: "休止",
};
