from app.memory.store import MemoryStore


def make(tmp_path):
    return MemoryStore(tmp_path / "memory.db")


def test_facts_are_remembered_once_and_can_be_forgotten(tmp_path):
    memory = make(tmp_path)
    assert memory.remember("Likki prefers meetings after 3 PM")
    assert not memory.remember("Likki  prefers meetings after 3 PM")  # duplicate (whitespace-normalised)
    memory.remember("Likki is building JARVIS and AI-Tester")
    assert memory.facts() == ["Likki prefers meetings after 3 PM", "Likki is building JARVIS and AI-Tester"]
    assert memory.forget("meetings") == ["Likki prefers meetings after 3 PM"]
    assert memory.facts() == ["Likki is building JARVIS and AI-Tester"]


def test_memory_survives_restart(tmp_path):
    make(tmp_path).remember("Favourite singer is Aditya Rikhari")
    assert make(tmp_path).facts() == ["Favourite singer is Aditya Rikhari"]


def test_todos(tmp_path):
    memory = make(tmp_path)
    first = memory.add_todo("finish the BERT model")
    memory.add_todo("call Rahul")
    assert memory.open_todos() == [(first, "finish the BERT model"), (first + 1, "call Rahul")]
    assert memory.complete_todo("bert") == ["finish the BERT model"]
    assert memory.complete_todo(str(first + 1)) == ["call Rahul"]
    assert memory.open_todos() == []


def test_learned_words_and_search(tmp_path):
    memory = make(tmp_path)
    memory.learn_word("Likki")
    memory.learn_word("likki")  # same word, different case
    assert memory.words() == ["Likki"]
    memory.remember("Likki works at Vaibhav Vyapaar")
    memory.log_exchange("what's the weather", "It's 25 degrees in Bengaluru.")
    found = memory.search("weather in Bengaluru")
    assert found["conversations"][0]["jarvis"] == "It's 25 degrees in Bengaluru."
    assert memory.search("vaibhav")["facts"] == ["Likki works at Vaibhav Vyapaar"]


def test_context_for_the_prompt(tmp_path):
    memory = make(tmp_path)
    assert memory.context() == ""
    memory.remember("Likki likes short answers")
    memory.add_todo("reply to Rahul")
    memory.log_exchange("hi", "Hello Likki!")
    context = memory.context()
    assert "Likki likes short answers" in context and "reply to Rahul" in context and "Hello Likki!" in context
