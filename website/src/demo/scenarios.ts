/** Scripted demo commands. Simulated: nothing is sent, no microphone is used. */
export interface DemoScenario {
  id: string;
  label: string;
  words: string;
  steps: string[];
  /** MEDIUM/HIGH risk actions ask first. LOW risk ones just answer. */
  confirm?: { question: string; finalStep: string; done: string; cancelled: string };
  answer?: string;
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: "email",
    label: "Email the Q3 report",
    words: "Luffy, email the Q3 report to Rahul.",
    steps: ["Find the file “Q3 Report.xlsx”", "Match “Rahul” to a saved contact", "Draft the email with the file attached"],
    confirm: {
      question: "Send “Q3 Report.xlsx” to Rahul Mehta (rahul@example.com)?",
      finalStep: "Send the email",
      done: "Sent. Rahul has the Q3 report.",
      cancelled: "Cancelled. Nothing was sent.",
    },
  },
  {
    id: "calendar",
    label: "What's on tomorrow?",
    words: "Luffy, what's on my calendar tomorrow?",
    steps: ["Read tomorrow's events from Google Calendar"],
    answer: "Three things: stand-up at 9:30, lunch with Priya at 1, and the board review at 4.",
  },
  {
    id: "share",
    label: "Share the contract",
    words: "Luffy, share the contract draft with legal, view only.",
    steps: ["Find “Contract Draft v3” in Google Drive", "Match “legal” to legal@example.com"],
    confirm: {
      question: "Share “Contract Draft v3” with legal@example.com as view only?",
      finalStep: "Share the file",
      done: "Shared with legal, view only.",
      cancelled: "Cancelled. Nothing was shared.",
    },
  },
];
