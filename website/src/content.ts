/* All site copy lives here. Every claim is taken from the JAS client documentation
 * (JAS-Full-Documentation.pdf, 03 Oct 2026). Do not add capabilities that are not in it. */

export const CONTACT = {
  name: "Likki Saribala",
  email: "likithreddysaribala@gmail.com",
};

/** Optional Higgsfield ambient loop for the hero (an .mp4 in /public). null = none.
 *  The live 3D core is the hero; a loop only adds atmosphere behind it. */
export const HERO_LOOP_SRC: string | null = null;

export const NAV = [
  { href: "#problem", label: "The problem" },
  { href: "#demo", label: "Try it" },
  { href: "#how", label: "How it works" },
  { href: "#trust", label: "Security" },
  { href: "#roadmap", label: "Roadmap" },
];

export const HERO = {
  eyebrow: "Your personal AI operator",
  title: ["Your laptop.", "By voice.", "From anywhere."],
  body:
    "JAS runs on your own Windows PC. Speak to your phone, and the real work happens on your laptop — opening files, driving Excel, sending email, sharing documents. Nothing consequential happens until you say yes.",
  chips: ["Wake word runs on your PC", "Asks before it acts", "Works through a locked screen"],
};

export const THESIS = {
  before: "“I'll deal with it when I'm back at my desk.”",
  after: "“Give me thirty seconds.”",
};

export interface Scenario {
  condition: string;
  name: string;
  role: string;
  story: string;
  solution: string;
}

export const SCENARIOS: Scenario[] = [
  {
    condition: "At a family event, far from home",
    name: "Anjali",
    role: "Regional Operations Manager",
    story:
      "7 PM on a Saturday at her cousin's wedding, three hours from the office. A client needs a revised proposal within the hour. Her laptop is at home, locked.",
    solution: "Finds the proposal, reads back the recipient for confirmation, and sends it by email.",
  },
  {
    condition: "Mid-flight, about to lose connectivity",
    name: "Rahul",
    role: "Startup Founder",
    story:
      "Boarding has closed. An investor wants the latest cap table before take-off. The laptop is in the overhead bin.",
    solution: "Locates the file by name, confirms the investor's address out loud, and sends it — inside a boarding queue.",
  },
  {
    condition: "In court, between hearings",
    name: "Priya",
    role: "Litigation Associate",
    story:
      "A ten-minute recess. A client calls for a change to a draft agreement sitting on her office PC. She cannot leave the building.",
    solution: "Opens the agreement in the background, makes the dictated change, saves it, and confirms the save out loud.",
  },
  {
    condition: "Back-to-back meetings, no laptop in the room",
    name: "Arjun",
    role: "Management Consultant",
    story:
      "His calendar has double-booked him. He has sixty seconds on a stairwell landing to move a meeting and tell the other attendee.",
    solution: "Moves the calendar event by the stated amount and notifies the attendee, after one spoken yes.",
  },
  {
    condition: "A family emergency, away from the desk",
    name: "Sneha",
    role: "HR Manager",
    story:
      "A family member is being admitted to hospital. The insurance desk needs a policy document that exists only on her work laptop.",
    solution: "Finds the document by name and shares it with the insurance contact — without touching a laptop.",
  },
  {
    condition: "A long commute, a number needed now",
    name: "Vikram",
    role: "Finance Analyst",
    story:
      "Two hours on a crowded train. His manager needs one updated figure from a spreadsheet that lives only on his home PC.",
    solution: "Opens the spreadsheet and reads back the exact cell or total, out loud, in seconds.",
  },
];

export const FLOW = [
  {
    title: "You speak",
    body: "From your phone or the laptop's own mic. Say “JAS” first — it only acts on what is addressed to it.",
  },
  {
    title: "JAS listens locally",
    body: "Wake-word detection and speech recognition run on the laptop itself. Audio is never sent to a cloud service.",
  },
  {
    title: "The model picks a tool",
    body: "A language model receives only the text, and may only choose from a fixed list of reviewed tools. No raw shell, ever.",
  },
  {
    title: "JAS asks to confirm",
    body: "Anything that sends, shares, deletes, schedules or remembers is checked with you out loud — enforced in code, not in a prompt.",
  },
  {
    title: "The action runs on your PC",
    body: "The real app does the real work. JAS reports success only when the action actually succeeded.",
  },
];

export type Risk = "instant" | "asks";

export const EXAMPLES: { say: string; happens: string; risk: Risk }[] = [
  { say: "Email the Q3 report to Rahul.", happens: "Finds the file, resolves “Rahul” to a saved contact, reads the address back, sends.", risk: "asks" },
  { say: "Share the contract draft with legal, view only.", happens: "Finds it in Google Drive, confirms the recipient and access level, then shares.", risk: "asks" },
  { say: "What's on my calendar tomorrow?", happens: "Reads back the day's events from Google Calendar.", risk: "instant" },
  { say: "Move my 3 PM meeting to 3:30 and notify everyone.", happens: "Updates the event and notifies attendees after one spoken yes.", risk: "asks" },
  { say: "Open the budget sheet and tell me the total in column F.", happens: "Opens the workbook in Excel and reads the range back out loud.", risk: "instant" },
  { say: "Add a pivot table summarising sales by region.", happens: "Builds the pivot table directly in the open workbook.", risk: "instant" },
  { say: "Remember that the client prefers calls after 4 PM.", happens: "Asks “should I remember that?” first. Nothing is remembered silently.", risk: "asks" },
  { say: "Pause the music.", happens: "A direct media control. No confirmation needed.", risk: "instant" },
];

export const CAPABILITIES = [
  { title: "Local wake word and speech", body: "Runs on the laptop's own GPU — about eleven times faster than the CPU path (41 s → 3.6 s on the same clip)." },
  { title: "A native Android app", body: "Floats over other apps and listens continuously. No hold-to-talk button." },
  { title: "Hands-free PC control", body: "Open and close apps, drive Excel — formulas, pivot tables, formatting, charts — browse, manage windows." },
  { title: "Google, built in", body: "Read and send email, read the calendar, schedule meetings, share a Drive file with someone by name." },
  { title: "Present while locked", body: "Keeps working behind Windows' lock screen — and the lock screen's face visibly blinks." },
  { title: "Reachable from anywhere", body: "Home Wi-Fi, or a private encrypted Tailscale tunnel when you are away." },
];

export const SECURITY = [
  { title: "Processing stays local", body: "The microphone is never streamed anywhere. Only the transcribed text leaves the machine, and only for the decision step." },
  { title: "Nothing consequential without a yes", body: "Sends, shares, deletes, schedules and memories are MEDIUM or HIGH risk and must be confirmed — enforced by the code that runs tools." },
  { title: "PIN-protected, self-defending", body: "Every phone request carries a six-digit PIN. Five wrong guesses in fifteen minutes locks that source out for fifteen minutes." },
  { title: "No open ports", body: "Away from home, traffic goes through an encrypted Tailscale mesh. The Android app pins the laptop's identity on first connect, like SSH." },
  { title: "Least-privilege Google access", body: "Calendar, Gmail, Contacts and Drive each use the narrowest scope available, granted by you at sign-in." },
];

export const LIMITATIONS = [
  { what: "Can't join or speak into a live video call", why: "Routing call audio through the phone is real engineering that hasn't been built yet." },
  { what: "Unreachable when the laptop is off or asleep", why: "Nothing is running to answer. The laptop is set to never sleep on power; Wake-on-LAN isn't available on this hardware." },
  { what: "Single user, single device", why: "Built around one person and one laptop. Teams are a deliberate, larger future phase." },
  { what: "Uses a cloud language model to decide", why: "The text of a command goes to Google Gemini or Anthropic Claude. The audio never does." },
  { what: "Google sign-in is in “Testing” mode", why: "The app hasn't been through Google's verification yet, so each account must be an approved tester." },
  { what: "Speech can mishear in a noisy room", why: "JAS only acts when addressed by name, but accuracy still depends on noise and accent." },
  { what: "Local data isn't encrypted at rest", why: "Memory, notes and the PIN sit in a local database protected only by the laptop's own account and disk." },
  { what: "The NPU isn't used", why: "The speech model's export doesn't meet the NPU's fixed-shape requirement. The GPU path already delivers the gain." },
];

export const ROADMAP = {
  now: [
    "Voice control of apps, files and Excel",
    "Email and Drive sharing, always confirmed first",
    "Works through a locked screen",
    "Reachable from anywhere, not just home Wi-Fi",
  ],
  next: ["Joining a live call and speaking into it through the phone", "Recording and replying inside a meeting remotely"],
  later: ["Multi-user, team-scoped deployment", "Local database encryption", "Independent security audit", "Formal Google app verification"],
};
