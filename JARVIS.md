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
| 2 Wake Word | ✅ | **Single word "Jarvis" works** (2026-09-23), using the community `jarvis_v1.onnx`. Measured on the user's voice: "Jarvis" 0.982, "Hey Jarvis" 0.997, ordinary speech 0.001 → threshold 0.5. The old built-in `hey_jarvis` scored only 0.146/0.067 on the same voice, which is why the wake word had been unreliable from the start. Laptop mic was initially delivering silence (Acer hardware/driver mute), resolved by user. Autostart ON |
| 3 Voice | ✅ | Verified by user 2026-09-22: "Yes?" → listen → transcribe → echo reply. Whisper small: 2.7 s for 4.8 s audio, exact transcript on test sentence. Open issue: wake word needs a pause between "Hey" and "Jarvis" for this user's fast speech |
| 4 LLM | ✅ | Verified by user 2026-09-22 by voice: conversation, follow-up context, cancel, honest refusal of PC control. Gemini free tier (`gemini-3.1-flash-lite` first, failover list); first sentence 1.1–2.7 s |
| **Milestone 1** | ✅ | 2026-09-22: autostart → "Hey Jarvis" → "Yes?" → STT → LLM → TTS answer, all verified by user |
| 5 Computer Control | ✅ | Verified by user 2026-09-22 (open/type/close+confirm/volume/unknown app). Typing garble fixed (1 char per SendInput), Whisper vocabulary, follow-up mode, Porcupine "Jarvis" option (awaiting AccessKey). Mouse deferred to Phase 10 |
| 6 Browser | 🟨 | Reworked to the user's own profile + media controls; stop/barge-in; ducking; instant media commands. Plus (brought forward) coding tools and screen vision. 119 tests. Awaiting user voice test |
| 7 Memory | 🟨 | Memory (facts, to-dos, learned words, conversation log) + personality/mood, rest mode, morning briefing, break reminders. 133 tests; live-tested memory across restart and real briefing. Awaiting user voice test |
| 8 Scheduler | 🟨 | Reminders (one-off, daily, weekdays, weekly) in memory.db + Windows toasts + spoken delivery, missed-while-off handling, briefing line. 163 tests; live-tested end to end. Awaiting user voice test |
| 9 Google | ✅ | Connected to the user's Google account and live-tested: calendar read, inbox read, scheduling asks first. 174 tests. Note: the user's OAuth client is a 'Web application' type, so sign-in uses the fixed redirect http://localhost:8765/ | Accepted |
| 10 Vision | ✅ | Vision-guided mouse: `click_on_screen` / `find_on_screen` / `scroll_screen` on top of `look_at_screen`. Live-tested on Calculator — 7 + 3 = 10, four clicks, four correct buttons (read back from the clipboard, not by vision). 208 tests. Awaiting user voice test |
| 11 Autonomous Agent | 🟨 | First increment: recovery. A LOW-risk tool that crashes gets one automatic retry (never an ordinary `ok=False`, and never MEDIUM/HIGH), re-checking cancellation, invisible to the UI checklist. "Try an alternative" and "explain and ask" already happen via the existing per-step tool-calling loop. Still missing: an explicit upfront plan the user sees before a multi-step task starts, and a higher step budget for genuinely long tasks (still capped at 8). See ADR-083 |
| 12 Phone | 🟨 | Web remote **and** a native Android app. Installed on the user's OnePlus and verified live: certificate pinned, all permissions held, floating face running, and speech carried from the phone to a real action ("Yeah, open my WhatsApp."). Then three audio faults found and fixed (ADR-078); awaiting a re-test of listening range and full-sentence playback |

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
| ADR-019 | 2026-09-22 | `STT_VOCABULARY` passed to Whisper as `initial_prompt` so names are spelled right ("licky" → "Alex"), beam 1 kept (beam 5: +0.7 s, no gain) | Accepted |
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
| ADR-043 | 2026-09-23 | Listening was cutting the user off mid-thought: end-of-speech silence 1.5 -> 2.2 s, start timeout 8 -> 10 s, max utterance 30 -> 60 s, and up to 3 continuations. The unfinished-thought regex now has two groups - words that never end a sentence ("and", "the", "some", even with a full stop) and words that only continue when no full stop follows ("that", "on", "if"), so "Play some." keeps listening while "Turn it on." does not | Accepted |
| ADR-044 | 2026-09-23 | Friends: the ten names are stored as a memory fact and as learned words (so Whisper expects them) and added to STT_VOCABULARY. The persona prompt handles "say hi to my friends" - ask who is there, then greet that person by name and rib them the way close friends do, explicitly fond and never about looks, family, money or work. Verified live | Accepted |
| ADR-045 | 2026-09-23 | Unlocking the PC by voice is refused, not deferred. Windows takes credentials only on the Winlogon secure desktop, which no ordinary application can reach; the only route is a custom credential provider, and a spoken pass phrase is trivially replayed by a recording or anyone standing nearby. Windows Hello is the supported answer - this laptop has a FocalTech fingerprint reader but no IR camera, so fingerprint is the option | Accepted |
| ADR-046 | 2026-09-23 | JARVIS follows the lock screen. "Lock my PC" is an instant command (no LLM) that locks and says **nothing** - the screen is going, so a spoken confirmation is noise. A `LockWatcher` polls `session.is_locked()` once a second (one `OpenInputDesktop` call): on lock it interrupts whatever JARVIS was doing and rests, so the same happens when the user locks by hand; on unlock it leaves rest and announces "Hey <name>, I'm ready." - a greeting, never the morning briefing. Polling is used because Windows offers no session-change signal an ordinary app can wait on without a window handle | Accepted |
| ADR-047 | 2026-09-23 | More answers without the LLM, because the free Gemini tier had been rate-limited 74 times and every LLM turn costs ~9 s. `app/voice/quick.py` gains a second kind of instant command that reads the phrase (`open <app>`, `switch to <app>`) or answers from the machine (time, date, battery, screenshot, "thank you"). A handler returning None passes the request on to the LLM, so "open my emails" still reaches Gmail while "open notepad" never leaves the machine. "Thank you" is included because the transcriber hallucinates it on silence, which was costing a full LLM round trip | Accepted |
| ADR-048 | 2026-09-23 | Single-word "Jarvis" without Picovoice. The Picovoice console locked the user's account behind commercial-use approval (work email domain) and refused a personal Gmail, so Porcupine is out. openWakeWord has no pre-trained bare "Jarvis", but the Home Assistant community collection has `en/jarvis/jarvis_v1.onnx` and `jarvis_v2.onnx`, both trained on "jarvis" and "hey jarvis" (v1 more sensitive, v2 fewer false positives). `load_openwakeword` now accepts a file name in `data/models/openwakeword` as well as a pre-trained name. Both score 0.997-0.999 on a real recording of the user saying "Hey Jarvis" and ~0.001 on three clips of their other speech; synthetic Piper clips are useless for judging them (the built-in model was trained on TTS audio and scores 0.998 on anything synthetic, the community models ~0.001), so the bare-"Jarvis" case is decided by `scripts/try_wake_words.py`, which records the user and scores all three. Result on the user's own voice: jarvis_v1 scored 0.982 on "Jarvis" and 0.997 on "Hey Jarvis" against 0.001 on ordinary speech, while jarvis_v2 was deaf to them (0.003) and the built-in hey_jarvis managed only 0.146/0.067 - so the wake word had been failing for a year-old reason nobody had measured. Shipped: jarvis_v1.onnx at threshold 0.5 | Accepted |
| ADR-049 | 2026-09-23 | The screen glows at its edges while JARVIS is looking at it, the way a call shows you are sharing. `ui/qml/ScreenGlow.qml` is a frameless, click-through (`WS_EX_TRANSPARENT`), always-on-top overlay over the whole screen; `ui/screenglow.py` shows it while any of look_at_screen / click_on_screen / find_on_screen / take_screenshot is running. It is driven by tool **events**, not called by the tools, so the UI stays a pure consumer - which needed the tool's name adding to ToolStarted/ToolFinished. It hides for the few hundred ms of the actual grab so JARVIS never photographs its own glow. First attempt reached 130 px in at 0.55 alpha and washed out a third of the screen; shipped at 78 px with a fast falloff | Accepted |
| ADR-050 | 2026-09-23 | Sun while ready, moon while asleep. STANDBY turns warm gold with a slowly turning corona of rays; SLEEPING and RESTING turn pale silver-blue, the sphere gains craters, and a starfield drifts behind the panel (two cached textures, only their position animates). `STATE_SKY` in `ui/theme.py` maps the state, so QML only renders. Measured: 0.71% CPU as the sun, 1.06% as the moon, against a 1.12% baseline | Accepted |
| ADR-051 | 2026-09-23 | Two bugs found in real use. (1) Every page JARVIS wrote had broken images because it used `via.placeholder.com`, which is dead (verified: times out; `source.unsplash.com` 503s too). The prompt now names picsum.photos and placehold.co, both verified live, and forbids the dead ones. (2) Told to overwrite, it made `_v2` and `_new` files instead: `write_file` was MEDIUM risk for any existing file, so overwriting meant a spoken confirmation and the model routed around it. FileAccess now remembers the files JARVIS itself wrote and treats rewriting them as LOW risk - a backup is still kept, it just doesn't interrupt. Someone else's file still asks | Accepted |
| ADR-052 | 2026-09-23 | Character animation. Asleep: the brows are put away entirely and three z's drift up from the sphere's shoulder - they live in Orb.qml, not Face.qml, because the face's cached layer clips anything that leaves the sphere. Awake: the corona is two wavy rings turning against each other - a closed polyline whose radius rises and falls (11 and 8 lobes), built once at load so only rotation, scale and opacity animate. Straight rays were tried first and looked mechanical. Waking from sleep fires a burst - the face bounces twice (OutBounce), the eyes gleam (catch-light flare plus a second spark) and a warm ring breaks outward. It triggers only on moon -> sun, so returning to standby after every reply does not set it off. Gaze reach 520 -> 380 px and pupil travel 5 -> 9 px, so the eyes swing much further for the same movement. Measured 1.14% CPU as the sun, 1.03% as the moon, against a 1.12% baseline. The z's are bright cyan with a dark outline so they read across the room; note the offscreen test platform has no fonts at all, so text is always tofu in rendered contact sheets | Accepted |
| ADR-053 | 2026-09-23 | Every state is a body in the solar system, and the panel behind takes its colour: Mercury starting, **Sun** ready, Venus at the wake word, Earth listening, Neptune understanding, Jupiter thinking, Mars working, Uranus checking, Saturn answering, **Moon** paused or resting. An error stays plain red - it should not look pretty. `STATE_BODY` in `ui/theme.py` maps it; `sky` is now derived (sun/moon only) so the corona, stars and z's still key off it. Each body is drawn with markings - craters, bands, a storm, seas, polar caps, and rings outside the sphere for Saturn - all static, inside the face's cached layer. `clip: true` clips to a rectangle, not a circle, so bands and caps ran off the sphere's edge; they are now sized by a chord measured at their narrowest point. The plain orbit ring and its arc fade out for the sun, whose wavy corona is the ring | Accepted |
| ADR-054 | 2026-09-23 | Renamed to **JAS** (Jarvis was taken). `ASSISTANT_NAME` in settings drives the orb, the dashboard, the tray, the toasts, the Windows app name and the system prompt - nothing user-facing is hard-coded any more. The **wake word stays "Jarvis"**: it is a trained model, the community collection has 102 words and none is JAS, and training one needs 25,000 synthetic examples. The repo folder, module names and log files keep the old name deliberately - renaming them would break paths for no benefit | Accepted |
| ADR-056 | 2026-09-23 | Commands are addressed to JAS, not Jarvis. `normalise()` strips a leading "JAS" however the transcriber spells it (JAS, Jass, Jazz, Jaz), but only at the start of an utterance and never before music/song/playlist/radio/track/album - stripping it anywhere would turn "play jazz music" into "play music". JAS is in STT_VOCABULARY so Whisper expects it. What JAS *says* to the user is `WAKE_PHRASE`, separate from the wake-word model, so the wording can change the moment the model is confirmed to answer to JAS - `scripts/try_wake_words.py` now records exactly that test | Accepted |
| ADR-057 | 2026-09-23 | The Claude brain can use tools, so `LLM_PROVIDER=claude` is now a real option rather than conversation-only (superseding that part of ADR-017). `app/brain/claude.py` runs the same loop as Gemini - model, tool calls, results, model - with the same 8-step limit, the same streaming so speech starts on the first sentence, and the same executor, so risk levels and spoken confirmations are unchanged. The system prompt and the tool schemas are marked `cache_control: ephemeral`: they are ~5,500 identical tokens on every request and a cache read costs a tenth of normal input, which is most of the bill for short spoken replies. Default model is Haiku 4.5 ($1/$5 per MTok) rather than Opus 5 ($5/$25) - about six times cheaper for this workload and faster, which matters more for speech. **Vision stays on Gemini**: it is wired from `GEMINI_API_KEY` independently of `LLM_PROVIDER`, so setting the provider to claude gives Claude's reasoning with Gemini's eyes and keeps image generation possible. Tested with a faked client (7 tests); not yet run against the live API | Accepted |
| ADR-058 | 2026-09-24 | Real Excel work through COM instead of vision-clicking the ribbon, which is what JAS was reduced to and why it stalled. Eight tools: open, sheet_info, read, write (values or formulas), autofit, sort, pivot_table, save. Four things had to be got right, each found by testing against real Excel rather than trusting a tool's own report. (1) Excel started from the shell does **not** register for automation; one opened through COM does - hence `excel_open`, and the app is cached for the session. (2) Late-bound COM collections cannot be iterated (`Workbooks.Count` is 1 but iterating yields broken objects) and `Address` is a string not a method - both now handled. (3) A parameter named `range` shadowed the builtin and broke sorting with "'str' object is not callable". (4) `Range.Sort` silently does nothing with a stale sort state, so the Sort object API is used and the result is **verified by re-reading the column** - a sort that did not happen reports failure. Modal dialogs ("keep this format?") are suppressed around anything that can prompt, since they block COM invisibly. The workbook is copied to data/backups before the first change, because COM edits bypass Excel's undo | Accepted |
| ADR-059 | 2026-09-24 | Latency, measured rather than guessed. A turn is end-of-speech wait + speech-to-text + LLM + speech: 2.2 s + 2.0-4.0 s + **1.6-30.4 s (median ~14 s)** + 0.4 s. The LLM is ~74% of it and the free Gemini tier has got slower (8.6 s median in Sept, ~14 s now, with 30 s spikes). Two free cuts: the end-of-speech wait drops 2.2 s -> 1.3 s, which is safe now that the unfinished-thought net reopens the mic up to 3 times; and the common Excel jobs ("compact column A", "fit the columns", "save the file") became instant commands, removing the whole LLM round trip from them. Whisper is already at beam_size=1 and int8, and `vad_filter` made no difference on a real clip (3.76 s either way), so speech-to-text needs a smaller model to improve - a trade against accuracy on this user's accent, not taken yet. Millisecond replies are not reachable while any LLM is in the loop; only the instant-command path can approach it | Accepted |
| ADR-060 | 2026-09-24 | Saying "stop" while JAS is answering now stops it. The wake word already interrupted, but only the word "Jarvis"; people say "stop". `app/voice/bargein.py` runs a second recorder fed by the wake-word service whenever the state is busy, and transcribes any short utterance it catches. The decision is made on the **transcript**, never on speech alone: JAS's own voice returns through the microphone, and treating any sound as a stop would make it cancel itself constantly - but its own words transcribe to its own sentence and simply do not match. That makes a false detection harmless. Capped at 4 s of audio, and it has its own Silero VAD instance because that model is stateful and sharing one with the main recorder corrupts both | Accepted |
| ADR-061 | 2026-09-24 | Model list reordered from measurement, not assumption. `gemini-3-flash-preview` was **first** and is 429-exhausted on the free tier (87 failures in one day), so every request wasted a round trip before falling back - that is what "Gemini limit reached" was. Measured live: flash-lite-latest 1.57 s, 3.1-flash-lite 2.73 s, flash-latest 3.62 s, 3-flash-preview 429, and both 2.5 models now 404. The preview model is dropped and the fastest working one leads | Accepted |
| ADR-062 | 2026-09-24 | Learning from outcomes (the user's "RLCD"). Training the weights is not possible - no fine-tuning on Gemini's free tier and the weights are not ours - so the loop is act, observe, keep the lesson, put it in the next prompt. The rewards already existed and were being discarded: a tool returning ok=False is a negative signal, and the user saying "stop" mid-task is a stronger one, since they are objecting in the moment. Both are recorded in an `outcomes` table against the request that caused them. Only a mistake repeated twice becomes a lesson (one is noise), at most six lessons reach the prompt, worst first, and an interrupt that was not the user's (a screen lock) is not held against the tool | Accepted |
| ADR-063 | 2026-09-24 | Three browser/music failures found by counting real errors in the logs rather than asking what felt broken. (1) `asyncio.run()` cannot be called when a loop is already running, and Playwright's sync API runs one on the calling thread - so every media check after a browser action crashed. Media calls now run on a private loop on a private thread, verified working from inside a running loop. (2) "Started Chrome but no window appeared" was reported when the URL opened as a **tab** in an already-open Chrome: no new window exists, only a title change, so window titles are now compared as well as handles. (3) A headless browser killed mid-navigation surfaced as "Target page, context or browser has been closed"; searches and page reads now restart the browser and retry once, while any other Playwright error still surfaces rather than being retried into confusion | Accepted |
| ADR-064 | 2026-09-24 | JAS guards the lock screen. It **cannot draw on it** - Winlogon's secure desktop admits only Microsoft's UI and registered credential providers - but an ordinary app may set the lock screen **image**, so JAS's face is there instead. Two faces are drawn with Pillow (the orb lives on the Qt thread and this runs from the watcher's): gold and level-browed "<name>'s PC / JAS is watching", and red and scowling "Don't touch Alex's PC". Wrong passwords are detected **without administrator rights** via `NetUserGetInfo` level 3 `bad_pw_count` - the Security event log needs admin and was refused, this is not. On lock JAS records the count and shows the watchful face; a rise switches it to angry, once, rather than thrashing the API; on unlock it returns to watchful and the greeting says how many attempts there were | Accepted |
| ADR-065 | 2026-09-24 | The same face goes on the **desktop wallpaper** too, via `SystemParametersInfoW(SPI_SETDESKWALLPAPER)` - no admin needed - and the lock watcher changes both together, so JAS's mood follows the user either way. The wallpaper version is the circle alone: the desktop already has icons on it, while the lock screen keeps the words because that is where a warning belongs. Two requests could not be met and were not faked: **eyes cannot follow the mouse on the lock screen** (nothing of ours runs on the secure desktop, so the image is static), and **the sign-in blur** needs `HKLM\SOFTWARE\Policies\Microsoft\Windows\System\DisableAcrylicBackgroundOnLogon`, which is an administrator write - offered to the user as one elevated command rather than done silently | Accepted |
| ADR-066 | 2026-09-24 | Two bugs the logs exposed once the lock screen was live. (1) The greeting said "0 wrong passwords" even though the angry face had fired: Windows **zeroes `bad_pw_count` on a successful sign-in**, so by greeting time the evidence is gone. The watcher now keeps the highest count seen during the lock rather than re-reading it. (2) "Empty reply" was raised as a RuntimeError when the model ended a turn after its tool calls without speaking - the user got an ERROR orb and "something went wrong" for work that had actually been done. It now says "Done." if a tool ran and asks them to repeat if nothing did, because reporting a failure for a success is the one thing this project must never do | Accepted |
| ADR-067 | 2026-09-25 | JAS answers questions about a spreadsheet instead of reading it. Three tools: `excel_calculate` runs any Excel formula through `Application.Evaluate` **without writing it into the sheet**, so SUM/COUNTIF/SUMIF/AVERAGE/INDEX+MATCH all work read-only and one question costs one call instead of pulling 89 rows into the prompt; `excel_find` returns every row containing a name, id or code; `excel_compare` shows where two columns differ. `excel_sheet_info` now also returns a few real rows so the model can see the shape before deciding. Two bugs the live test caught: INDEX/OFFSET return a *reference*, so the model was handed a COM object rather than a value (now resolved through .Value), and comparing whole columns counted the header row as a difference. Verified against a real workbook: 9 of 9 questions answered correctly, each checked against the known answer | Accepted |
| ADR-068 | 2026-09-25 | Four more Excel commands - filter, insert/delete rows and columns, formatting (bold, colour, number format, freeze header) and charts - chosen because tool schemas are not free: 15 Excel tools already cost 1,604 tokens on **every** request, so breadth is traded against latency deliberately rather than adding one tool per phrase. Deleting rows asks first; inserting does not. Two bugs the live test caught: `format` had no default for `range`, so "freeze the header row" on its own raised a TypeError; and `SpecialCells(xlCellTypeVisible).Rows.Count` counts only the **first** block, so a filter matching three scattered rows reported one. Verified 9 of 9 against a real workbook, each checked by re-reading the sheet | Accepted |
| ADR-069 | 2026-09-25 | Pausing is silent. A test that flaked only under load turned out to be a real race: for a moment after `pause()` the state is still STANDBY, so the worker announced "Okay, stopped." to someone who had just muted JAS. The interrupt reason is now checked and a paused stop says nothing | Accepted |
| ADR-070 | 2026-09-25 | JAS on the phone is a **remote, not a port**. Porting would lose the only reason it is useful - Win32 and COM drive Excel, the windows and the Chrome profile, and none of that exists on Android or iOS - so a phone-native JAS would be a chatbot with no hands. Instead `app/remote.py` serves a small page over the home network with aiohttp (already a dependency) and feeds what you type into `core.ask_text`, the same path the dashboard uses, so the phone gets the whole assistant rather than a cut-down copy. Security: every request carries a six-digit PIN kept in memory.db so it survives restarts, and it is bound to the LAN and never the internet. Known limits: same Wi-Fi only, and the laptop must be awake. Voice from the phone is the next step - recording there and transcribing here, so it works on any phone and the audio never leaves the machine | Accepted |
| ADR-071 | 2026-09-25 | The phone speaks the answer, in JAS's own voice rather than the phone's robot one: `Speaker.render` returns the same Piper audio as a WAV and `/voice` serves the latest reply. Two things this forced. (1) A request from the phone sets `core.quiet`, so the laptop does **not** say the answer out loud in an empty room - every speech call in the pipeline now goes through one guard so that cannot be forgotten, and the flag lasts a single turn. (2) Phones refuse to play audio until the user has interacted, so the page unlocks playback on the first tap with a silent clip and tells the user to tap if it is still blocked. Audio is rendered once per reply and cached against a reply id, because the phone polls and synthesising on every poll would be wasteful. Verified end to end: asked from the phone, answered "It's 12:59 PM", 90 KB of valid WAV returned | Accepted |
| ADR-072 | 2026-09-25 | Talking into the phone. The page captures **raw audio** through the Web Audio API, resamples to 16 kHz and writes the WAV header itself, rather than using MediaRecorder - that produces webm or m4a depending on the phone and would need ffmpeg on the laptop to decode. Encoding in the browser means any phone sends exactly what Whisper wants and the laptop needs no audio decoder at all. The clip is transcribed **here**, on the same Whisper JAS already uses, so the recording never goes to a cloud and the accuracy matches talking to the laptop directly. Hold-to-talk uses pointer events so it works with touch and mouse alike; clips under 2 KB are dropped without waking Whisper. Verified end to end with a real recording of the user: 151 KB in, "How are you today? Please open Chrome and play some music." transcribed in 6.1 s, Chrome opened, music started, and 212 KB of reply audio returned for the phone to speak | Accepted |
| ADR-073 | 2026-09-25 | The phone remote is HTTPS, because Chrome refused the microphone: browsers only allow `getUserMedia` on a secure origin, and a LAN IP over http is not one. No authority will sign a certificate for 192.168.x.x, so JAS makes its own with `cryptography` (already a dependency) covering both the laptop's IP and localhost, valid ten years and written once to data/certificates - a fresh certificate each restart would make the phone warn every time. The phone shows one "not private" warning and remembers the choice; that is inherent to a private address with no public name, not a fault. Verified: HTTPS serves and plain http no longer answers | Accepted |
| ADR-074 | 2026-09-25 | The phone gets the real face, not a coloured circle. `ui/phone.html` and `ui/phone.js` (real files now, not a string inside remote.py) draw the sphere in SVG with the same eight moods, the same planets - craters, bands, seas, Saturn's rings - the same irregular blink and eyes that follow your thumb as the eyes follow the mouse on the laptop. The mood and planet tables are duplicated in JS because the phone cannot import `ui/theme.py`; a test asserts every mood and body name appears in the served page so the two cannot drift apart silently. Edge lighting glows the screen border in the state colour while JAS is listening or working. **Not possible and not attempted:** waking on a long-press of the power or volume button - a web page cannot intercept hardware buttons, and no app may take the power button at all. A wake word on the phone would mean running the model in the browser and only works while the page is open; not built | Accepted |
| ADR-075 | 2026-09-25 | JAS installs on the phone as an app rather than living in a browser tab: a web manifest (`display: standalone`), a service worker that caches **nothing** (a stale answer is worse than no answer; it exists only because browsers will not offer to install without one) and icons drawn from the same face as the lock screen, rendered once per size. Installed, it has its own icon, its own window and its own entry in the app switcher, with no address bar. The eyes now follow the **phone's tilt** through `deviceorientation` - gamma for left-right, beta for front-back - with a thumb on the screen taking priority for 2.5 s, and iOS asked for permission on first tap since it withholds motion otherwise. **Still not possible:** a floating bubble over other apps needs `SYSTEM_ALERT_WINDOW`, which only a native Android app can hold - no web page can, whatever it is installed as | Accepted |
| ADR-076 | 2026-09-25 | The phone listens by itself. Holding a button is not how you talk to an assistant, so the microphone opens when the app does and a sentence is sent when the speaker stops - energy above a threshold starts it, 1.1 s of quiet ends it, under 350 ms is discarded as a cough. Three things this forced: the microphone is ignored while JAS is speaking through the same phone, or it hears its own reply and loops; listening stops on `visibilitychange` because holding the microphone behind other apps drains the battery for nothing; and Pause and Hide were added to match the laptop. Chrome also **refuses to install a web app from an untrusted site**, which is why the self-signed certificate blocked installation - it is now downloadable at `/JAS.crt` so the phone can be told to trust this laptop, which removes both the warning and the refusal | Accepted |
| ADR-077 | 2026-09-25 | JAS is a **native Android app** (`android/`, Kotlin, minSdk 26), because the one thing the user asked for is the one thing no web page may ever have: `SYSTEM_ALERT_WINDOW`, the permission to float over other apps. The app is still a client - the laptop keeps the brain, the tools and Whisper - so it is seven small files against the existing `/state`, `/listen`, `/voice` and `/ask`: a foreground service holding the draggable face, the sphere redrawn on Canvas with the same nine moods and the same planets, always-on listening at the thresholds the web version settled on (0.018 energy, 1.1 s of quiet, 350 ms minimum), AudioTrack playback that walks the RIFF chunks instead of assuming a 44-byte header, and edge lighting in an untouchable overlay so the app underneath keeps working. **Certificate pinning instead of installing a CA.** Chrome had refused to install the web app from an untrusted origin and telling the phone to trust `JAS.crt` proved awkward, so the app remembers the exact certificate it met first and then accepts only that one - the bargain SSH makes. That removes the certificate install entirely and is strictly safer than trusting anything that answers; when the laptop's IP changes it signs a new certificate, so the app says exactly that and offers **Pair again**. Toolchain: JDK 17, SDK 34, Gradle 8.7, all under `C:\jas-tools` because the SDK's own .bat scripts do not quote JAVA_HOME and the space in the user's home directory broke `sdkmanager` outright. **Verified:** builds clean and the APK is signed, 3.2 MB, carrying SYSTEM_ALERT_WINDOW and FOREGROUND_SERVICE_MICROPHONE. **Not verified:** that it runs - that needs the user's phone, and `tests/manual/android.md` has the 13 checks. **Still impossible and documented as such:** a power-button long-press (Android gives that gesture only to the registered device assistant, replacing Google Assistant system-wide), a wake word on the phone (it would cost battery all day for nothing, since the face being on screen already means it is listening), and working away from the house | Accepted |
| ADR-078 | 2026-09-25 | Three real faults found by using the Android app, two of them mine. (1) **Every reply was cut to 0.4 s** - "hey shantanu" came out "hey shan.ta". `AudioTrack.write` only fills a buffer, so waiting a fixed 400 ms and then calling `flush` destroyed the rest; the buffer was also sized to the whole clip, so `write` returned without playing anything. Playback now waits on `playbackHeadPosition`, the only honest answer to "has this been played", with a deadline so a stalled track cannot hang the thread, and the buffer is half a second so `WRITE_BLOCKING` keeps us in step. (2) **A cough woke Whisper.** `MIN_MS` was measured across the whole clip, and every clip ends with the 1.1 s of silence that closed it, so a 100 ms blip cleared a 350 ms bar every time - Whisper then hallucinated on the near-silence, which is where "Thank you." from an empty room came from. Now only time spent above the threshold counts, frame by frame, and a clip that fails is dropped rather than sent at the 15 s cap. The same bug was in `ui/phone.js`, since the Kotlin was written from it; both fixed. (3) **Fixing that, I over-corrected** and added a fixed peak gate of 0.045, which threw away ordinary speech and anything from another room. Replaced with thresholds measured against the room itself - an exponential average of the level while nobody is talking, speech starting at 2.5x that and accepted at 4x - so one setting works in a silent bedroom, beside a fan, and from the next room. Every clip now logs its duration, peak, requirement and room level, so the next round of tuning uses the user's real numbers instead of my guesses. On the laptop, `is_hallucination` drops what Whisper returns for silence, and deliberately does **not** include yes, yeah, ok, no, sure, stop or cancel - it had them at first, which would have broken confirmations and barge-in, the two paths that must work on a single word | Accepted |
| ADR-079 | 2026-09-26 | Three things the phone needed before it could be called working. (1) **It only acts when JAS is called by name.** The microphone is open the whole time the face is showing, so it hears the room: in four minutes of somebody else's conversation it sent 72 clips and tried to act on "Namkotas too" and "Amazon is an external API power". No loudness threshold can help, because that audio IS speech - it simply was not addressed to JAS. The check is on the transcript, on the laptop, since the laptop is transcribing anyway: no model on the phone, no battery cost. Whisper spells the name several ways and "jazz" is the commonest, which the barge-in phrases already knew. After a reply there is a 25 s window where no name is needed, so a conversation is not "jas" every line, and `stop` never needs the name at all. (2) **The phone pins the laptop's public key, not its certificate.** The router gave this laptop three addresses in two days - .131, .118, .111 - and the certificate names the address, so pinning the certificate made every move look like a different machine. One key is now kept for the laptop and a certificate minted per address from it; a kept certificate is checked against the key before being served, because one signed by an older per-address key would fail the handshake. This is also what certificate pinning is supposed to mean. (3) **The phone finds the laptop instead of being told where it is.** `app/beacon.py` answers "JAS?" on UDP 8771 with its address; the app broadcasts that when it cannot reach the laptop and re-learns where it moved to, so only the PIN is ever typed in. UDP broadcast rather than mDNS: a dozen lines, and Android's mDNS support is uneven. The reply carries the address and nothing else - finding JAS grants nothing, since every real request still carries the PIN and the laptop is still recognised by its key. A taken port degrades to typing the address by hand rather than failing. **Verified end to end on the real network:** broadcast found 192.168.0.111:8770, the key fingerprint was the one minted when the laptop was .118, and `/state` answered | Accepted |
| ADR-080 | 2026-09-27 | JAS is reachable from outside the house, over Tailscale rather than a forwarded router port. WSS/WebSocket was the user's first idea and does not solve the actual problem: the laptop sits behind NAT, so there is no address to connect *to* from outside, whatever protocol rides on top. Tailscale gives the laptop a stable private address (`100.x.y.z`) that both devices can reach once they are on the same tailnet, with no port opened on the router and no third party ever seeing the traffic unencrypted. Verified: JAS answers `/state` over the Tailscale interface with zero server changes, because `web.TCPSite` already binds `0.0.0.0` and Tailscale is just another interface. Reachable from anywhere is a different threat model from reachable from the home Wi-Fi: a 6-digit PIN with no lockout is 1,000,000 combinations, guessable by a script in minutes, and that was fine when an attacker first had to be inside the house. `_check_pin` now locks a source out for fifteen minutes after five wrong guesses within a fifteen-minute window, with the PIN not even compared while locked out; this is what makes reaching JAS from anywhere acceptable rather than reckless. The app remembers the Tailscale address (`awayHost`) separately from the one LAN broadcast discovery finds (`host`), and discovery is never allowed to touch it - without that separation, coming home would let LAN discovery silently overwrite the one address that works away from home, so the next trip out the door would find nothing reachable at all. `state()` tries the LAN address first, the Tailscale address second, and only then falls back to asking the network - LAN first because it is faster when both devices happen to be on it. Manual test in `tests/manual/android.md`; no automated test, matching how the rest of the Android app is verified (ADR-077 to ADR-079), since this project has no Android test infrastructure and adding one for a single piece of host-selection logic tied to Android's Context would be disproportionate | Accepted |
| ADR-081 | 2026-09-27 | The phone's discovery beacon was answering with a stale address - `Beacon._host` was captured once at JAS startup and never refreshed, so when the router reassigned this laptop's IP while JAS kept running (which happened four times in a week), the beacon kept confidently telling the phone the *old* address, and the phone dutifully tried to connect to nothing. Found by testing the phone directly: it asked "JAS?" and got back `.111` while the laptop had moved to `.109` hours earlier with no restart in between. `Beacon.answer` now looks the address up fresh on every reply via an injected `host_lookup` callable (defaulting to `local_host`), rather than storing a string at construction. A regression test fakes an IP change mid-run and asserts the second answer reflects it, which the bug it is named for would have failed outright | Accepted |
| ADR-082 | 2026-09-27 | "hey jas" felt completely unresponsive with people nearby - not a logic bug (the addressing from ADR-079 was working correctly on inspection) but a real capacity problem, measured directly: a 1.6 s clip once took 47.7 s to transcribe, a 10.2 s clip took 63.3 s. `Transcriber.transcribe` already serialises every caller behind one lock, correctly - there is one Whisper model, on CPU, shared by the wake-word pipeline, barge-in and every phone - but nothing stopped the queue behind that lock from growing without bound. The phone segments every pause into its own clip and posts it regardless of whether the previous one has been answered, so a real conversation nearby floods the queue faster than one CPU can drain it; each clip is then answered a minute late, to a question nobody is still asking, while also starving the local wake-word pipeline of the same model. Fixed at both ends. `Transcriber.backlog` reports how many callers are queued or running right now (a plain counter under its own uncontended lock); `RemoteControl._listen` refuses a clip outright - `"JAS is catching up"` - rather than joining a queue already two deep, which is more honest than accepting it and answering too late to matter. On the phone, `BubbleService.send` now allows only one clip in flight at a time; further speech detected mid-request is simply not sent, matching the choice the laptop now makes about its own backlog. 8 new tests, including one that drives a stand-in model through a real thread to observe the counter mid-transcription rather than guessing at timing with sleeps | Accepted |
| ADR-083 | 2026-09-28 | Phase 11 (Autonomous Agent), first increment: recovery. `ToolExecutor.run` gave every LOW-risk tool that crashes one automatic retry, per the "retry safely once if idempotent" standard CLAUDE.md §6 had stated but nothing enforced. The trigger is a genuine crash only, never an ordinary `ok=False` - the first design retried both, and would have doubled the cost of every routine "nothing found" vision search (a real, non-trivial call) for an answer that could not have changed an instant later; caught before it shipped, not after. LOW risk is reused as the bar for "safe to repeat automatically", since it is already, by this project's own definition, "safe to run with no confirmation at all" - no new per-tool metadata was added, so there was nothing to mis-mark across the ~40 existing tools. MEDIUM/HIGH are never retried: those already got the user's one-time confirmation, and a tool that half-sent a message must not risk sending it twice on its own initiative. The retry re-checks cancellation, so a pause landing in the gap stops the task rather than forcing one more attempt, and it is invisible to the UI checklist - one ToolStarted, one ToolFinished, never two, so a single command does not appear to run itself twice. "Try an alternative" and "explain and ask" - the rest of §6's standard - are not new code: the existing per-step loop in `gemini.py`/`claude.py` already feeds every final result back to the model, which already reacts to a failure it cannot recover from. **Not yet built:** an explicit upfront plan the user can see before a multi-step task starts, and a higher step budget for genuinely long tasks (still capped at `MAX_TOOL_STEPS = 8`, sized for a conversational turn, not an extended job) - both real, deferred to a later increment rather than built speculatively now. 7 new tests | Accepted |
| ADR-084 | 2026-09-28 | Two real gaps, both making "fully control JAS from the phone" untrue in practice. (1) **The phone had no way to wake a sleeping JAS.** `ask_text` only transitions from STANDBY or RESTING; while paused (SLEEPING) it returned False, and the phone reported "JAS is busy - try again in a moment" - the wrong message, since nothing about being asleep changes by retrying. Worse, the phone's own Pause/Resume chip only ever muted the *phone's own* microphone (`BubbleService.paused`) and never touched the laptop's actual state at all - two unrelated things both called "pause". `RemoteControl._ask_core` now wakes a paused JAS before handing it the request, but only once the request has already passed the addressing check - "hey jas ...", a follow-up, or "stop" - so overheard conversation still can never wake it; only something genuinely said to it can. (2) **The floating bubble showed what was heard and what JAS replied, in text, on screen** - asked to stop, since the whole point of the bubble is voice in, voice out. `BubbleService` no longer sets the transcript or the reply as the label's text; tapping the face still shows the plain state word ("Listening", "Thinking"), which is not conversational content. 3 new tests for the wake path | Accepted |
| ADR-085 | 2026-09-28 | Speech-to-text moved off the CPU, onto this machine's Intel GPU, via OpenVINO. "Milliseconds" had been asked for more than once and was never actually fixed, only patched around (ADR-082's backpressure). Measured honestly before committing to anything: this chip (Core Ultra 5 115U) has a dedicated NPU, so NPU was tried first and it works, is genuinely fast in isolation. Then the CPU (faster-whisper) baseline transcribed the same clips cleanly at ~2 s each - not itself the problem in isolation. The real, provable case came from reproducing the actual failure: the same clip transcribed under real CPU load (`multiprocessing`, all 8 cores saturated, matching the wake-word-pipeline-plus-phone contention that once produced a 75 s backlog) took **41.22 s on CPU** and **3.57 s on GPU via OpenVINO** - the same accurate transcript, because GPU work never competes with the CPU for the same core. `app/voice/stt/openvino_transcriber.py` mirrors `Transcriber`'s exact interface (`transcribe`, `backlog`, `set_vocabulary`, `ensure_loaded`) so nothing that calls it needed to change; `app/voice/stt/make_transcriber` picks CPU or OpenVINO from `STT_BACKEND`, and falls back to CPU automatically if the OpenVINO model has not been exported (`scripts/export_whisper_openvino.py`, a one-time step needing its own heavier packages - optimum-intel, torch, transformers - kept out of `requirements.txt` since they are only needed for that one export, not for running JAS). Now live and confirmed: "Using OpenVINO speech recognition on GPU" at startup. **NPU itself does not work yet** - `RuntimeError: roi_end <= max_dim`, a real, known OpenVINO limitation: the NPU plugin needs fixed input shapes and this export does not provide them. Left as `stt_device = "GPU"` rather than fought further tonight; revisiting NPU is a real, separate piece of work for later, not a silent downgrade - GPU already solves the actual problem. 14 new tests | Accepted |
| ADR-055 | 2026-09-23 | JAS answers in whichever of two voices is closer to the pitch of whoever just spoke (`en_GB-alan-medium` and `en_GB-jenny_dioco-medium`, the second loaded lazily to save RAM). `app/voice/pitch.py` measures the median fundamental by autocorrelation over the voiced frames; above 183 Hz it picks the higher voice, below 147 Hz the lower, and in the 36 Hz band between it keeps whatever is already in use so one ambiguous sentence cannot flip the voice mid-conversation. It needs a quarter-second of voiced speech before deciding. This measures pitch, not identity - voices do not divide neatly and the cost of being wrong is only a wrong voice, so it is a hint and `VOICE_MATCHES_SPEAKER=false` turns it off | Accepted |
| ADR-012 | 2026-09-22 | Voice turn runs in `VoicePipeline` on its own thread; every step uses `transition_from` so pause/cancel mid-turn aborts cleanly. Responder is a pluggable `str -> str` (echo in Phase 3, LLM in Phase 4) | Accepted |
