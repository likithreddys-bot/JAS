"""JAS from your phone: a small page served on your home network.

Porting JAS to a phone would mean losing the only reason it is useful — it drives Excel, your
windows and your Chrome profile through Windows APIs that do not exist on Android or iOS. So the
phone is a remote instead: you type (or later speak) there, and the work happens on this laptop.

Requests go through `core.ask_text`, the same path the dashboard uses, so the phone gets the whole
assistant — tools, memory, confirmations and all — rather than a cut-down copy.

Security: this listens on the local network, so every request must carry the PIN. It is never
opened to the internet.

It is served over HTTPS because browsers only allow microphone access on a secure origin — over
plain HTTP the phone simply refuses to record. The certificate is generated here and signed by
nobody, so the phone will warn once that it is not trusted; that is expected for a device on your
own network with no public name.
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import socket
import threading
import time
from pathlib import Path

from aiohttp import web

from app.core.events.events import AssistantReply, StateChanged, TranscriptReady
from app.core.jarvis import Jarvis
from app.voice.bargein import is_stop
from ui.theme import STATE_BODY, STATE_COLORS, STATE_LABELS

log = logging.getLogger("jarvis.remote")

DEFAULT_PORT = 8770

# What Whisper says when it is given near-silence. It is a generative model, so handed a second of
# room tone it does not return nothing - it returns the most likely thing a clip of that length
# contains, learned from captioned video: a sign-off or a filler. These arrived from an empty room.
# Only ever matched against a WHOLE utterance, so "thank you for opening Chrome" is untouched.
# Deliberately does NOT include "yes", "yeah", "ok", "okay", "no", "sure" or "stop". Those are how
# a confirmation gets answered and how JAS gets interrupted, so dropping them would break the two
# things that most need to work on one word.
HALLUCINATIONS = frozenset({
    "thank you", "thanks", "thank you very much", "thanks for watching",
    "thank you for watching", "thank you so much", "thanks a lot",
    "please subscribe", "subscribe to my channel", "like and subscribe",
    "bye", "bye bye", "goodbye", "see you", "see you next time",
    "you", "so", "oh", "hmm", "mm", "mhm", "uh", "um", "ah", "eh",
    "the", "a", "an", "and", "i", "it", "is",
    "blank_audio", "silence", "music", "applause", "inaudible", "noise", "beep",
})


def is_hallucination(text: str) -> bool:
    """True when the whole utterance is Whisper filling in silence rather than something said."""
    # Whisper repeats itself on silence - "Thank you. Thank you." - so judge the sentence it repeated.
    sentences = [part.strip() for part in re.split(r"[.!?]+", text.lower()) if part.strip()]
    if len(sentences) > 1 and len(set(sentences)) == 1:
        text = sentences[0]
    stripped = "".join(c for c in text.lower() if c.isalnum() or c.isspace() or c == "_")
    words = stripped.split()
    if not words:
        return True  # punctuation, music notes or brackets only
    return " ".join(words) in HALLUCINATIONS
PIN_NOTE = "remote_pin"


def _matches(cert_file: Path, key_file: Path) -> bool:
    """Whether a kept certificate belongs to the kept key.

    Certificates written before the key was shared across addresses were signed with a key of their
    own, so reusing one with this key would hand the phone a certificate the server cannot prove it
    owns and the handshake would simply fail.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    try:
        cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
        key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
        return cert.public_key().public_numbers() == key.public_key().public_numbers()
    except Exception:
        log.warning("Could not read %s, so making a fresh certificate", cert_file.name)
        return False


def certificate(folder: Path, host: str) -> tuple[Path, Path]:
    """A self-signed certificate for this laptop's address, made once and kept.

    Browsers refuse `getUserMedia` on an insecure origin, so the phone cannot use its microphone
    over http. Nobody can sign a certificate for a private address like 192.168.x.x, so this signs
    its own; the phone shows one warning and remembers the choice.
    """
    import datetime
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    folder.mkdir(parents=True, exist_ok=True)
    # One key for this laptop, kept forever; a certificate per address it has had. The router hands
    # out a new IP every so often, and a new key each time would change JAS's identity — the phone
    # app pins the key, so it would refuse to connect and have to be re-paired. Same key, new
    # certificate: the address on it changes, who it is does not.
    cert_file, key_file = folder / f"{host}.pem", folder / "jas.key"
    if cert_file.exists() and key_file.exists() and _matches(cert_file, key_file):
        return cert_file, key_file

    if key_file.exists():
        key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.datetime.now(datetime.timezone.utc)
    alternatives = [x509.DNSName("localhost")]
    try:
        alternatives.append(x509.IPAddress(ipaddress.ip_address(host)))
    except ValueError:
        alternatives.append(x509.DNSName(host))
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(alternatives), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))

    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    if not key_file.exists():
        key_file.write_bytes(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
    log.info("Made a certificate for %s (valid 10 years)", host)
    return cert_file, key_file


def local_host() -> str:
    """This laptop's address on the home network: whoever we would reach the router as."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))  # never sent; just picks the outgoing interface
        host = probe.getsockname()[0]
    except Exception:
        host = "127.0.0.1"
    finally:
        probe.close()
    return host


# --- who was being spoken to ------------------------------------------------------------------
#
# The phone's microphone is open the whole time the face is showing, so it hears the room, not just
# you. Left unchecked that is not a small annoyance: in four minutes of somebody else's conversation
# it sent 72 clips, and JAS tried to act on "Namkotas too" and "Amazon is an external API power".
# No loudness threshold can help - that audio IS speech, it is simply not addressed to JAS.
#
# So a clip from the phone is acted on only when JAS was called by name. Whisper spells it several
# ways and "jazz" is the commonest, which is why the barge-in phrases already allow for it.
CALLED = re.compile(
    r"^\s*(?:hey|hi|hello|ok|okay|yo)?[\s,.]*"
    r"(?:jas|jass|jaz|jazz|jarvis|jervis)\b[\s,.!?:-]*",
    re.I)

# After JAS answers, the next thing said needs no name, so a conversation is not "jas" every line.
FOLLOW_UP_SECONDS = 25.0


def addressed_to_jas(text: str) -> str | None:
    """The command with the name stripped off, or None when JAS was not the one being spoken to.

    An empty string means it was called with nothing after it - "hey jas" on its own.
    """
    called = CALLED.match(text)
    if not called:
        return None
    return text[called.end():].strip()


def local_address(port: int) -> str:
    return f"https://{local_host()}:{port}"


class RemoteControl:
    """Serves the phone page and feeds what you type into the ordinary voice pipeline."""

    def __init__(self, core: Jarvis, pin: str, port: int = DEFAULT_PORT,
                 assistant_name: str = "JAS", render=None, transcribe=None,
                 certificates: Path | None = None) -> None:
        self._core = core
        self._pin = pin
        self._port = port
        self._name = assistant_name
        self._render = render  # text -> WAV bytes, so the phone speaks in JAS's own voice
        self._transcribe = transcribe  # WAV audio -> text, done here so any phone can be talked to
        self._certificates = certificates
        self._said = ""
        self._heard = ""
        self._reply_id = 0
        self._icons: dict[int, bytes] = {}
        self._audio: tuple[int, bytes] | None = None
        self._spoke_at = 0.0  # when JAS last answered, so a follow-up needs no name
        core.bus.subscribe(AssistantReply, self._on_reply)
        core.bus.subscribe(TranscriptReady, self._on_heard)
        core.bus.subscribe(StateChanged, lambda e: None)
        self._thread = threading.Thread(target=self._serve, name="remote", daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def address(self) -> str:
        return local_address(self._port)

    def _on_reply(self, event: AssistantReply) -> None:
        if event.text and event.text != self._said:
            self._said = event.text
            self._reply_id += 1
            self._spoke_at = time.monotonic()

    def _on_heard(self, event: TranscriptReady) -> None:
        self._heard = event.text
        self._said = ""

    # --- the three things the phone asks for ---------------------------------

    def _authorised(self, request) -> bool:
        return secrets.compare_digest(str(request.query.get("pin", "")), self._pin)

    async def _page(self, request):
        return web.Response(text=phone_page(self._name), content_type="text/html")

    async def _manifest(self, request):
        """What turns the page into an installed app: own icon, own window, no browser."""
        return web.json_response({
            "name": self._name, "short_name": self._name,
            "start_url": "/", "scope": "/",
            "display": "standalone", "orientation": "portrait",
            "background_color": "#0B0E14", "theme_color": "#0B0E14",
            "icons": [{"src": f"/icon-{size}.png", "sizes": f"{size}x{size}",
                       "type": "image/png", "purpose": "any maskable"}
                      for size in (192, 512)],
        }, content_type="application/manifest+json")

    async def _ca(self, request):
        """The certificate, to install on the phone.

        Chrome refuses to install a web app from a site it does not trust, and nobody will sign a
        certificate for a private address. Installing this one on the phone makes the warning and
        the refusal go away, because the phone then knows who signed it: this laptop.
        """
        if self._certificates is None:
            return web.Response(status=404)
        cert_file, _ = certificate(self._certificates, local_host())
        return web.Response(body=cert_file.read_bytes(),
                            content_type="application/x-x509-ca-cert",
                            headers={"Content-Disposition": 'attachment; filename="JAS.crt"'})

    async def _worker(self, request):
        """A service worker is required before a browser will offer to install the app."""
        return web.Response(text=SERVICE_WORKER, content_type="application/javascript")

    async def _icon(self, request):
        size = int(request.match_info.get("size", 192))
        if size not in self._icons:
            self._icons[size] = _icon_bytes(size)
        return web.Response(body=self._icons[size], content_type="image/png",
                            headers={"Cache-Control": "max-age=86400"})

    async def _state(self, request):
        if not self._authorised(request):
            return web.json_response({"error": "wrong pin"}, status=403)
        state = self._core.state.current
        return web.json_response({
            "state": state.value,
            "label": STATE_LABELS[state],
            "colour": STATE_COLORS[state],
            "body": STATE_BODY.get(state, ""),
            "heard": self._heard,
            "said": self._said,
            "reply_id": self._reply_id,
            "can_speak": self._render is not None,
            "busy": state.value not in ("standby", "resting", "sleeping"),
        })

    async def _voice(self, request):
        """The latest reply as a WAV, so the phone speaks it rather than the laptop."""
        if not self._authorised(request):
            return web.Response(status=403)
        if self._render is None or not self._said:
            return web.Response(status=404)
        wanted = self._reply_id
        if self._audio is None or self._audio[0] != wanted:
            try:
                self._audio = (wanted, self._render(self._said))
            except Exception:
                log.exception("Could not render the reply for the phone")
                return web.Response(status=500)
        return web.Response(body=self._audio[1], content_type="audio/wav",
                            headers={"Cache-Control": "no-store"})

    async def _listen(self, request):
        """Speech recorded on the phone, transcribed here. The audio never leaves this laptop."""
        if not self._authorised(request):
            return web.json_response({"error": "wrong pin"}, status=403)
        if self._transcribe is None:
            return web.json_response({"error": "speech recognition isn't ready yet"}, status=503)
        wav = await request.read()
        if len(wav) < 2000:
            return web.json_response({"heard": "", "error": "I didn't catch that"})
        try:
            heard = await asyncio.get_running_loop().run_in_executor(None, self._transcribe, wav)
        except Exception:
            log.exception("Could not transcribe what the phone sent")
            return web.json_response({"error": "I couldn't make that out"}, status=500)
        heard = (heard or "").strip()
        if not heard:
            return web.json_response({"heard": "", "error": "I didn't catch that"})
        if is_hallucination(heard):
            # The phone's microphone is always open, so it will send the odd clip of room tone.
            # Acting on Whisper's guess at what that contained would mean answering nobody.
            log.info("Ignoring %r from the phone: that is silence, not speech", heard[:40])
            return web.json_response({"heard": "", "error": ""})

        command = addressed_to_jas(heard)
        answering = (time.monotonic() - self._spoke_at) < FOLLOW_UP_SECONDS
        if command is None and not answering and not is_stop(heard):
            # Somebody was talking, but not to JAS. Overhearing the room is not a reason to act.
            log.info("Not for me: %r", heard[:60])
            return web.json_response({"heard": "", "error": ""})
        heard = command or heard
        log.info("Remote voice: %r", heard[:80])
        self._heard, self._said = heard, ""
        accepted = self._core.ask_text(heard, answer_here=False)
        return web.json_response({"heard": heard, "accepted": accepted,
                                  "error": "" if accepted else "JAS is busy — try again in a moment"})

    async def _ask(self, request):
        if not self._authorised(request):
            return web.json_response({"error": "wrong pin"}, status=403)
        body = await request.json()
        text = str(body.get("text", "")).strip()
        if not text:
            return web.json_response({"error": "say something"}, status=400)
        log.info("Remote request: %r", text[:80])
        self._heard, self._said = text, ""
        # The answer belongs on the phone that asked, not out loud in an empty room.
        accepted = self._core.ask_text(text, answer_here=False)
        return web.json_response({"accepted": accepted,
                                  "error": "" if accepted else "JAS is busy — try again in a moment"})

    def _ssl(self):
        """HTTPS, because a phone will not open its microphone on an insecure page."""
        if self._certificates is None:
            return None
        import ssl

        cert_file, key_file = certificate(self._certificates, local_host())
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        return context

    def _serve(self) -> None:
        async def run() -> None:
            app = web.Application()
            app.add_routes([web.get("/", self._page),
                            web.get("/state", self._state),
                            web.get("/voice", self._voice),
                            web.post("/ask", self._ask),
                            web.post("/listen", self._listen),
                            web.get("/manifest.webmanifest", self._manifest),
                            web.get("/sw.js", self._worker),
                            web.get("/JAS.crt", self._ca),
                            web.get("/icon-{size}.png", self._icon)])
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", self._port, ssl_context=self._ssl()).start()
            log.info("Phone remote on %s (pin %s)", self.address, self._pin)
            while True:
                await asyncio.sleep(3600)

        try:
            asyncio.new_event_loop().run_until_complete(run())
        except Exception:
            log.exception("Phone remote could not start")


def _icon_bytes(size: int) -> bytes:
    """JAS's face as a square app icon, drawn from the same picture as the lock screen."""
    import io

    from app.lockart import draw_face

    picture = draw_face("watchful", with_text=False)
    side = min(picture.size)
    left = (picture.width - side) // 2
    square = picture.crop((left, 0, left + side, side)).resize((size, size))
    out = io.BytesIO()
    square.save(out, "PNG")
    return out.getvalue()


SERVICE_WORKER = """
// Just enough to make the browser offer to install JAS as an app. Nothing is cached: every
// answer must be live, and a stale reply would be worse than no reply.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
"""


def pin_for(memory) -> str:
    """A stable PIN, kept with JAS's other notes so it survives a restart."""
    existing = memory.note(PIN_NOTE)
    if existing:
        return existing
    pin = f"{secrets.randbelow(900000) + 100000}"
    memory.set_note(PIN_NOTE, pin)
    return pin


PHONE_DIR = Path(__file__).resolve().parents[1] / "ui"


def phone_page(name: str) -> str:
    """The page and its script, with the assistant's name filled in."""
    html = (PHONE_DIR / "phone.html").read_text(encoding="utf-8")
    script = (PHONE_DIR / "phone.js").read_text(encoding="utf-8")
    page = html.replace("{{NAME}}", name)
    bundle = f"<script>const NAME = {name!r};\n{script}\n</script>\n</body></html>"
    return page.replace("</body></html>", bundle)
