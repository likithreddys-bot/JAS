import pytest

from app.core.events.bus import EventBus
from app.core.events.events import StateChanged
from app.core.jarvis import Jarvis
from app.core.state.machine import InvalidTransition, StateMachine
from app.core.state.states import TRANSITIONS, JarvisState as S


def make():
    bus = EventBus()
    events = []
    bus.subscribe(StateChanged, events.append)
    return StateMachine(bus), events


def test_starts_in_starting():
    sm, _ = make()
    assert sm.current is S.STARTING


def test_full_voice_cycle_publishes_events():
    sm, events = make()
    path = [S.STANDBY, S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING, S.RESPONDING, S.STANDBY]
    for target in path:
        sm.transition(target)
    assert [e.current for e in events] == path
    assert events[0].previous is S.STARTING


def test_invalid_transition_rejected_and_state_unchanged():
    sm, events = make()
    sm.transition(S.STANDBY)
    with pytest.raises(InvalidTransition):
        sm.transition(S.EXECUTING)
    assert sm.current is S.STANDBY
    assert len(events) == 1


def test_error_reachable_from_every_state_except_itself():
    for state, targets in TRANSITIONS.items():
        assert (S.ERROR in targets) is (state is not S.ERROR)


def test_every_state_has_transitions_defined():
    assert set(TRANSITIONS) == set(S)


def test_error_carries_reason():
    sm, events = make()
    sm.transition(S.ERROR, "microphone not found")
    assert events[-1].reason == "microphone not found"


def test_pause_and_resume():
    core = Jarvis()
    core.start()
    core.pause()
    assert core.paused
    core.pause()  # idempotent
    core.resume()
    assert core.state.current is S.STANDBY


def test_pause_from_active_state_goes_through_standby():
    core = Jarvis()
    core.start()
    core.state.transition(S.WAKE_DETECTED)
    core.state.transition(S.LISTENING)
    core.toggle_pause()
    assert core.state.current is S.SLEEPING
