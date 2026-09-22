"""Tools that let the LLM use JARVIS's memory, to-do list and weather."""
from __future__ import annotations

from typing import Callable

from app.memory.store import MemoryStore
from app.tools import weather
from app.tools.base import Risk, Tool, ToolResult


def memory_tools(memory: MemoryStore, home_city: str, on_word_learned: Callable[[], None] = lambda: None) -> list[Tool]:
    def remember(fact: str) -> ToolResult:
        new = memory.remember(fact)
        return ToolResult(True, {"remembered": fact, "already_known": not new})

    def recall(query: str) -> ToolResult:
        return ToolResult(True, memory.search(query))

    def forget(about: str) -> ToolResult:
        gone = memory.forget(about)
        if not gone:
            return ToolResult(False, error=f"I don't have anything remembered about {about!r}.")
        return ToolResult(True, {"forgotten": gone})

    def add_todo(text: str) -> ToolResult:
        return ToolResult(True, {"added": text, "id": memory.add_todo(text)})

    def list_todos() -> ToolResult:
        return ToolResult(True, {"open_todos": [{"id": i, "text": t} for i, t in memory.open_todos()]})

    def complete_todo(match: str) -> ToolResult:
        done = memory.complete_todo(match)
        if not done:
            return ToolResult(False, error=f"No open to-do matches {match!r}.")
        return ToolResult(True, {"completed": done})

    def learn_word(word: str) -> ToolResult:
        memory.learn_word(word)
        on_word_learned()
        return ToolResult(True, {"learned": word})

    def get_weather(city: str = "") -> ToolResult:
        try:
            report = weather.today(city or home_city)
        except Exception as exc:
            return ToolResult(False, error=f"Couldn't get the weather: {exc}")
        return ToolResult(True, {**report, "summary": weather.describe(report)})

    text = {"type": "string"}
    return [
        Tool("remember", "Save a lasting fact about the user (preferences, people, projects, routines, how they "
             "spell names). Use it on your own whenever the user shares something worth remembering.",
             {"type": "object", "properties": {"fact": text}, "required": ["fact"]}, remember,
             lambda fact: "Remembering that"),
        Tool("recall", "Search what you remember and past conversations.",
             {"type": "object", "properties": {"query": text}, "required": ["query"]}, recall, lambda query: "Recalling"),
        Tool("forget", "Forget remembered facts containing the given words (asks the user first).",
             {"type": "object", "properties": {"about": text}, "required": ["about"]}, forget,
             lambda about: f"Forgetting “{about}”", risk=Risk.MEDIUM,
             confirm_question=lambda about: f"Should I forget what I remember about {about}?"),
        Tool("add_todo", "Add an item to the user's to-do list.", {"type": "object", "properties": {"text": text},
             "required": ["text"]}, add_todo, lambda text: f"Adding to-do: {text[:30]}"),
        Tool("list_todos", "List the user's open to-dos.", {"type": "object", "properties": {}}, list_todos,
             lambda: "Checking your to-dos"),
        Tool("complete_todo", "Mark a to-do as done, by its number or some words from it.",
             {"type": "object", "properties": {"match": text}, "required": ["match"]}, complete_todo,
             lambda match: "Marking to-do done"),
        Tool("learn_word", "Learn a name or unusual word the user uses so speech recognition spells it right "
             "(e.g. names of people, projects, places).", {"type": "object", "properties": {"word": text},
             "required": ["word"]}, learn_word, lambda word: f"Learning “{word}”"),
        Tool("get_weather", "Today's weather (current, high/low, rain chance). City defaults to the user's home city.",
             {"type": "object", "properties": {"city": text}}, get_weather, lambda city="": "Checking the weather"),
    ]
