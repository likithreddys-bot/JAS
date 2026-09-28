# Manual test — the JAS Android app

The app is a **client**. All the thinking, Excel, Chrome and Windows control still happens on the
laptop; the phone contributes a microphone, a speaker, a screen and a face that floats over other
apps. So the laptop must be running JAS and on the same Wi-Fi throughout.

## What to install

The build produces `android/app/build/outputs/apk/debug/app-debug.apk`.

1. Copy that file to the phone (USB, or with the phone plugged in run
   `adb install -r android/app/build/outputs/apk/debug/app-debug.apk`).
2. Open it on the phone and allow "install from unknown source" when Android asks. This is a debug
   build signed with the standard debug key — it is not from the Play Store and Android will say so.
3. **You do not need to install `JAS.crt` for the app.** The app pins the laptop's certificate the
   first time it connects. The certificate download is still there for the browser version.

## Setting it up (once)

1. On the laptop, find the line JAS logs at startup:
   `Phone remote: open https://192.168.x.x:8765 and enter PIN 123456`
2. In the app, type the address **without** `https://` — just `192.168.x.x:8765` — and the PIN.
3. Press **Show JAS on screen**. Android will ask for two things:
   - the **microphone** — JAS cannot hear you without it;
   - **Display over other apps** — this is the one a web page can never have, and it is what makes
     the floating face possible. Turn it on and press Show again.
4. The app should drop to the background and a small JAS face should appear on top of whatever you
   were doing.

Expected: the small grey line at the bottom of the setup screen changes from `not paired yet` to
`paired certificate 4A:2B:…`.

## The checks

| # | Do this | Expect |
|---|---|---|
| 1 | Look at the floating face | The sphere breathes, blinks on an irregular rhythm, and is the Sun's warm orange while the laptop is idle |
| 2 | Tilt the phone left and right | The pupils move the way you tilt, the same way they follow the mouse on the laptop |
| 3 | Say "what time is it" out loud, without touching anything | The screen edges glow, the face turns through Earth → Jupiter → Saturn, and the phone's own speaker answers in JAS's voice |
| 4 | Say "open Chrome" | Chrome opens **on the laptop**; the phone says it did |
| 5 | While it is answering a long question, say "stop" | It stops mid-sentence |
| 6 | Drag the face to another corner | It follows your finger and stays where you drop it |
| 7 | Tap the face once | Two chips appear beside it: Pause and Hide, with the current state above them |
| 8 | Tap Pause, then talk | Nothing is sent. The chip now says Resume |
| 9 | Tap Resume, then talk | It hears you again |
| 10 | Tap Hide | The face disappears and the notification goes away. The laptop is unaffected |
| 11 | Open a game or video and talk | The face stays on top and still hears you — this is the whole point of the native app |
| 12 | Turn the laptop's Wi-Fi off | The face goes grey with a concerned brow and the setup screen explains why |
| 13 | Turn it back on | It recovers on its own within a second |

## Reading the listening log

Every clip the phone decides about is logged, so tuning uses real numbers rather than guesses.
With the phone plugged in:

```
adb logcat -s JasEars:V
```

```
1400ms of speech, peak 0.0312, needed 0.0180, room 0.0045 -> sent
200ms of speech,  peak 0.0090, needed 0.0096, room 0.0024 -> dropped
```

- **room** — what the microphone hears with nobody talking. Learned continuously.
- **needed** — the peak a clip must reach to count as a voice: four times the room, floored at 0.0096.
- `dropped` on things you actually said → the thresholds are too strict; send me these lines.
- `sent` on coughs, doors and traffic → too loose; same, send me the lines.

## If replies are cut off mid-word

That was a real bug (every reply was clipped to 0.4 s) and is fixed. If it returns, it is the
playback drain in `Mouth.kt`: `write` only fills the buffer, so playback must be followed with
`playbackHeadPosition`, never a fixed sleep.

## Things that are still not possible, and why

- **Long-pressing the power button** to wake JAS. Android does not let any app take the power
  button; the system owns it. Assistant apps get the long-press *gesture* only by being registered
  as **the** device assistant, which replaces Google Assistant system-wide.
- **A wake word on the phone.** The app would have to run the wake-word model on the phone
  continuously. That is possible but it costs battery all day, and the face being on screen already
  means JAS is listening — there is nothing to wake.
## Working away from home (Tailscale)

The app reaches the laptop directly over the internet only through Tailscale, a private VPN mesh —
never through a forwarded router port. Setup, once:

1. On the laptop, Tailscale is already installed and signed in. Confirm the address it's using:
   `& "C:\Program Files\Tailscale\tailscale.exe" ip -4` — it looks like `100.x.y.z`.
2. On the phone, install **Tailscale** from the Play Store and sign in with the **same account**.
3. In the JAS app, scroll to **"Laptop's Tailscale address (only needed away from home)"** and enter
   `100.x.y.z:8770` (the address from step 1, with the JAS port).
4. Turn off Wi-Fi on the phone (or use mobile data) and confirm JAS still answers.

This is why the PIN now locks a source out after five wrong guesses (`app/remote.py`) — a 6-digit
PIN alone is fine on the home Wi-Fi, where an attacker already has to be inside the house, but not
once this is reachable from anywhere.

The Tailscale address is remembered separately from the one LAN discovery finds, and is only ever
set by hand — so coming home and leaving again does not lose it. See ADR-080 in `JARVIS.md`.

## If it will not connect

- `This is not the laptop JAS was paired with` — the laptop's IP changed, so it made a new
  certificate for the new address. Press **Pair again** and reconnect.
- Nothing at all — check the phone is on the same Wi-Fi, and that the laptop is awake. A sleeping
  laptop cannot answer.

## "JAS is catching up"

There is one Whisper model, on CPU, shared by the wake-word pipeline, barge-in and every phone. If
people are talking nearby, the phone segments every pause into its own clip and can queue up faster
than one CPU can transcribe — this message means a clip was refused outright rather than added to
that queue, because answering it a minute late would be worse than not answering it at all. It is
expected occasionally with people around; if it shows up standing alone in a quiet room, something
else is wrong — check Task Manager for a second JAS process, or another program pinning the CPU.
See ADR-082 in `JARVIS.md`.
