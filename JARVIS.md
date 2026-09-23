# JARVIS — Personal Desktop AI Agent

> **This is the master document of the project.** It defines what JARVIS is, how it is built, and in what order.
> Every design decision, feature, and phase traces back to this file. If code and this file disagree, one of them must be updated deliberately — never silently.

- **Platform:** Windows 11 (first-class). Architecture must stay portable to macOS/Linux later.
- **Language:** Python 3.12+
- **Status tracker:** see [§ 12 Roadmap & Status](#12-roadmap--status)
- **Decisions log:** see [§ 14 Architecture Decision Records](#14-architecture-decision-records-adr)

---

## 1. Vision

JARVIS is **not a chatbot**. It is a real personal AI companion that lives on the laptop — a modern, intelligent operating layer for the computer with voice, vision, memory, reasoning, computer control, browser control, scheduling, Google integrations, and a premium desktop UI.

It will eventually be able to:

- Listen to voice and detect **"Hey Jarvis"** locally
- Understand natural language, answer questions, keep conversational context
- See and understand the screen
- Control the computer (apps, keyboard, mouse, windows) through safe tools
- Control Chrome (navigate, search, play music/videos) via Playwright
- Create notes, remember information, set reminders
- Work with Google Calendar, Contacts, Meet, Gmail, Drive
- Execute multi-step tasks, observe results, recover from failures
- Maintain long-term memory
- Speak responses back
- **Show everything it is doing** through a beautiful desktop UI — never a black box

### The target experience

```text
                 JARVIS
        ●
     Listening...

You:    "Hey Jarvis."
JARVIS: "Yes?"
You:    "Open Chrome and play Sahiba."

        🧠 Understanding
        ✓ Chrome opened
        ✓ YouTube opened
        ✓ Searching Sahiba
        ✓ Playing result

JARVIS: "Playing Sahiba."

             ●
        JARVIS READY
   Listening for "Hey Jarvis"
```

### Runtime flow

```text
Windows starts
   ↓
JARVIS background service (silent)
   ↓
Local wake-word detection  ← microphone audio NEVER leaves the machine here
   ↓  "Hey Jarvis"
UI activates → listening animation → "Yes?"
   ↓
Listen (VAD, end-of-speech detection)
   ↓
Speech-to-text
   ↓
LLM / Agent → Plan → Execute tools → Observe → (repeat) → Respond
   ↓
Text-to-speech
   ↓
Return to STANDBY
```

---

## 2. Non-Negotiable Rules

1. **Build incrementally.** One subsystem at a time. Test it. Integrate only after it works.
2. **No fake capabilities.** Never write a function that prints "Done!" when nothing happened. Every "Done" must correspond to a real, verified action. If something can't be done reliably, say so.
3. **No placeholders where real functionality is expected.** If a credential is needed, build the config path and document exactly what is required.
4. **Never replace working components unnecessarily.**
5. **Modular.** Voice, Brain, Memory, Tools, UI are independent and communicate through defined interfaces/events.
6. **The LLM never touches the OS directly.** All actions go through registered, permission-checked tools.
7. **Privacy by design.** Local wake word, no continuous audio/screen upload, visible mic/screen indicators.
8. **Document every major architectural decision** in § 14.
9. **Never commit secrets.** `.env` + `.env.example`; OS credential store for tokens.

---

## 3. High-Level Architecture

```text
                         JARVIS
                           │
            ┌──────────────┴──────────────┐
       Desktop UI                   Background Service
            └──────────────┬──────────────┘
                      JARVIS CORE
              (event bus + state machine)
        ┌──────────────────┼──────────────────┐
      VOICE              BRAIN              MEMORY
   Wake word            LLM client         Short-term
   VAD / STT            Planner            Long-term
   TTS                  Router             Episodic / Notes
        └──────────────────┼──────────────────┘
                         TOOLS  (registry + executor + permissions)
        ┌─────────┬────────┼────────┬─────────┬─────────┐
     Computer  Browser   Google   Files     Web      Vision
     Keyboard  Playwright Calendar Notes    Search   Screenshot
     Mouse     Chrome    Gmail    Memory             UI understanding
     Windows             Meet/Contacts/Drive
```

**Core principle:** subsystems publish/subscribe to events on a central bus (e.g. `WakeWordDetected`, `TranscriptReady`, `StateChanged`, `ToolStarted`, `ToolFinished`). The UI is a pure consumer of these events — it renders state, it does not own logic. This keeps the UI, the voice pipeline, and the agent testable in isolation.

---

## 4. State Machine

Formal states:

```text
STARTING → STANDBY → WAKE_DETECTED → LISTENING → TRANSCRIBING → THINKING
         → PLANNING → EXECUTING ⇄ OBSERVING → RESPONDING → STANDBY
ERROR (from any state)       SLEEPING / PAUSED (user-controlled)
```

| State | Color | Visual meaning |
|---|---|---|
| STANDBY | 🔵 blue | Calm, slow breathing orb |
| LISTENING | 🟢 green | Audio-reactive orb (mic amplitude/frequency) |
| THINKING / PLANNING | 🟡 amber | Particle / orbit processing animation |
| EXECUTING / OBSERVING | 🟠 orange | Step checklist with live progress |
| RESPONDING | 🟣 violet | Orb pulses with TTS output |
| ERROR | 🔴 red | Clear reason + Retry / Cancel |
| SLEEPING / PAUSED | ⚫ dim | Mic visibly off |

Transitions are explicit and validated — illegal transitions are rejected and logged. **The animation itself must communicate state**, not just a text label.

---

## 5. Subsystems

### 5.1 Voice
- **Passive mode:** mic → local wake-word engine only. No LLM, no cloud.
- **Active mode:** after wake word → VAD-based recording (stop when the user stops speaking, not fixed lengths) → STT.
- Must handle: silence detection, noise, interruption, cancellation, timeout, microphone errors/disconnects.
- **TTS:** natural, configurable voice and speed, streaming if possible, **immediately interruptible**.
- Never persist raw audio by default.

### 5.2 Brain (LLM / Agent)
Components: `Agent`, `Planner`, `ToolRegistry`, `ToolExecutor`, `ObservationManager`, `ConversationManager`.

Controlled loop:
```text
REQUEST → UNDERSTAND → PLAN → SELECT TOOL → (permission check) → EXECUTE
        → OBSERVE → DECIDE NEXT STEP → … → COMPLETE / RECOVER / ASK USER
```
- Structured tool/function calling only.
- Step limits and timeouts to prevent runaway loops.
- Recovery on failure: retry safely, try an alternative, or explain and ask.
- Every step emits events so the UI can show the live checklist.

### 5.3 Tools
All tools share one interface: name, description, JSON schema for args, **risk level**, async `run()` returning a structured result (`ok`, `data`, `error`) — never a bare string claiming success.

| Tool group | Capabilities |
|---|---|
| **Computer** | `open_application`, `close_application`, `mouse_move/click/double_click`, `keyboard_type/press/hotkey`, `take_screenshot`, `get_screen_size`, `focus_window`, `get_active_window` |
| **Browser** (Playwright) | `open_browser`, `navigate`, `search`, `click`, `type`, `select`, `scroll`, `extract_text`, `get_page_state`, `close_browser` — **DOM-first**, vision only as fallback |
| **Vision** | Screenshot → vision model → UI understanding → target → coordinates. Capture only on demand. |
| **Notes** | `create_note`, `search_notes`, `read_note`, `update_note`, `delete_note` |
| **Reminders** | `create_reminder`, `list_reminders`, `cancel_reminder` — persistent, survive UI close |
| **Google** (OAuth) | Calendar, People/Contacts, Gmail, Meet, Drive |
| **Notifications** | Native Windows toast notifications |

### 5.4 Memory
| Layer | Content |
|---|---|
| Short-term | Current conversation |
| Long-term | Things explicitly asked to remember ("I prefer meetings after 3 PM") |
| Episodic | Useful past events / interactions |
| Notes / Tasks / Preferences / Events | Structured records |

Start simple (SQLite, see ADR). Move to PostgreSQL + pgvector (or FAISS) for semantic recall when the need is real.

### 5.5 Safety & Permissions
| Level | Behavior | Examples |
|---|---|---|
| **LOW** | Auto-execute | Open Chrome, search, open VS Code, read screen, create note |
| **MEDIUM** | Ask confirmation | Create calendar event, send email/message, upload file |
| **HIGH** | Always confirm, show exact impact | Delete files/emails, financial actions, install software, change system settings |

```text
⚠️ CONFIRM ACTION
JARVIS wants to delete: 248 files from Downloads.
[ CANCEL ]   [ CONFIRM ]
```

### 5.6 Interruptions
- "Actually, stop." → TTS stops **immediately**.
- "Jarvis, cancel that." → current task cancelled where safely possible.
- Implemented via cancellation tokens propagated through agent → executor → tools.

### 5.7 Privacy
- Local wake word; no continuous mic or screen upload.
- Screen captured only when a tool requires it; visible "SCREEN AWARE" indicator when active.
- Clear mic-active indicator.
- Credentials in OS secure storage (Windows Credential Manager via `keyring`).
- No sensitive data in logs by default.
- Full activity/history view; one-click **Pause JARVIS**.

---

## 6. UI / UX

**Feel:** premium, calm, intelligent, futuristic. An original visual language — not a copy of any product, not a generic dashboard.

**Use:** dark-first, soft glass, subtle gradients, high-quality typography, smooth motion, strong hierarchy, generous spacing, micro-interactions, audio-reactive animation.
**Avoid:** Bootstrap-style dashboards, card overload, rainbow colors, clutter, cheap neon/sci-fi effects, pointless graphs.

### The face
The centre of the orb is a **face**: a dark head plate, two lens eyes and brows. No mouth — eyes and brows
carry the expression. It blinks, widens its pupils when it hears you, knits its brows while thinking, looks up
and away while it reasons, follows the mouse the rest of the time (so you see it look at what it clicks),
smiles with its eyes while speaking, and closes its lids when resting. One mood per state in `ui/theme.py`.

### Surfaces
1. **Floating assistant** — compact, always available, animated orb and face reflecting state.
2. **Live task view** — shows the request and a step checklist (`✓` done, `●` in progress, `○` pending).
3. **Screen-aware panel** — live preview, "👁 Looking at screen", target, action.
4. **Activity timeline** — timestamped history of everything JARVIS did today.
5. **Dashboard** — status, today's activity count, upcoming reminders/meetings, memory size, connected services, CPU/RAM/mic. Clean, not enterprise.
6. **Settings** — General, Voice, Wake Word, AI Model, Memory, Privacy, Permissions, Google, Browser, Notifications, Appearance, Keyboard Shortcuts, Logs.
7. **System tray** — Open · Pause listening · Settings · Memory · Activity · Connected services · Exit.
8. **Global hotkey** — `Ctrl+Space` (configurable) to activate manually.

### Errors are never silent
```text
🟠 JARVIS
I couldn't open YouTube.
Reason: Chrome is not responding.
[ Retry ] [ Cancel ]
```

---

## 7. Technology Choices (recommended — confirm/revise per phase in § 14)

| Concern | Recommendation | Why | Alternatives |
|---|---|---|---|
| Desktop UI | **PySide6 (Qt 6) + QML** | Native Windows, GPU-accelerated animations, frameless/translucent windows, tray support, one process with Python | Tauri/Electron + Python backend (heavier, two runtimes) |
| Wake word | **openWakeWord** | Free, fully local, ships a pre-trained "hey jarvis" model, no license key | Porcupine (excellent, but needs Picovoice key; custom words limited on free tier) |
| Audio I/O | **sounddevice** (PortAudio) | Reliable on Windows, numpy-native | PyAudio |
| VAD | **Silero VAD** | Accurate end-of-speech detection, small, local | webrtcvad |
| STT | **faster-whisper** (local, `small`/`base`, int8) | Private, fast on CPU, good accuracy | Cloud STT (lower latency on weak CPUs, less private) |
| LLM | **Claude API** (tool use) behind a provider-agnostic `LLMClient` interface | Strong tool calling & reasoning | Local via Ollama for offline/basic mode |
| TTS | **Piper** (local) default; optional cloud voice | Fast, private, free, interruptible | Edge-TTS, ElevenLabs, Kokoro |
| Browser | **Playwright** (Chromium/Chrome channel) | DOM-level automation, robust selectors | Selenium |
| Computer control | **pywin32 / pywinauto** + **PyAutoGUI** | Windows-native window mgmt; simple input | — |
| Screenshots | **mss** | Fast, multi-monitor | PIL ImageGrab |
| Storage | **SQLite** first → PostgreSQL + pgvector later | Zero setup; upgrade when semantic memory needs it | FAISS |
| Scheduler | **APScheduler** with SQLite job store | Persistent jobs | Windows Task Scheduler |
| Notifications | **windows-toasts** (WinRT) | Native Windows 11 toasts | plyer |
| Config | **pydantic-settings** + `.env` | Typed, validated config | — |
| Secrets | **keyring** | Windows Credential Manager | — |
| Logging | stdlib `logging` + JSON formatter, rotating files | Structured, no extra deps | loguru |
| Tests | **pytest** + **pytest-asyncio** | Standard | — |

> ⚠️ **Environment note:** the machine currently has **Python 3.14**. Several audio/ML packages (onnxruntime, ctranslate2 for faster-whisper, openWakeWord deps) may not yet ship 3.14 wheels. **Install Python 3.12** and use a project virtual environment (`py -3.12 -m venv .venv`).

---

## 8. Project Structure (target)

```text
JARVIS/
├── JARVIS.md               ← this file (master spec)
├── CLAUDE.md               ← how the AI engineer works on this project
├── README.md               ← setup & run instructions
├── .env.example
├── requirements.txt
├── run.py                  ← entry point
├── app/
│   ├── core/
│   │   ├── events/         ← event bus
│   │   ├── state/          ← state machine
│   │   ├── agent/          ← agent loop, conversation manager
│   │   ├── planner/
│   │   └── router/
│   ├── voice/
│   │   ├── audio/          ← mic stream, device mgmt
│   │   ├── wake_word/
│   │   ├── vad/
│   │   ├── stt/
│   │   └── tts/
│   ├── llm/                ← provider-agnostic LLM client
│   ├── tools/              ← registry, executor, base Tool
│   │   ├── computer/
│   │   ├── browser/
│   │   ├── vision/
│   │   ├── notes/
│   │   ├── reminders/
│   │   └── google/
│   ├── memory/
│   ├── scheduler/
│   ├── notifications/
│   ├── security/           ← permissions, confirmation, secrets
│   └── config/             ← settings, logging setup
├── ui/                     ← PySide6 / QML: orb, panels, tray, dashboard, settings
├── tests/
│   ├── unit/
│   ├── integration/
│   └── manual/             ← manual test scenarios (TEST-xxx)
├── scripts/                ← install, autostart registration, diagnostics
├── data/                   ← local DB, models (gitignored)
└── logs/                   ← jarvis.log, agent.log, voice.log, browser.log, errors.log (gitignored)
```

---

## 9. Configuration, Logging, Performance

**Config:** `.env` (never committed) + `.env.example`:
```text
LLM_PROVIDER=anthropic
LLM_API_KEY=
LLM_MODEL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
TTS_API_KEY=
WAKE_WORD_SENSITIVITY=0.5
HOTKEY=ctrl+space
```

**Logging:** structured, rotating, per-subsystem (`jarvis`, `agent`, `voice`, `browser`, `errors`). No raw audio, transcripts of sensitive content, tokens, or keys by default.

**Performance targets (idle):**
- CPU < 3% while in STANDBY
- RAM: lean baseline; STT/vision models lazy-loaded and unloadable
- Wake-word → UI reaction < 300 ms
- End of speech → first spoken word: aim < 2.5 s
- All I/O async; heavy work off the UI thread

---

## 10. Development Phases

| # | Phase | Scope |
|---|---|---|
| 1 | **Foundation** | Structure, config, logging, event bus, state machine, basic floating UI, system tray, start/stop |
| 2 | **Wake Word** | Autostart at login → background mic → local "Hey Jarvis" → UI activation; reliability testing |
| 3 | **Voice** | VAD + STT + TTS; "Hey Jarvis" → "Yes?" works perfectly |
| 4 | **LLM** | Questions, conversation, basic commands |
| 5 | **Computer Control** | Apps, keyboard, mouse, screenshots, windows |
| 6 | **Browser** | Playwright: open Chrome, YouTube, search, play |
| 7 | **Memory** | Remember, recall, notes, conversation history |
| 8 | **Scheduler** | Reminders, notifications, scheduled tasks |
| 9 | **Google** | OAuth + Calendar, Contacts, Gmail, Meet, Drive |
| 10 | **Vision** | Screen understanding |
| 11 | **Autonomous Agent** | Multi-step planning, observation, recovery |

---

## 11. Milestone 1 (the first real goal)

```text
Windows login → JARVIS starts automatically → wake-word detector running
→ "Hey Jarvis" → UI changes → JARVIS says "Yes?"
→ "How are you?" → STT → LLM → TTS → JARVIS answers → back to STANDBY
```
Nothing else is required for Milestone 1. **Make this reliable first.** (Covers Phases 1–4.)

---

## 12. Roadmap & Status

Legend: ⬜ not started · 🟨 in progress · ✅ done & verified

| Phase | Status | Notes |
|---|---|---|
| 1 Foundation | ✅ | Verified by user 2026-09-22. Added right-click menu on the orb (Win11 hides new tray icons under ^) |
| 2 Wake Word | ✅ | Verified by user 2026-09-22 with real voice. User's normal voice scores 0.3–0.46 (background ≈ 0.00) → user `.env` threshold 0.3. Only the full phrase "Hey Jarvis" is supported (single "Jarvis" needs a custom-trained model). Laptop mic was initially delivering silence (Acer hardware/driver mute), resolved by user. Autostart ON |
| 3 Voice | ✅ | Verified by user 2026-09-22: "Yes?" → listen → transcribe → echo reply. Whisper small: 2.7 s for 4.8 s audio, exact transcript on test sentence. Open issue: wake word needs a pause between "Hey" and "Jarvis" for this user's fast speech |
| 4 LLM | ✅ | Verified by user 2026-09-22 by voice: conversation, follow-up context, cancel, honest refusal of PC control. Gemini free tier (`gemini-3.1-flash-lite` first, failover list); first sentence 1.1–2.7 s |
| **Milestone 1** | ✅ | 2026-09-22: autostart → "Hey Jarvis" → "Yes?" → STT → LLM → TTS answer, all verified by user |
| 5 Computer Control | ✅ | Verified by user 2026-09-22 (open/type/close+confirm/volume/unknown app). Typing garble fixed (1 char per SendInput), Whisper vocabulary, follow-up mode, Porcupine "Jarvis" option (awaiting AccessKey). Mouse deferred to Phase 10 |
| 6 Browser | 🟨 | Reworked to the user's own profile + media controls; stop/barge-in; ducking; instant media commands. Plus (brought forward) coding tools and screen vision. 119 tests. Awaiting user voice test |
| 7 Memory | 🟨 | Memory (facts, to-dos, learned words, conversation log) + personality/mood, rest mode, morning briefing, break reminders. 133 tests; live-tested memory across restart and real briefing. Awaiting user voice test |
| 8 Scheduler | 🟨 | Reminders (one-off, daily, weekdays, weekly) in memory.db + Windows toasts + spoken delivery, missed-while-off handling, briefing line. 163 tests; live-tested end to end. Awaiting user voice test |
| 9 Google | ✅ | Connected to thebatmanx69@gmail.com and live-tested: calendar read, inbox read, scheduling asks first. 174 tests. Note: the user's OAuth client is a 'Web application' type, so sign-in uses the fixed redirect http://localhost:8765/ | Accepted |
| 10 Vision | ✅ | Vision-guided mouse: `click_on_screen` / `find_on_screen` / `scroll_screen` on top of `look_at_screen`. Live-tested on Calculator — 7 + 3 = 10, four clicks, four correct buttons (read back from the clipboard, not by vision). 208 tests. Awaiting user voice test |
| 11 Autonomous Agent | ⬜ | |

---

## 13. Testing

- Automated tests (pytest) for every subsystem — state machine, event bus, config, tool registry, permission checks, agent loop with a fake LLM.
- Hardware-dependent parts (mic, speakers, screen) get **manual test scenarios** in `tests/manual/`:

```text
TEST 001 — Start Jarvis
Expected: wake-word listener active · UI shows STANDBY · idle CPU low

TEST 002 — Say "Hey Jarvis"
Expected: wake word detected · UI becomes LISTENING · "Yes?" spoken

TEST 003 — Say "Open Chrome"
Expected: Chrome launches · activity log updates
```

---

## 14. Architecture Decision Records (ADR)

Each major decision is recorded here: **context → options → decision → consequences.**

| # | Date | Decision | Status |
|---|---|---|---|
| ADR-001 | 2026-09-22 | Python 3.12 venv (system has 3.14; ML/audio wheel compatibility). 3.12.10 installed via winget | Accepted |
| ADR-002 | 2026-09-22 | PySide6 6.11 + QML for UI | Accepted |
| ADR-003 | 2026-09-22 | openWakeWord 0.6 (ONNX runtime) `hey_jarvis` model, threshold 0.5, 2 s cooldown. ~2 ms per 80 ms frame. Model loads off the UI thread while orb shows STARTING | Accepted |
| ADR-007 | 2026-09-22 | Autostart via per-user `HKCU\...\Run` entry running `pythonw.exe run.py` (no admin, no console). Managed by `scripts/autostart.py` | Accepted |
| ADR-008 | 2026-09-22 | Mic stays open except when paused; detection only in STANDBY; mic failure → ERROR with reason, silent retry every 5 s, auto-recover | Accepted |
| ADR-004 | 2026-09-22 | Event bus + explicit state machine as the core integration pattern. Bus handlers run on the publisher's thread; the UI marshals to the Qt thread via a queued signal (`ui/bridge.py`) | Accepted |
| ADR-006 | 2026-09-22 | Single instance enforced with `QLockFile` in `data/` (autostart + manual launch must not double-run the mic) | Accepted |
| ADR-005 | 2026-09-22 | SQLite first, PostgreSQL + pgvector when semantic memory is needed | Proposed |
| ADR-009 | 2026-09-22 | TTS: Piper `en_GB-alan-medium` (local, 22 kHz). Fixed phrases ("Yes?") pre-rendered at startup; playback in 50 ms blocks so `stop()` is near-instant | Accepted |
| ADR-010 | 2026-09-22 | STT: faster-whisper `small` int8 on CPU, language forced to `en` (auto-detect is unreliable on short accented phrases). Loaded on wake (hidden behind "Yes?" + speech), unloaded after 5 min idle — machine has ~2 GB free RAM | Accepted |
| ADR-011 | 2026-09-22 | End-of-speech via Silero VAD (bundled with openWakeWord): 0.8 s silence ends, 5 s no-speech timeout, 15 s cap, 240 ms pre-roll. The wake-word thread owns the mic and routes frames to the recorder while LISTENING (single mic reader) | Accepted |
| ADR-013 | 2026-09-22 | Brain: Claude API, `claude-opus-5`, effort `low` for fast spoken replies, streamed; server-side `fallbacks: "default"` enabled (re-runs a safety-declined request on Anthropic's recommended fallback model). Reply spoken sentence-by-sentence as it streams. History kept in memory, append-only; reset after 10 min idle or 20 turns. Key in `.env` `CLAUDE_API_KEY`; without a key JARVIS falls back to echo replies | Accepted |
| ADR-015 | 2026-09-22 | Claude Pro subscription does not include API access, so the default provider is **Gemini free tier** (`gemini-flash-latest` alias via `google-genai`) until the user funds the Claude API. `LLM_PROVIDER=gemini|claude` switches; both share one system prompt and the same streaming `str -> Iterator[str]` interface. Note: Google may use free-tier prompts to improve its products | Accepted |
| ADR-014 | 2026-09-22 | "Cancel / never mind / stop" handled locally without the LLM. System prompt states JARVIS can't control the PC yet, so it never claims actions it didn't do | Accepted |
| ADR-016 | 2026-09-22 | Tools: one `Tool` type (JSON schema, risk, label, confirm question) + `ToolExecutor` that validates args, enforces risk (MEDIUM/HIGH → spoken yes/no confirmation; silence = no), drives EXECUTING/OBSERVING and publishes ToolStarted/ToolFinished for the orb checklist. Tools verify their effect (window appeared / closed / focused) before returning ok | Accepted |
| ADR-017 | 2026-09-22 | Apps launched via `Get-StartApps` + `shell:AppsFolder\<AppID>` (covers classic and Store apps). Fuzzy match threshold 0.85 so misheard names work but "photoshop" never opens "Photos". Typing via `SendInput` Unicode (verified: ✓, é, Hindi). Mouse tools deliberately omitted until vision (Phase 10). Tool use wired for Gemini only; Claude brain stays conversation-only until it can be tested with a key | Accepted |
| ADR-018 | 2026-09-22 | Text entry pastes via the clipboard (then restores the user's text clipboard): key-by-key `SendInput` dropped/repeated characters in Win11 Notepad even with 12 ms gaps ("hello ucky", "sscaped wwwlines"). Paste: 20/20 exact incl. 1,260 chars of Hindi/Telugu/Tamil in 0.6 s, verified by reading the text back. Key-by-key typing is only used if the clipboard holds non-text (e.g. an image) so it's never destroyed. Literal `
` from the LLM is converted to real line breaks | Accepted |
| ADR-019 | 2026-09-22 | `STT_VOCABULARY` passed to Whisper as `initial_prompt` so names are spelled right ("licky" → "Likki"), beam 1 kept (beam 5: +0.7 s, no gain) | Accepted |
| ADR-020 | 2026-09-22 | Follow-up mode: after a reply JARVIS listens `FOLLOW_UP_SECONDS` (6) more without the wake word; silence or noise ends the conversation quietly | Accepted |
| ADR-021 | 2026-09-22 | Single-word "Jarvis": Picovoice Porcupine built-in keyword (local, needs free AccessKey) selectable via `WAKE_WORD_ENGINE=porcupine`; on a missing/rejected key JARVIS shows why and falls back to openWakeWord "Hey Jarvis" | Accepted |
| ADR-022 | 2026-09-22 | ~~Separate visible JARVIS Chrome profile~~ → superseded by ADR-025 after user feedback ("use only my Chrome profile") | Superseded |
| ADR-023 | 2026-09-22 | `play_music` searches YouTube Music/YouTube, opens the first result and reports success only when playback time is advancing; skips ads when allowed and reports the real title; flags non-matching results ("closest match"). Web search uses DuckDuckGo HTML (Google captchas automated browsers). Page content is untrusted; clicks on pay/send/delete/post/sign-out labels need confirmation; no typing into password fields | Accepted |
| ADR-024 | 2026-09-22 | Gemini speed: `thinking_level=minimal` and `gemini-3-flash-preview` first (1.2–1.4 s/step vs erratic 2–12 s), failover to flash-lite on 429/5xx (free-tier quotas are small) | Accepted |
| ADR-025 | 2026-09-22 | Everything visible opens in the user's OWN Chrome profile (`CHROME_PROFILE`, default = last used) as a new tab via `--profile-directory`. Songs found via `ytmusicapi` (0.5–1.5 s), videos via YouTube results HTML; playback verified and controlled through Windows media controls (SMTC, `winrt`), which also works for Spotify/Media Player. Research (web_search/read_webpage) runs in an invisible headless Chrome. Clicking inside pages of the user's profile is not possible (Chrome 136+ blocks automation) → needs a companion extension or vision later. WinRT is imported lazily: importing it before Qt crashes Python | Accepted |
| ADR-026 | 2026-09-22 | Barge-in: the wake word is also detected while busy (transcribing/thinking/executing/responding); it sets `core.cancelled`, stops TTS and the recorder, returns to standby, and JARVIS says "Okay, stopped." once the old turn unwinds. The executor refuses further tools once cancelled | Accepted |
| ADR-027 | 2026-09-22 | Gemini models that return 429/5xx are skipped for a cooldown (429: 10 min) instead of being retried on every step (each refusal was adding seconds) | Accepted |
| ADR-028 | 2026-09-22 | Audio ducking: other apps' volume (pycaw, per-session) drops to 15% whenever JARVIS is awake/listening/busy and is restored at standby, so it neither talks over music nor mishears the user. Instant commands (pause/stop the song, resume, next, previous, volume, mute) are matched locally and run without the LLM (~1 s); bare "stop" pauses only if something is playing, else cancels | Accepted |
| ADR-029 | 2026-09-22 | Coding help (brought forward at the user's request): file tools limited to `FILES_ROOT` (user's home) excluding AppData/key folders and secret files (.env, keys) so they never reach the LLM; overwrite = MEDIUM + backup in data/backups; delete = HIGH → Recycle Bin. The active VS Code file is found from the front-most VS Code window title + VS Code's storage.json workspace folders (a keyboard-shortcut approach failed when focus was in a side panel). Long explanations go to a Markdown document opened in VS Code; only a short summary is spoken | Accepted |
| ADR-030 | 2026-09-22 | Screen vision (brought forward from Phase 10, user-approved to use Gemini): `look_at_screen` captures the primary monitor only on request, downsizes to 1600 px JPEG and asks Gemini vision; the orb checklist shows "Looking at your screen" | Accepted |
| ADR-031 | 2026-09-22 | Memory in local SQLite (`data/memory.db`): facts, to-dos, learned words, conversation log. The LLM saves facts/words on its own (`remember`, `learn_word`); facts, open to-dos and the last exchanges are injected into the system prompt with the user's name and mood-awareness guidance. Learned words extend Whisper's vocabulary live | Accepted |
| ADR-032 | 2026-09-22 | New state RESTING ("go offline"): dim-indigo still orb, mic listens for the wake word only. JARVIS starts resting and rests again when the laptop wakes (clock-gap detection). Waking from rest gives a local (no-LLM) briefing: name greeting, Open-Meteo weather for HOME_CITY, calendar note (until Google), VS Code recent projects, open to-dos → takes today's to-dos (LLM saves them) → plays MORNING_MUSIC in the user's Chrome | Accepted |
| ADR-033 | 2026-09-22 | Break reminders: continuous keyboard/mouse use (GetLastInputInfo; ≥5 min idle = break) ≥ BREAK_REMINDER_MINUTES triggers a spoken announcement when JARVIS is idle, followed by listening for the reply | Accepted |
| ADR-034 | 2026-09-22 | Roadmap re-ordered at the user's request: coding + screen vision (Phases 10–11 items) and memory/routines came before Google. Next: Google (Calendar, Gmail with send-on-confirm) | Accepted |
| ADR-035 | 2026-09-22 | Human pacing, from real logs (cut-offs like "Play some.", "CMA screen and there is a..."): end-of-speech silence 0.8 → 1.5 s, start timeout 5 → 8 s, max 15 → 30 s (all in `.env`); if a transcript ends like an unfinished thought ("and", "the", "some", "uhm", "...") JARVIS keeps listening up to 2× and joins the parts; the prompt tells the LLM to follow self-corrections ("no wait, cancel that"). "On it." is spoken as soon as the first tool starts. Measured before: STT ≈ 2 s, LLM to first word median 8.6 s (free Gemini flash-lite), up to 35 s for 11-step tasks | Accepted |
| ADR-036 | 2026-09-22 | Reminders stored in `memory.db` and delivered by a 5 s polling thread (no APScheduler needed): Windows toast (`windows-toasts`, lazy WinRT import) plus a spoken announcement when JARVIS is idle (queued up to 10 min if busy). Reminders due while JARVIS was off fire at startup, announced as missed. Times parsed from the LLM's ISO value or 'in N minutes', with clock-only times rolling to tomorrow | Accepted |
| ADR-037 | 2026-09-22 | Google via official `google-api-python-client` + installed-app OAuth (`scripts/google_login.py`, token in `data/`, gitignored). Scopes: calendar.events/readonly, gmail.modify + gmail.send, contacts.readonly. Creating meetings and sending/replying to mail are MEDIUM risk → spoken confirmation quoting the text; email/calendar content is declared untrusted in the prompt (prompt-injection defence). Attendee names resolved via Contacts; unknown names are reported, never guessed | Accepted |
| ADR-038 | 2026-09-23 | Dashboard window (QML, same dark language as the orb): Overview (today's counts, meetings, reminders, connected services, CPU/RAM, type-to-JARVIS box), Activity (live timeline from the event bus, 200 entries) and Settings (curated `.env` editor that keeps comments and order, flags settings needing a restart, and can restart JARVIS). Opened from the tray/orb menu | Accepted |
| ADR-039 | 2026-09-23 | Global shortcut (`HOTKEY`, default Ctrl+Space) via RegisterHotKey + a Qt native event filter; wakes JARVIS without the wake word (and never gives the morning briefing). Typed requests from the dashboard run the same pipeline as speech (`typed` turn kind) | Accepted |
| ADR-040 | 2026-09-23 | Vision-guided mouse: Gemini returns the click point as JSON `[y, x]` in 0–1000 normalised coordinates, converted to mouse pixels via the display-scaling ratio. JARVIS photographs the **active window**, not the whole screen (a whole-screen shot made calculator keys ~4% of the frame and the first live test clicked '+' instead of '3', computing 7+7=14); `whole_screen=true` is available for the taskbar and desktop. Targets matching buy/pay/delete/send/… are MEDIUM risk → spoken confirmation. If another window comes to the front between the screenshot and the click, the click is refused rather than sent to a stale position | Accepted |
| ADR-041 | 2026-09-23 | JARVIS has a face, modelled on the Sphere in Las Vegas (`ui/sphere.webp`): a large pale lit sphere with two round white eyes and thin curved brows, and no mouth. The sphere is warm white washed 42% with the state colour, so it stays a friendly pale sphere while the state is still readable across the room. One mood per state in `ui/theme.py` (`STATE_FACES`); `ui/qml/Face.qml` turns a mood into eye openness, brow lift/angle and pupil size, so the QML holds only rendering. Eyes close by squashing while a drawn curve fades in, which also gives the smiling arc eyes while speaking. It blinks on an irregular 2.2-6.4 s rhythm, widens its pupils with the microphone level, looks up and away while thinking, and otherwise follows the real mouse cursor (20 Hz, stopped while resting) - so it visibly looks at what it is about to click. Face is a cached layer: the window repaints at 60 fps for the halo, and re-drawing the face every frame cost 0.80% -> 4.09% idle CPU; cached, the whole orb UI measures 1.12% with the face contributing 0.09% | Accepted |
| ADR-042 | 2026-09-23 | Two honesty fixes. (1) `press_keys` reported ok=True for Win+L, which Windows silently ignores (a protected sequence), so JARVIS truthfully said it had locked a PC that was still open: added a real `lock_pc` tool on `LockWorkStation()` that reports success only after `OpenInputDesktop` confirms the lock screen is up, and `press_keys` now refuses Win+L and Ctrl+Alt+Delete with a message naming the right tool. The prompt also never said the tools were the limit of what JARVIS can do - it does now. (2) The full morning briefing fired on every wake from rest (several times a day, and after every restart); it is now recorded in a `notes` table in memory.db and given once per calendar day - later wakes are a short greeting with no weather, to-do prompt or morning video | Accepted |
| ADR-012 | 2026-09-22 | Voice turn runs in `VoicePipeline` on its own thread; every step uses `transition_from` so pause/cancel mid-turn aborts cleanly. Responder is a pluggable `str -> str` (echo in Phase 3, LLM in Phase 4) | Accepted |
