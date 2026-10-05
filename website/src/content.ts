/* All site copy lives here. Every claim is taken from the client documentation (written when it was called JAS)
 * (JAS-Full-Documentation.pdf, 03 Oct 2026). Do not add capabilities that are not in it. */

export const CONTACT = {
  name: "Likki Saribala",
  email: "likithreddysaribala@gmail.com",
};

/** Optional Higgsfield ambient loop for the hero (an .mp4 in /public). null = none.
 *  The live 3D core is the hero; a loop only adds atmosphere behind it. */
export const HERO_LOOP_SRC: string | null = null;

export const NAV = [
  { href: "#film", label: "The film" },
  { href: "#not-siri", label: "Why Luffy" },
  { href: "#problem", label: "The problem" },
  { href: "#demo", label: "Try it" },
  { href: "#how", label: "How it works" },
  { href: "#trust", label: "Security" },
  { href: "#roadmap", label: "Roadmap" },
  { href: "#faq", label: "FAQ" },
];

export const HERO = {
  eyebrow: "Your personal AI operator",
  // Title shows [0] and [2]: "Your laptop." / "From anywhere." The middle line stays for the OG/meta copy.
  title: ["Your laptop.", "By voice.", "From anywhere."],
  body:
    "Luffy runs on your own Windows PC. Speak to your phone, and the real work happens on your laptop — opening files, driving Excel, sending email, sharing documents. Nothing consequential happens until you say yes.",
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
    body: "From your phone or the laptop's own mic. Say its name first — it only acts on what is addressed to it.",
  },
  {
    title: "Luffy listens locally",
    body: "Wake-word detection and speech recognition run on the laptop itself. Audio is never sent to a cloud service.",
  },
  {
    title: "The model picks a tool",
    body: "A language model receives only the text, and may only choose from a fixed list of reviewed tools. No raw shell, ever.",
  },
  {
    title: "Luffy asks to confirm",
    body: "Anything that sends, shares, deletes, schedules or remembers is checked with you out loud — enforced in code, not in a prompt.",
  },
  {
    title: "The action runs on your PC",
    body: "The real app does the real work. Luffy reports success only when the action actually succeeded.",
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
  { title: "Present while locked", body: "Keeps working behind Windows' lock screen — and the circle on the lock screen visibly moves." },
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
  { what: "Speech can mishear in a noisy room", why: "Luffy only acts when addressed by name, but accuracy still depends on noise and accent." },
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

/** The roast. "Them" lines are generic caricatures of phone assistants, not quotes from any product.
 *  Every Luffy line is a capability from the client documentation. */
export const ROAST = {
  eyebrow: "No offence",
  title: ["Not Siri.", "Not Gemini.", "Just Luffy."],
  body: "Phone assistants are brilliant at the weather. Luffy is for the work that is stuck on your laptop.",
  cards: [
    {
      them: "Here's what I found on the web.",
      jas: "Opens the actual spreadsheet on your PC and reads you the total in column F.",
    },
    {
      them: "I can set a timer for that.",
      jas: "Sends the Q3 report from your laptop — locked, at home, three hours away.",
    },
    {
      them: "Sorry, I can't do that on this device.",
      jas: "Drives Excel on your Windows PC by voice: formulas, pivot tables, charts.",
    },
    {
      them: "Sending your voice to the cloud…",
      jas: "Hears its name and transcribes you on your own laptop. Your audio never leaves it.",
    },
  ],
  disclosure:
    "Full disclosure: Luffy may rent a cloud brain — Gemini or Claude — to pick which tool to use. It gets the text of your command. Never your audio, never the keyboard. The brain can be rented. The hands are Luffy's.",
};

/** The film: a 20-second spot. HR needs a report sent to her manager now; her laptop is far away. */
export const FILM = {
  src: "film/luffy-film.mp4",
  poster: "film/luffy-film-poster.jpg",
  title: "Thirty seconds.",
  caption: "A dramatised scenario. Luffy really does send email from your own PC, and asks before it sends.",
};

export const HIGHLIGHTS = [
  { big: "11×", label: "faster speech recognition on the laptop's own GPU", note: "41 s → 3.6 s, same clip, under load" },
  { big: "0", label: "ports opened on your router", note: "Away from home it rides a private Tailscale tunnel" },
  { big: "1 yes", label: "before anything is sent, shared or remembered", note: "Enforced by the code that runs tools" },
  { big: "6 digits", label: "of PIN on every phone request", note: "Five wrong guesses locks that source out" },
  { big: "Locked", label: "screen? Luffy keeps working", note: "And the circle on the lock screen really moves" },
  { big: "0 s", label: "of microphone audio sent to the cloud", note: "Wake word and speech run on your PC" },
];

/** Straight answers. Every one is taken from the client documentation. */
export const FAQ = [
  {
    q: "Does Luffy listen to everything I say?",
    a: "It listens only for its name, on your laptop itself. Nothing is sent anywhere until it hears its name, and speech recognition also runs on the laptop.",
  },
  {
    q: "What leaves my PC?",
    a: "Only the text of a command, sent to a language model (Google Gemini or Anthropic Claude) so it can choose which tool to use. Never your audio, and never control of your PC.",
  },
  {
    q: "Can Luffy send something without asking me?",
    a: "No. Anything that sends, shares, deletes, schedules or remembers is confirmed with you first. That rule is enforced by the code that runs the tools, not by an instruction to the AI.",
  },
  {
    q: "Does it work from outside my home?",
    a: "Yes, through a private, encrypted Tailscale tunnel. No port is opened on your router, and every request from the phone needs your six-digit PIN.",
  },
  {
    q: "What if my laptop is off or asleep?",
    a: "Then Luffy can't answer: nothing is running. The laptop is set never to sleep while it is plugged in.",
  },
  {
    q: "Which devices does it work with?",
    a: "Today: a Windows PC, controlled from the PC itself or from a native Android app.",
  },
  {
    q: "Can it join my video calls?",
    a: "Not yet. Joining a live call and speaking into it through the phone is in development.",
  },
  {
    q: "Can my team use it?",
    a: "Not yet. Luffy is built for one person and one laptop. Team accounts are a deliberate, later phase.",
  },
];
