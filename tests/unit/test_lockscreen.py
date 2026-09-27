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


def watcher(core, screen, greeting="Hey Likki, I'm ready."):
    w = LockWatcher.__new__(LockWatcher)  # no polling thread in tests
    w._core, w._is_locked, w._greeting, w._poll = core, screen, greeting, 0.01
    w._bad_passwords = lambda: None  # Windows not asked about passwords in these tests
    w._set_face = None
    w._locked = screen()
    w._wrong_at_lock = 0
    w._intruder = False
    w._wrong_seen = 0
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
    assert core.announcement == "Hey Likki, I'm ready."
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
    w._core, w._is_locked, w._greeting, w._poll = core, screen, "Hey Likith, I'm ready.", 0.01
    w._bad_passwords = lambda: counts[0]
    w._set_face = lambda mood: faces.append(mood) or True
    w._locked = screen()
    w._wrong_at_lock = counts[0]
    w._intruder = False
    w._wrong_seen = 0
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
    assert core.announcement == "Hey Likith, I'm ready."


def test_the_lock_faces_are_drawn_and_look_different():
    from app.lockart import draw_face

    calm, cross = draw_face("watchful"), draw_face("angry")
    assert calm.size == cross.size == (1920, 1080)
    assert calm.tobytes() != cross.tobytes(), "the two moods must not look the same"


def test_the_wallpaper_face_has_no_words_but_the_lock_screen_does():
    """The desktop already has your icons on it; the lock screen needs to say whose PC this is."""
    from app.lockart import draw_face

    lock = draw_face("angry", "Likith", "JAS", with_text=True)
    paper = draw_face("angry", "Likith", "JAS", with_text=False)
    assert lock.size == paper.size == (1920, 1080)
    assert lock.tobytes() != paper.tobytes(), "the lock screen version carries the warning text"


def test_the_wallpaper_is_written_even_if_windows_refuses_it(tmp_path, monkeypatch):
    import ctypes

    from app import lockart

    monkeypatch.setattr(ctypes.windll.user32, "SystemParametersInfoW", lambda *a: 0)
    assert lockart.set_wallpaper("watchful", tmp_path, "Likith", "JAS") is False
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
