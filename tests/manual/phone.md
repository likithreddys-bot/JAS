# JAS on your phone (manual test)

JAS can't run *on* a phone — its whole value is driving Excel, your windows and your Chrome profile
through Windows APIs that don't exist on Android or iOS. So your phone is a **remote**: you ask
there, the work happens on the laptop.

---

## Setup (once)

1. Phone and laptop on the **same Wi-Fi**
2. Open **https://192.168.0.131:8770** in your phone's browser — note the **s**
   Your phone will warn that the connection "is not private". Tap **Advanced → Proceed**.
   That is expected: no certificate authority will vouch for a private address like this one.
   You only do it once.
3. Enter the PIN: **173407**  (it's remembered after that)
4. **Make the warning go away and allow installing** — do this once:
   - Open **https://192.168.0.131:8770/JAS.crt** on the phone → it downloads
   - Android: **Settings → Security → More security settings → Encryption & credentials →
     Install a certificate → CA certificate → Install anyway**, pick the downloaded `JAS.crt`
   - iPhone: open the file → **Settings → Profile Downloaded → Install**, then
     **Settings → General → About → Certificate Trust Settings** and switch JAS on
   - Reopen the page: the warning is gone, and Chrome will now offer **Install app**
5. **Install it**: Chrome menu → **Install app**. It then has its own icon and opens with no
   browser around it. (iPhone: Share → Add to Home Screen.)

The address and PIN are printed in `logs/jarvis.log` at every start, and the PIN doesn't change.

## TEST P.1 — It connects
Expect: JAS's face in the state colour, the state under it ("Ready", "Resting"…), and a text box.

## TEST P.1b — Tilt it
Tilt the phone left, right, forward, back. **JAS's eyes follow the tilt**, the way they follow the
mouse on the laptop. Touch the screen and they follow your thumb instead for a couple of seconds.

## TEST P.2 — Ask it something, and hear it
Type **"what's the time"** → the answer appears on the phone **and your phone speaks it**, in JAS's
own voice. The laptop stays quiet, because the answer belongs to whoever asked.

If nothing is heard the first time, tap the screen once — phones block audio until you interact
with the page, and JAS will tell you so.

## TEST P.3 — Just talk to it
There is no button. **Open the app and speak.** The bars under the face move when it hears you,
and your sentence is sent when you stop talking.

The first time, your phone asks permission for the microphone — allow it.

Expect: what you said appears, JAS does the work on the laptop, and **your phone speaks the answer**.

## TEST P.3b — Pause and Hide
**Pause** stops it listening (the button turns solid). **Hide** fades JAS almost away so it is out
of your way without closing it.

## TEST P.4 — Make it do something
Type **"lock my pc"** from the other room. The laptop should lock.

## TEST P.5 — It follows along
Talk to JAS at the laptop normally and watch the phone: what you said and its reply both appear.

## TEST P.6 — The PIN really matters
Open the page in a private tab and enter a wrong PIN → it refuses (403) and offers to re-enter.

---

### What's verified
- HTTPS serves, plain http no longer answers, a wrong PIN is rejected with 403 — checked live
- asked from the phone, answered "It's 12:59 PM", 90 KB of valid WAV returned — checked live
- a real recording sent to /listen was transcribed in 6.1 s, acted on (Chrome opened, music
  started) and 212 KB of reply audio came back — checked live
- a typed request goes through the same pipeline as the dashboard — 21 automated tests

### Known limits
- **Same Wi-Fi only.** Outside the house needs something like Tailscale — ask and I'll set it up.
- **The laptop must be awake.** A remote can't wake a sleeping machine.
- **Your voice is transcribed on the laptop**, never in a cloud — same Whisper, same accuracy.
- Transcribing takes a few seconds (6 s for a 5 s clip), the same as talking to the laptop.
