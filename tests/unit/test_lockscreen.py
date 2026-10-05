"""JARVIS follows the lock screen: rests with it, greets when it comes back."""
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.lockscreen import LockWatcher
from app.voice import quick


class FakeScreen:
    def __init__(self, locked=False):
        self.locked = locked

    def __call__(self):
        return self.locked


def watcher(core, screen, greeting="Hey Alex, I'm ready."):
    w = LockWatcher.__new__(LockWatcher)  # no polling thread in tests
    w._core, w._is_locked, w._greeting, w._poll = core, screen, greeting, 0.01
    w._bad_passwords = lambda: None  # Windows not asked about passwords in these tests
    w._set_face = None
    w._locked = screen()
    w._wrong_at_lock = 0
    w._intruder = False
    w._wrong_seen = 0
    w._blink_stop = None
    return w


def test_locking_the_screen_puts_jarvis_to_rest():
    core = Jarvis()
    core.start()
    screen = FakeScreen()
    watch = watcher(core, screen)

    screen.locked = True
    watch.check()
    assert core.state.current is S.RESTING

    watch.check()  # still locked: nothing more happens
    assert core.state.current is S.RESTING


def test_unlocking_wakes_jarvis_and_greets_without_a_briefing():
    core = Jarvis()
    core.start()
    screen = FakeScreen(locked=True)
    core.rest("screen locked")
    watch = watcher(core, screen)

    screen.locked = False
    watch.check()
    assert core.announcement == "Hey Alex, I'm ready."
    assert core.state.current is S.WAKE_DETECTED  # speaks the greeting, no morning briefing


def test_locking_interrupts_whatever_jarvis_was_doing():
    core = Jarvis()
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    core.state.transition(S.LISTENING)
    screen = FakeScreen()
    watch = watcher(core, screen)

    screen.locked = True
    watch.check()
    assert core.cancelled.is_set()


def test_lock_my_pc_is_an_instant_command_that_says_nothing():
    calls = []
    said = quick.run("Jarvis, lock my pc", lambda name, args: calls.append(name) or {"ok": True})
    assert calls == ["lock_pc"]
    assert said == ""  # nothing is spoken: the screen is about to go

    for phrase in ("lock my laptop", "lock the computer", "lock my screen", "lock"):
        assert quick.match(phrase)[0] == "lock_pc", phrase
    assert quick.match("lock the front door") is None


def watcher_with_passwords(core, screen, counts, faces):
    """A watcher whose password counter and lock-screen face are both fakes."""
    w = LockWatcher.__new__(LockWatcher)
    w._core, w._is_locked, w._greeting, w._poll = core, screen, "Hey Alex, I'm ready.", 0.01
    w._bad_passwords = lambda: counts[0]
    w._set_face = lambda mood: faces.append(mood) or True
    w._locked = screen()
    w._wrong_at_lock = counts[0]
    w._intruder = False
    w._wrong_seen = 0
    w._blink_stop = None
    return w


def test_a_wrong_password_turns_the_lock_screen_angry():
    core = Jarvis()
    core.start()
    screen, counts, faces = FakeScreen(), [3], []
    watch = watcher_with_passwords(core, screen, counts, faces)

    screen.locked = True
    watch.check()
    assert faces == ["watchful"], "locking shows the watchful face"

    counts[0] = 4          # someone got the password wrong
    watch.check()
    assert faces == ["watchful", "angry"]

    counts[0] = 5          # still trying: the face is already angry, don't thrash the API
    watch.check()
    assert faces == ["watchful", "angry"]


def test_unlocking_after_attempts_says_so_and_calms_down():
    core = Jarvis()
    core.start()
    screen, counts, faces = FakeScreen(locked=True), [3], []
    core.rest("screen locked")
    watch = watcher_with_passwords(core, screen, counts, faces)

    counts[0] = 5          # two wrong attempts while away
    screen.locked = False
    watch.check()
    assert faces[-1] == "watchful", "back to calm once you are in"
    assert "wrong 2 times" in core.announcement


def test_a_clean_unlock_is_just_a_greeting():
    core = Jarvis()
    core.start()
    screen, counts, faces = FakeScreen(locked=True), [3], []
    core.rest("screen locked")
    watch = watcher_with_passwords(core, screen, counts, faces)

    screen.locked = False
    watch.check()
    assert core.announcement == "Hey Alex, I'm ready."


def test_locking_starts_blinking_and_unlocking_stops_it():
    core = Jarvis()
    core.start()
    screen, counts, faces = FakeScreen(), [0], []
    watch = watcher_with_passwords(core, screen, counts, faces)

    screen.locked = True
    watch.check()
    assert watch._blink_stop is not None, "a lock must start a blink loop"

    screen.locked = False
    watch.check()
    assert watch._blink_stop is None, "unlocking must stop it, not leave it blinking behind you"


def test_the_blink_loop_alternates_shut_and_open_until_stopped():
    import threading

    from app import lockscreen

    core = Jarvis()
    core.start()
    faces = []
    watch = watcher_with_passwords(core, FakeScreen(), [0], faces)

    import time
    # Real timing would make this test slow and flaky - the gap and shut duration are near zero,
    # so several cycles happen almost immediately and the assertion is on the pattern, not the clock.
    lockscreen.BLINK_GAP_SECONDS = (0.0, 0.0)
    lockscreen.BLINK_SHUT_SECONDS = 0.0
    stop = threading.Event()
    thread = threading.Thread(target=watch._blink_loop, args=(stop,))
    thread.start()
    time.sleep(0.05)
    stop.set()
    thread.join(timeout=2)

    assert not thread.is_alive(), "the loop must exit once told to stop"
    assert len(faces) >= 2, "expected at least one full blink"
    assert faces[0] == "blink" and faces[1] == "watchful", "shuts before it reopens"


def test_the_blink_loop_never_overrides_the_angry_face():
    import threading

    from app import lockscreen

    core = Jarvis()
    core.start()
    faces = []
    watch = watcher_with_passwords(core, FakeScreen(), [0], faces)
    watch._intruder = True  # a warning is already showing

    import time
    lockscreen.BLINK_GAP_SECONDS = (0.0, 0.0)
    lockscreen.BLINK_SHUT_SECONDS = 0.0
    stop = threading.Event()
    thread = threading.Thread(target=watch._blink_loop, args=(stop,))
    thread.start()
    time.sleep(0.05)
    stop.set()
    thread.join(timeout=2)

    assert faces == [], "must never blink over a warning that is meant to hold still"


def test_the_angry_warning_uses_the_configured_name_not_a_hardcoded_one():
    """This used to be a literal string, so the warning always said the same name regardless of
    who was actually configured - it must come from the `name` argument every time."""
    from app.lockart import draw_face

    likki = draw_face("angry", "Likki", "JAS")
    sam = draw_face("angry", "Sam", "JAS")
    assert likki.tobytes() != sam.tobytes(), "the warning text must change with the configured name"


def test_blink_looks_different_from_watchful():
    from app.lockart import draw_face

    assert draw_face("watchful").tobytes() != draw_face("blink").tobytes()


def test_the_lock_faces_are_drawn_and_look_different():
    from app.lockart import draw_face

    calm, cross = draw_face("watchful"), draw_face("angry")
    assert calm.size == cross.size == (1920, 1080)
    assert calm.tobytes() != cross.tobytes(), "the two moods must not look the same"


def test_the_wallpaper_face_has_no_words_but_the_lock_screen_does():
    """The desktop already has your icons on it; the lock screen needs to say whose PC this is."""
    from app.lockart import draw_face

    lock = draw_face("angry", "Alex", "JAS", with_text=True)
    paper = draw_face("angry", "Alex", "JAS", with_text=False)
    assert lock.size == paper.size == (1920, 1080)
    assert lock.tobytes() != paper.tobytes(), "the lock screen version carries the warning text"


def test_the_wallpaper_is_written_even_if_windows_refuses_it(tmp_path, monkeypatch):
    import ctypes

    from app import lockart

    monkeypatch.setattr(ctypes.windll.user32, "SystemParametersInfoW", lambda *a: 0)
    assert lockart.set_wallpaper("watchful", tmp_path, "Alex", "JAS") is False
    assert (tmp_path / "wallpaper-watchful.jpg").exists(), "the picture is still drawn"


def test_the_attempt_count_survives_windows_clearing_it():
    """Windows zeroes bad_pw_count on a successful sign-in, so the peak must be remembered."""
    core = Jarvis()
    core.start()
    screen, counts, faces = FakeScreen(), [2], []
    watch = watcher_with_passwords(core, screen, counts, faces)

    screen.locked = True
    watch.check()
    counts[0] = 4            # two wrong tries
    watch.check()
    counts[0] = 0            # correct password: Windows resets the counter
    screen.locked = False
    watch.check()
    assert "wrong 2 times" in core.announcement, core.announcement


def test_the_lock_screen_brush_matches_the_websites():
    # website/src/core/enso.ts draws the same stroke from the same generator; the website's tests
    # pin the same dab count (data-dabs on the core layer). Change both or neither.
    from app.lockart import enso_dabs

    dabs = enso_dabs()
    assert len(dabs) == 11738
    assert round(sum(d[0] + d[1] * 3 + d[2] * 7 + d[3] * 11 for d in dabs), 6) == 143705.439656


def test_the_seal_writes_luffy_in_katakana_and_falls_back_to_an_initial():
    from app.lockart import KATAKANA, draw_face

    assert KATAKANA["luffy"] == "ルフィ"
    # An assistant name with no katakana spelling still draws (its initial goes on the seal).
    assert draw_face("watchful", "Likki", "Nova").size == (1920, 1080)
