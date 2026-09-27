"""JAS records how its choices turned out, and repeated mistakes become prompt lessons."""
from pathlib import Path

from app.core.events.events import TaskInterrupted, ToolFinished, TranscriptReady
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.learning import STOPPED, Learner, lessons_from
from app.memory.store import MemoryStore


def setup(tmp_path):
    core = Jarvis()
    memory = MemoryStore(tmp_path / "memory.db")
    return core, memory, Learner(core, memory)


def test_outcomes_are_recorded_against_the_request(tmp_path):
    core, memory, learner = setup(tmp_path)
    core.bus.publish(TranscriptReady("compact column A"))
    core.bus.publish(ToolFinished(1, "Fitting", True, "", "excel_autofit"))
    core.bus.publish(ToolFinished(2, "Pivoting", False, "rows and values clash", "excel_pivot_table"))

    reliability = dict((tool, (ok, bad)) for tool, ok, bad in memory.tool_reliability())
    assert reliability["excel_autofit"] == (1, 0)
    assert reliability["excel_pivot_table"] == (0, 1)


def test_one_failure_is_noise_but_two_is_a_lesson(tmp_path):
    core, memory, learner = setup(tmp_path)
    core.bus.publish(ToolFinished(1, "Pivoting", False, "rows and values clash", "excel_pivot_table"))
    assert learner.lessons() == "", "a single failure must not burn prompt tokens"

    core.bus.publish(ToolFinished(2, "Pivoting", False, "rows and values clash", "excel_pivot_table"))
    lesson = learner.lessons()
    assert "excel_pivot_table failed 2 times" in lesson
    assert "rows and values clash" in lesson


def test_being_told_to_stop_counts_against_what_was_running(tmp_path):
    """"Stop" is the clearest signal that the choice was wrong, so it is recorded as one."""
    core, memory, learner = setup(tmp_path)
    core.bus.publish(TranscriptReady("play some music"))
    for _ in range(2):
        core.bus.publish(ToolFinished(1, "Playing", True, "", "play_music"))
        core.bus.publish(TaskInterrupted("stopped by user"))

    lesson = learner.lessons()
    assert "play_music" in lesson and "stopped this 2 times" in lesson
    assert any(detail == STOPPED for _, detail, _ in memory.repeated_failures())


def test_an_interrupt_that_was_not_the_user_is_not_held_against_it(tmp_path):
    core, memory, learner = setup(tmp_path)
    core.bus.publish(ToolFinished(1, "Looking", True, "", "look_at_screen"))
    core.bus.publish(TaskInterrupted("screen locked"))
    assert memory.repeated_failures(minimum=1) == []


def test_lessons_are_capped_and_worst_first(tmp_path):
    core, memory, learner = setup(tmp_path)
    for n in range(10):
        for _ in range(n + 2):
            memory.record_outcome(f"tool{n}", False, f"error {n}")
    lesson = lessons_from(memory)
    assert lesson.count("\n- ") <= 6
    assert "tool9" in lesson.split("\n")[1], "the most repeated mistake comes first"


def test_no_lessons_when_nothing_has_gone_wrong(tmp_path):
    core, memory, learner = setup(tmp_path)
    core.bus.publish(ToolFinished(1, "Fitting", True, "", "excel_autofit"))
    assert learner.lessons() == ""
