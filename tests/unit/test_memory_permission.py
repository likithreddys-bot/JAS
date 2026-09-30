"""Nothing is remembered without being asked first - a hard rule, enforced by the executor,
not left to the model's own good behaviour (CLAUDE.md's own stated philosophy: the executor
enforces confirmation, not the prompt).

Before this, `remember` and `learn_word` were LOW risk - the executor ran them with no
confirmation at all, and the system prompt separately told the model to use them "without
being asked... without announcing it every time". Both are fixed here.
"""
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.memory.store import MemoryStore
from app.tools.executor import ToolExecutor
from app.tools.memory_tools import memory_tools


def executor(tmp_path, confirm=None):
    memory = MemoryStore(tmp_path / "memory.db")
    core = Jarvis()
    core.start()
    for s in (S.WAKE_DETECTED, S.LISTENING, S.TRANSCRIBING, S.THINKING):
        core.state.transition(s)
    ex = ToolExecutor(core, memory_tools(memory, "Bengaluru"))
    if confirm is not None:
        ex.set_confirmer(confirm)
    return ex, memory


def test_remember_is_refused_with_no_way_to_ask(tmp_path):
    ex, memory = executor(tmp_path)  # no confirmer set, matching a tool call before one exists
    result = ex.run("remember", {"fact": "Likki prefers meetings after 3 PM"})
    assert result["ok"] is False
    assert memory.facts() == [], "must not be saved without a real chance to confirm"


def test_remember_asks_before_saving_anything(tmp_path):
    asked = []
    ex, memory = executor(tmp_path, confirm=lambda q: asked.append(q) or False)
    result = ex.run("remember", {"fact": "Likki prefers meetings after 3 PM"})

    assert result["ok"] is False and result["declined_by_user"] is True
    assert asked == ["Should I remember that Likki prefers meetings after 3 PM?"]
    assert memory.facts() == [], "declining must mean nothing is written, not written anyway"


def test_remember_only_saves_after_a_real_yes(tmp_path):
    ex, memory = executor(tmp_path, confirm=lambda q: True)
    result = ex.run("remember", {"fact": "Likki prefers meetings after 3 PM"})
    assert result["ok"] is True
    assert memory.facts() == ["Likki prefers meetings after 3 PM"]


def test_learn_word_also_asks_first(tmp_path):
    asked = []
    ex, memory = executor(tmp_path, confirm=lambda q: asked.append(q) or False)
    result = ex.run("learn_word", {"word": "Sreenidhi"})
    assert result["ok"] is False
    assert asked == ["Should I remember the word “Sreenidhi”?"]
    assert memory.words() == [], "declining must mean nothing is learned"


def test_learn_word_saves_only_after_yes(tmp_path):
    ex, memory = executor(tmp_path, confirm=lambda q: True)
    ex.run("learn_word", {"word": "Sreenidhi"})
    assert memory.words() == ["Sreenidhi"]


def test_forget_still_asks_too_matching_the_others_now(tmp_path):
    """This one already asked before tonight - included so the whole family is proven consistent
    in one place, not just the two that changed."""
    ex, memory = executor(tmp_path, confirm=lambda q: True)
    memory.remember("Likki prefers meetings after 3 PM")
    ex.run("forget", {"about": "meetings"})
    assert memory.facts() == []
