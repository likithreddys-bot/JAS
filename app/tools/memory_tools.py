"""Tools that let the LLM use JARVIS's memory, to-do list and weather."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from app.memory.store import MemoryStore
from app.tools import weather
from app.tools.base import Risk, Tool, ToolResult


TIME_FORMATS = ("%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p")


def parse_when(at: str, in_minutes: int, now: datetime) -> datetime:
    """"2026-09-23T18:00", "18:00", "6:30 PM" or N minutes from now -> a datetime in the future."""
    if in_minutes:
        return now + timedelta(minutes=in_minutes)
    at = at.strip().upper()
    if not at:
        raise ValueError("Tell me when: a time, a date and time, or in how many minutes.")
    try:
        due = datetime.fromisoformat(at.replace(" ", "T") if len(at) > 8 and at[4:5] == "-" else at)
    except ValueError:
        for fmt in TIME_FORMATS:
            try:
                clock = datetime.strptime(at, fmt).time()
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"I couldn't understand the time {at!r}.") from None
        due = datetime.combine(now.date(), clock)
        if due <= now:
            due += timedelta(days=1)  # "at 9" when it's already past 9 means tomorrow
    if due < now - timedelta(minutes=1):
        raise ValueError(f"{due:%A %I:%M %p} has already passed.")
    return due


def memory_tools(
    memory: MemoryStore,
    home_city: str,
    on_word_learned: Callable[[], None] = lambda: None,
    now: Callable[[], datetime] = datetime.now,
) -> list[Tool]:
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

    def create_reminder(text: str, at: str = "", in_minutes: int = 0, repeat: str = "none") -> ToolResult:
        try:
            due = parse_when(at, in_minutes, now())
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
        reminder_id = memory.add_reminder(text, due, repeat)
        return ToolResult(True, {"id": reminder_id, "text": text, "when": f"{due:%A %d %B, %I:%M %p}", "repeat": repeat})

    def list_reminders() -> ToolResult:
        return ToolResult(True, {"reminders": [
            {"id": r["id"], "when": f"{r['due']:%A %d %B, %I:%M %p}", "text": r["text"], "repeat": r["repeat"]}
            for r in memory.upcoming_reminders()]})

    def cancel_reminder(match: str) -> ToolResult:
        cancelled = memory.cancel_reminders(match)
        if not cancelled:
            return ToolResult(False, error=f"No upcoming reminder matches {match!r}.")
        return ToolResult(True, {"cancelled": cancelled})

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
        Tool("create_reminder",
             "Remind the user at a time: pass `at` as a local date-time 'YYYY-MM-DDTHH:MM' (work out 'tomorrow', "
             "'tonight' etc. from the current date), or `in_minutes` for 'in 20 minutes'. repeat: none, daily, "
             "weekdays or weekly. They get a Windows notification and JARVIS says it out loud.",
             {"type": "object", "properties": {
                 "text": {"type": "string", "description": "What to remind them about, e.g. 'call Rahul'"},
                 "at": {"type": "string"}, "in_minutes": {"type": "integer"},
                 "repeat": {"type": "string", "enum": ["none", "daily", "weekdays", "weekly"]}},
              "required": ["text"]},
             create_reminder, lambda text, at="", in_minutes=0, repeat="none": f"Setting reminder: {text[:30]}"),
        Tool("list_reminders", "List upcoming reminders.", {"type": "object", "properties": {}}, list_reminders,
             lambda: "Checking reminders"),
        Tool("cancel_reminder", "Cancel a reminder by its number or words from it.",
             {"type": "object", "properties": {"match": text}, "required": ["match"]}, cancel_reminder,
             lambda match: "Cancelling reminder"),
        Tool("get_weather", "Today's weather (current, high/low, rain chance). City defaults to the user's home city.",
             {"type": "object", "properties": {"city": text}}, get_weather, lambda city="": "Checking the weather"),
    ]
