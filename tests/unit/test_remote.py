"""The phone remote: it reaches the whole assistant, and refuses anyone without the PIN.

The handlers are called directly with a small stub request, so this needs no async pytest plugin
and no real socket.
"""
import asyncio
import json

import pytest

from app.core.events.events import AssistantReply, TranscriptReady
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.memory.store import MemoryStore
from app.remote import PIN_NOTE, RemoteControl, local_address, pin_for


class Request:
    """Just the things the handlers touch: the query string, the JSON body and the source."""

    def __init__(self, pin="123456", body=None, remote="203.0.113.5"):
        self.query = {"pin": pin}
        self._body = body or {}
        self.remote = remote  # the source address, so lockout can be tested per-source

    async def json(self):
        return self._body


def call(handler, request):
    response = asyncio.run(handler(request))
    is_json = response.content_type in ("application/json", "application/manifest+json")
    payload = json.loads(response.text) if is_json else response.text
    return response.status, payload


@pytest.fixture
def remote():
    core = Jarvis()
    core.start()
    return core, RemoteControl(core, "123456", port=0, assistant_name="JAS")


def test_five_wrong_pins_lock_out_that_source(remote):
    """A 6-digit PIN alone is 1,000,000 combinations - guessable by a script in minutes once this
    is reachable from anywhere. The lockout is what makes that acceptable."""
    _, control = remote
    for _ in range(4):
        status, out = call(control._state, Request(pin="000000"))
        assert status == 403 and out["error"] == "wrong pin"

    # The fifth wrong guess is the one that trips the lockout, and is itself refused by it.
    status, out = call(control._state, Request(pin="000000"))
    assert status == 429
    assert "Too many wrong PINs" in out["error"]


def test_a_locked_out_source_is_refused_even_with_the_right_pin(remote):
    """Once locked out, the PIN is not even compared - the lockout is the whole answer."""
    _, control = remote
    for _ in range(5):
        call(control._state, Request(pin="000000"))

    status, out = call(control._state, Request(pin="123456"))
    assert status == 429 and "Too many wrong PINs" in out["error"]


def test_lockout_is_per_source_not_global(remote):
    """One attacker locking themselves out must not lock out the phone's own PIN."""
    _, control = remote
    for _ in range(5):
        call(control._state, Request(pin="000000", remote="198.51.100.9"))

    status, out = call(control._state, Request(pin="123456", remote="192.168.0.117"))
    assert status == 200, "a different source, and the right PIN, must still work"


def test_a_correct_pin_clears_previous_failures(remote):
    """Four wrong guesses followed by the right one must not carry a grudge into the next mistake."""
    _, control = remote
    for _ in range(4):
        call(control._state, Request(pin="000000"))
    assert call(control._state, Request(pin="123456"))[0] == 200

    # Four more wrong guesses now must not trip the five-attempt lockout the first four almost did.
    for _ in range(4):
        status, _ = call(control._state, Request(pin="000000"))
        assert status == 403, "the slate was wiped by the successful attempt above"


def test_the_lockout_expires(remote, monkeypatch):
    """Fifteen minutes is a deterrent, not a life sentence for a mistyped PIN."""
    import app.remote as remote_module

    clock = [1000.0]
    monkeypatch.setattr(remote_module.time, "monotonic", lambda: clock[0])

    _, control = remote
    for _ in range(5):
        call(control._state, Request(pin="000000"))
    assert call(control._state, Request(pin="123456"))[0] == 429, "still within the lockout"

    clock[0] += remote_module.LOCKOUT_SECONDS + 1
    status, _ = call(control._state, Request(pin="123456"))
    assert status == 200, "the lockout has served its time"


def test_old_failures_do_not_accumulate_towards_a_lockout(remote, monkeypatch):
    """Two wrong guesses today and two next week are not four - the window resets what it counts."""
    import app.remote as remote_module

    clock = [1000.0]
    monkeypatch.setattr(remote_module.time, "monotonic", lambda: clock[0])

    _, control = remote
    for _ in range(4):
        call(control._state, Request(pin="000000"))

    clock[0] += remote_module.ATTEMPT_WINDOW_SECONDS + 1
    status, out = call(control._state, Request(pin="000000"))
    assert status == 403 and out["error"] == "wrong pin", "the old attempts had already expired"


def test_the_page_loads_without_a_pin(remote):
    """The page is harmless; everything it asks for afterwards needs the PIN."""
    _, control = remote
    status, body = call(control._page, Request(pin=""))
    assert status == 200
    assert "JAS" in body and "listening" in body
    assert "<svg" in body, "the face is drawn, not just a coloured circle"


def test_state_and_ask_refuse_a_wrong_pin(remote):
    _, control = remote
    assert call(control._state, Request(pin="000000"))[0] == 403
    assert call(control._ask, Request(pin="000000", body={"text": "lock my pc"}))[0] == 403


def test_state_reports_what_jas_is_doing(remote):
    _, control = remote
    status, state = call(control._state, Request())
    assert status == 200
    assert state["state"] == "standby" and state["label"] == "Ready"
    assert state["colour"].startswith("#") and state["busy"] is False


def test_a_typed_request_goes_through_the_real_pipeline(remote):
    core, control = remote
    status, out = call(control._ask, Request(body={"text": "lock my pc"}))
    assert status == 200 and out["accepted"] is True
    assert core.typed_request == "lock my pc"
    assert core.state.current is S.WAKE_DETECTED, "the phone uses the same path as the dashboard"


def test_an_empty_request_is_refused(remote):
    _, control = remote
    assert call(control._ask, Request(body={"text": "   "}))[0] == 400


def test_the_phone_sees_what_was_heard_and_said(remote):
    core, control = remote
    core.bus.publish(TranscriptReady("what's the total"))
    core.bus.publish(AssistantReply("Five thousand four hundred and fifty."))
    _, state = call(control._state, Request())
    assert state["heard"] == "what's the total"
    assert "Five thousand" in state["said"]


def test_a_busy_jas_says_so_rather_than_queueing(remote):
    core, control = remote
    core.state.transition(S.WAKE_DETECTED)
    core.state.transition(S.LISTENING)
    _, out = call(control._ask, Request(body={"text": "open notepad"}))
    assert out["accepted"] is False and "busy" in out["error"]


def test_a_sleeping_jas_wakes_up_for_a_typed_request(remote):
    """Asleep is not the same as busy - without this, the phone got "try again in a moment" and
    would go on getting that forever, since nothing about "asleep" changes by retrying."""
    core, control = remote
    core.pause()
    assert core.paused

    _, out = call(control._ask, Request(body={"text": "open notepad"}))
    assert out["accepted"] is True
    assert core.paused is False, "must actually wake up, not just pretend to accept the request"
    assert core.typed_request == "open notepad"


def test_a_sleeping_jas_wakes_up_when_called_by_name_from_the_phones_voice(remote):
    core, control = remote
    core.pause()
    control._transcribe = lambda wav: "Hey Jas, lock my pc"

    _, out = call(control._listen, VoiceRequest())
    assert out["accepted"] is True and out["heard"] == "lock my pc"
    assert core.paused is False


def test_a_sleeping_jas_is_not_woken_by_a_conversation_it_only_overheard(remote):
    """Waking on any old noise nearby would make "pause" meaningless the moment a phone is in the
    room - it must only wake for something actually addressed to it."""
    core, control = remote
    core.pause()
    control._transcribe = lambda wav: "so anyway I told him the meeting is at five"

    call(control._listen, VoiceRequest())
    assert core.paused is True, "overheard conversation must never wake a paused JAS"


def test_the_pin_is_six_digits_and_survives_a_restart(tmp_path):
    memory = MemoryStore(tmp_path / "memory.db")
    first = pin_for(memory)
    assert first.isdigit() and len(first) == 6
    assert pin_for(memory) == first, "a new PIN every restart would be useless"
    assert memory.note(PIN_NOTE) == first


def test_the_address_is_a_real_local_one():
    address = local_address(8770)
    assert address.startswith("https://") and address.endswith(":8770")
    assert not address.startswith("https://0.0.0.0")


def test_a_phone_request_is_answered_on_the_phone_not_the_laptop(remote):
    """Speaking a reply out loud in an empty room is the wrong place for it."""
    core, control = remote
    call(control._ask, Request(body={"text": "what's the time"}))
    assert core.quiet is True, "the laptop stays silent for a request that came from the phone"


def test_asking_at_the_laptop_still_speaks_there():
    core = Jarvis()
    core.start()
    core.ask_text("what's the time")          # the dashboard, not the phone
    assert core.quiet is False


def test_the_phone_gets_the_reply_as_audio(remote):
    core, control = remote
    control._render = lambda text: b"RIFF....WAVEfmt " + text.encode()
    core.bus.publish(AssistantReply("Half past four."))

    response = asyncio.run(control._voice(Request()))
    assert response.status == 200
    assert response.content_type == "audio/wav"
    assert b"Half past four." in response.body


def test_the_audio_is_rendered_once_per_reply(remote):
    """Rendering speech is not free; the phone polls, so it must not re-render on every poll."""
    core, control = remote
    renders = []
    control._render = lambda text: renders.append(text) or b"WAV"
    core.bus.publish(AssistantReply("First answer."))

    asyncio.run(control._voice(Request()))
    asyncio.run(control._voice(Request()))
    assert renders == ["First answer."], "polling twice must not synthesise twice"

    core.bus.publish(AssistantReply("Second answer."))
    asyncio.run(control._voice(Request()))
    assert renders == ["First answer.", "Second answer."]


def test_voice_needs_the_pin_too(remote):
    core, control = remote
    control._render = lambda text: b"WAV"
    core.bus.publish(AssistantReply("Something private."))
    assert asyncio.run(control._voice(Request(pin="000000"))).status == 403


def test_no_audio_before_there_is_anything_to_say(remote):
    _, control = remote
    control._render = lambda text: b"WAV"
    assert asyncio.run(control._voice(Request())).status == 404


def wav_bytes(seconds=1.0, rate=16000):
    """A 16 kHz mono WAV, the shape the phone page produces."""
    import io
    import math
    import struct
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 12)))
                                 for i in range(int(rate * seconds))))
    return buffer.getvalue()


class IconRequest(Request):
    def __init__(self, size: int):
        super().__init__(pin="")
        self.match_info = {"size": str(size)}


class AudioRequest(Request):
    def __init__(self, body: bytes, pin="123456"):
        super().__init__(pin=pin)
        self._audio = body

    async def read(self):
        return self._audio


def test_speech_from_the_phone_is_transcribed_here_and_acted_on(remote):
    """The recording is transcribed on this laptop; the audio never goes to a cloud.

    Spoken to, JAS must be called by name - the microphone is open the whole time, so an unnamed
    sentence may well be a conversation it merely overheard. See the addressing tests below.
    """
    core, control = remote
    seen = []
    control._transcribe = lambda wav: seen.append(len(wav)) or "Hey Jas, lock my pc"

    status, out = call(control._listen, AudioRequest(wav_bytes()))
    assert status == 200
    assert out["heard"] == "lock my pc" and out["accepted"] is True
    assert seen and seen[0] > 2000, "the real audio was handed to the transcriber"
    assert core.typed_request == "lock my pc", "the name is stripped before the command is run"
    assert core.quiet is True, "a spoken phone request is answered on the phone"


def test_a_tap_with_no_speech_says_so_rather_than_guessing(remote):
    _, control = remote
    control._transcribe = lambda wav: "   "
    status, out = call(control._listen, AudioRequest(wav_bytes()))
    assert status == 200 and out["heard"] == "" and "didn't catch" in out["error"]


def test_a_clip_too_short_to_be_speech_is_rejected_without_transcribing(remote):
    _, control = remote
    calls = []
    control._transcribe = lambda wav: calls.append(wav) or "something"
    status, out = call(control._listen, AudioRequest(b"RIFF" + b"\x00" * 100))
    assert status == 200 and out["heard"] == "" and calls == [], "no point waking Whisper for a blip"


def test_speech_needs_the_pin(remote):
    _, control = remote
    control._transcribe = lambda wav: "open notepad"
    assert call(control._listen, AudioRequest(wav_bytes(), pin="000000"))[0] == 403


def test_speech_says_so_when_whisper_is_not_loaded_yet(remote):
    _, control = remote
    control._transcribe = None
    status, out = call(control._listen, AudioRequest(wav_bytes()))
    assert status == 503 and "isn't ready" in out["error"]


def test_the_phone_listens_by_itself_with_no_button_to_hold():
    """Holding a button is not how you talk to an assistant; it listens from the moment it opens."""
    from app.remote import phone_page

    page = phone_page("JAS")
    assert "/listen?pin=" in page
    assert "getUserMedia" in page and "16000" in page, "audio is captured and resampled on the phone"
    assert "QUIET_MS" in page and "SPEAKING" in page, "it decides when a sentence has ended"
    assert 'id="mic"' not in page and "hold to talk" not in page, "the hold button is gone"


def test_the_phone_can_be_paused_and_hidden():
    from app.remote import phone_page

    page = phone_page("JAS")
    assert 'id="pause"' in page and 'id="hide"' in page


def test_the_phone_stops_listening_in_the_background():
    """Holding the microphone open behind other apps would drain the battery for nothing."""
    from app.remote import phone_page

    assert "visibilitychange" in phone_page("JAS")


def test_the_phone_ignores_jas_own_voice():
    """The microphone is always open, so hearing its own reply would start a loop."""
    from app.remote import phone_page

    assert "player.paused" in phone_page("JAS")


class VoiceRequest(Request):
    """A request carrying recorded audio, which is what /listen reads."""

    def __init__(self, pin="123456"):
        super().__init__(pin=pin)

    async def read(self):
        return bytes(4000)  # long enough to be taken seriously; the transcriber is stubbed


def _hearing(words):
    """A remote whose speech recognition always returns `words`."""
    core = Jarvis()
    core.start()
    return core, RemoteControl(core, "123456", port=0, assistant_name="JAS",
                               transcribe=lambda wav: words)


def test_a_deep_queue_is_refused_rather_than_joined(remote):
    """One Whisper model, on CPU, shared by everything that can hear.

    A real conversation nearby once queued this laptop 75 seconds deep - each clip answered a
    minute late, to a question nobody was still asking. Refusing a clip outright, immediately, is
    more honest than accepting it and making the user wait for an answer that arrives too late to
    matter, and it stops the queue from growing without bound in the first place.
    """
    core = Jarvis()
    core.start()
    control = RemoteControl(core, "123456", port=0, assistant_name="JAS",
                            transcribe=lambda wav: "hey jas, lock my pc",
                            backlog=lambda: 2)
    status, out = call(control._listen, VoiceRequest())
    assert status == 200
    assert out["heard"] == "" and "catching up" in out["error"]


def test_a_shallow_queue_is_still_served(remote):
    """One already running and one waiting is normal, not a reason to refuse."""
    core = Jarvis()
    core.start()
    control = RemoteControl(core, "123456", port=0, assistant_name="JAS",
                            transcribe=lambda wav: "hey jas, lock my pc",
                            backlog=lambda: 1)
    status, out = call(control._listen, VoiceRequest())
    assert status == 200 and out["heard"] == "lock my pc"


def test_no_backlog_given_defaults_to_never_refusing(remote):
    """The `remote` fixture builds RemoteControl with no backlog= at all, like every caller before
    this existed - it must default to "nothing queued", not to refusing every request."""
    _, control = remote
    control._transcribe = lambda wav: "hey jas, lock my pc"
    status, out = call(control._listen, VoiceRequest())
    assert status == 200 and out["heard"] == "lock my pc"


def test_a_new_ip_does_not_change_who_the_laptop_is(tmp_path):
    """The router reassigns the laptop's address, and the certificate names the address.

    The phone pins the laptop's public key, so one key shared by every address means a move needs
    no re-pairing. It caught us for real: 192.168.0.131 became 192.168.0.118 and the phone refused.
    """
    import hashlib

    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    from app.remote import certificate

    def identity(pem):
        cert = x509.load_pem_x509_certificate(pem.read_bytes())
        return hashlib.sha256(cert.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()

    old, old_key = certificate(tmp_path, "192.168.0.131")
    new, new_key = certificate(tmp_path, "192.168.0.118")

    assert old != new, "each address gets its own certificate, so browsers are happy"
    assert old_key == new_key == tmp_path / "jas.key", "but one key, kept"
    assert identity(old) == identity(new), "so the phone still recognises this laptop"


def test_a_certificate_from_an_older_key_is_not_reused(tmp_path):
    """Serving a certificate this key cannot prove it owns would fail the handshake outright."""
    from app.remote import certificate

    cert_file, key_file = certificate(tmp_path, "192.168.0.131")
    kept = cert_file.read_bytes()
    key_file.write_bytes(certificate(tmp_path / "elsewhere", "10.0.0.1")[1].read_bytes())

    again, _ = certificate(tmp_path, "192.168.0.131")
    assert again.read_bytes() != kept, "the mismatched certificate must be replaced, not served"


def test_the_phone_only_acts_when_jas_is_called():
    """The microphone is open the whole time, so it hears the room and not only its owner.

    Unchecked, four minutes of somebody else's conversation sent 72 clips and JAS tried to act on
    "Amazon is an external API power". No loudness threshold can help: that audio IS speech.
    """
    _, overheard = _hearing("Amazon is an external API power. You see, even though I got")
    status, payload = call(overheard._listen, VoiceRequest())
    assert status == 200
    assert payload["heard"] == "", "a conversation JAS overheard must not become a command"
    assert not payload["error"], "and it is not an error either - nobody was talking to it"


def test_being_called_by_name_runs_the_command_without_the_name():
    from app.remote import addressed_to_jas

    _, called = _hearing("Hey Jas, what time is it")
    _, payload = call(called._listen, VoiceRequest())
    assert payload["heard"] == "what time is it", "the name is not part of the request"

    # Whisper spells it several ways, and "jazz" is the commonest.
    assert addressed_to_jas("Jazz, lock my pc") == "lock my pc"
    assert addressed_to_jas("jasmine smells nice") is None, "the name must be a whole word"


def test_a_follow_up_needs_no_name():
    """Saying "jas" before every line of a conversation would be absurd."""
    core, control = _hearing("and open chrome as well")
    core.bus.publish(AssistantReply("It is half past six."))
    _, payload = call(control._listen, VoiceRequest())
    assert payload["heard"] == "and open chrome as well"


def test_stop_never_needs_the_name():
    """Being interrupted has to work on one word, whatever else is going on."""
    _, control = _hearing("stop")
    _, payload = call(control._listen, VoiceRequest())
    assert payload["heard"] == "stop"


def test_whisper_filling_in_silence_is_not_treated_as_a_command():
    """The phone's microphone is always open, so it sends the odd clip of room tone.

    Whisper is generative: given a second of near-silence it returns the likeliest thing a clip
    that long contains, learned from captioned video. "Thank you." arrived from an empty room.
    """
    from app.remote import is_hallucination

    for silence in ("Thank you.", "Thanks for watching!", "you", "So...", "Bye.",
                    "[BLANK_AUDIO]", "...", "♪♪", "Hmm.", "(silence)"):
        assert is_hallucination(silence), silence


def test_the_words_that_must_never_be_filtered():
    """One-word answers carry the most weight, so the filter must not touch them.

    "yes" answers a confirmation before something irreversible; "stop" is how JAS is interrupted.
    Dropping either would break the two paths that most need to work on a single word.
    """
    from app.remote import is_hallucination

    for real in ("yes", "yeah", "no", "ok", "okay", "sure", "stop", "cancel", "lock my pc",
                 "thank you for opening Chrome", "send a message to sunny"):
        assert not is_hallucination(real), real


def test_a_cough_does_not_wake_whisper():
    """The clip always ends with 1.1 s of silence, so the gate must measure the speech, not the clip.

    Measuring the clip is how "Thank you." arrived from an empty room: Whisper hallucinates on
    near-silence, and a 100 ms blip plus the silence tail cleared a 350 ms minimum every time.
    """
    from app.remote import phone_page

    page = phone_page("JAS")
    assert "spokenMs" in page, "the speech counter must exist"
    assert "now - startedAt > MIN_MS" not in page, "MIN_MS must not be measured across the clip"
    assert "CLEARLY_SPEECH" in page, "a peak test, so a fan at the threshold is not a voice"
    assert "if (wasSpeech) send(done)" in page, "a clip that fails the tests is dropped, not sent"


def test_the_phone_shows_the_same_face_as_the_laptop():
    """The phone is not a cut-down JAS: same moods, same planets, same blinking."""
    from app.remote import phone_page

    page = phone_page("JAS")
    for mood in ("calm", "alert", "listening", "thinking", "focused", "warm", "concerned", "asleep"):
        assert mood in page, mood
    for body in ("moon", "mercury", "jupiter", "earth", "saturn"):
        assert body in page, body
    assert "craters" in page and "rings" in page and "blink" in page
    assert 'class="edge"' in page, "edge lighting"


def test_the_certificate_covers_this_machines_address(tmp_path):
    """A phone will not open its microphone on an insecure page, so HTTPS is not optional."""
    import ipaddress

    from cryptography import x509

    from app.remote import certificate

    cert_file, key_file = certificate(tmp_path, "192.168.0.131")
    assert cert_file.exists() and key_file.exists()

    cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert ipaddress.ip_address("192.168.0.131") in names.get_values_for_type(x509.IPAddress)
    assert "localhost" in names.get_values_for_type(x509.DNSName)

    lifetime = cert.not_valid_after_utc - cert.not_valid_before_utc
    assert lifetime.days > 3000, "regenerating yearly would mean re-accepting the warning yearly"


def test_the_certificate_is_made_once_and_kept(tmp_path):
    from app.remote import certificate

    first = certificate(tmp_path, "192.168.0.131")[0].read_bytes()
    assert certificate(tmp_path, "192.168.0.131")[0].read_bytes() == first, \
        "a new certificate each restart would warn the phone every time"


def test_a_hostname_that_is_not_an_ip_still_works(tmp_path):
    from cryptography import x509

    from app.remote import certificate

    cert_file, _ = certificate(tmp_path, "my-laptop")
    cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "my-laptop" in names.get_values_for_type(x509.DNSName)


def test_the_address_given_to_the_user_is_https():
    from app.remote import local_address

    assert local_address(8770).startswith("https://")


def test_it_installs_as_an_app_rather_than_a_browser_tab(remote):
    """"Add to home screen" should give a real app: own icon, own window, no address bar."""
    _, control = remote
    status, manifest = call(control._manifest, Request(pin=""))
    assert status == 200
    assert manifest["display"] == "standalone", "not a browser tab"
    assert manifest["name"] == "JAS"
    assert {i["sizes"] for i in manifest["icons"]} == {"192x192", "512x512"}


def test_the_app_icon_is_jas_face(remote):
    _, control = remote
    response = asyncio.run(control._icon(IconRequest(192)))
    assert response.status == 200 and response.content_type == "image/png"
    assert response.body[:4] == b"\x89PNG"

    from PIL import Image
    import io
    assert Image.open(io.BytesIO(response.body)).size == (192, 192)


def test_icons_are_drawn_once(remote):
    _, control = remote
    asyncio.run(control._icon(IconRequest(192)))
    first = control._icons[192]
    asyncio.run(control._icon(IconRequest(192)))
    assert control._icons[192] is first, "redrawing the icon on every request would be wasteful"


def test_nothing_is_cached_by_the_service_worker(remote):
    """A stale answer would be worse than no answer, so the worker only enables installing."""
    _, control = remote
    status, script = call(control._worker, Request(pin=""))
    assert status == 200
    assert "skipWaiting" in script
    assert "caches.open" not in script and "cache.put" not in script


def test_the_eyes_follow_the_phones_tilt():
    from app.remote import phone_page

    page = phone_page("JAS")
    assert "deviceorientation" in page
    assert "gamma" in page and "beta" in page, "left-right and front-back tilt"
    assert "requestPermission" in page, "iPhones only give motion after asking"


def test_the_certificate_can_be_installed_on_the_phone(remote, tmp_path):
    """Chrome will not install an app from a site it does not trust, so the phone needs this."""
    _, control = remote
    control._certificates = tmp_path
    response = asyncio.run(control._ca(Request(pin="")))
    assert response.status == 200
    assert response.content_type == "application/x-x509-ca-cert"
    assert b"BEGIN CERTIFICATE" in response.body
    assert "JAS.crt" in response.headers["Content-Disposition"]
