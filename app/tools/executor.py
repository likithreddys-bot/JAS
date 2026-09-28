"""Runs tool calls requested by the LLM: validate → permission → execute → report.

Also drives the EXECUTING / OBSERVING states and publishes step events for the UI, and gives
failed tools one safe retry (see `run`) rather than leaving recovery entirely to the LLM's
improvisation, per the "retry safely once if idempotent" standard in CLAUDE.md §6.
"""
from __future__ import annotations

import itertools
import logging
from typing import Any, Callable

from app.core.events.events import ToolFinished, ToolStarted
from app.core.jarvis import Jarvis
from app.core.state.states import JarvisState as S
from app.tools.base import Risk, TaskCancelled, Tool, ToolResult

log = logging.getLogger("jarvis.agent")

_JSON_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
_ACTIVE = (S.THINKING, S.RESPONDING, S.OBSERVING)
DECLINED = ("The user was asked to confirm and said no (or didn't answer), so nothing was done. "
            "Just acknowledge that; don't guess any other reason and don't retry.")


class ToolExecutor:
    def __init__(self, core: Jarvis, tools: list[Tool]) -> None:
        self._core = core
        self._tools = {t.name: t for t in tools}
        self._ids = itertools.count(1)
        self._confirm: Callable[[str], bool] | None = None

    @property
    def tools(self) -> list[Tool]:
        return list(self._tools.values())

    def set_confirmer(self, confirm: Callable[[str], bool]) -> None:
        """`confirm(question) -> bool` asks the user (by voice) and returns their answer."""
        self._confirm = confirm

    def run(self, name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        """Execute one tool call and return a JSON-serialisable result for the LLM."""
        args = dict(args or {})
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(False, error=f"Unknown tool {name!r}").to_dict()
        if problem := _validate(tool.parameters, args):
            log.warning("Rejected %s(%s): %s", name, args, problem)
            return ToolResult(False, error=f"Invalid arguments: {problem}").to_dict()

        self._check_not_cancelled()
        risk = tool.risk_for(args)
        if risk is not Risk.LOW:
            question = tool.confirm_question(**args) if tool.confirm_question else f"Should I {tool.label(**args).lower()}?"
            if self._confirm is None or not self._confirm(question):
                log.info("User declined %s(%s)", name, args)
                return {"ok": False, "declined_by_user": True, "error": DECLINED}
            self._check_not_cancelled()

        step_id = next(self._ids)
        label = tool.label(**args)
        state = self._core.state
        for current in _ACTIVE:
            if state.transition_from(current, S.EXECUTING):
                break
        self._core.bus.publish(ToolStarted(step_id, label, name))
        log.info("Tool %s(%s) [%s risk]", name, args, risk.value)
        result, crashed = self._attempt(tool, name, args)
        if crashed and risk is Risk.LOW:
            # Only a crash earns a retry, never an ordinary ok=False. A tool that raised hit
            # something unexpected - a stale window handle, a COM call made too soon - and trying
            # again half a second later, after re-checking cancellation, often just works. A tool
            # that instead deliberately returned ok=False ("nothing found", "nothing to do") gave a
            # clean, deterministic answer that will not have changed in the same instant; retrying
            # that would only double the cost of every routine miss from a vision or COM call for
            # no benefit. LOW risk is reused as the bar for "repeat automatically" because it is
            # already, by this project's own definition, "safe to run with no confirmation at all" -
            # MEDIUM/HIGH already got the user's one-time confirmation, and repeating a consequential
            # action they were never asked to repeat is exactly what must never happen on our own
            # initiative - a tool that half-sent a message must not risk sending it twice.
            self._check_not_cancelled()
            log.info("Tool %s crashed (%s) - retrying once, low risk", name, result.error)
            result, crashed = self._attempt(tool, name, args)
        log.info("Tool %s -> %s", name, result.to_dict())
        self._core.bus.publish(ToolFinished(step_id, label, result.ok, result.error, name))
        state.transition_from(S.EXECUTING, S.OBSERVING)
        return result.to_dict()

    def _attempt(self, tool: Tool, name: str, args: dict[str, Any]) -> tuple[ToolResult, bool]:
        try:
            return tool.run(**args), False
        except Exception as exc:
            log.exception("Tool %s crashed", name)
            return ToolResult(False, error=f"{type(exc).__name__}: {exc}"), True

    def _check_not_cancelled(self) -> None:
        if self._core.cancelled.is_set() or self._core.state.current in (S.SLEEPING, S.STANDBY):
            raise TaskCancelled()


def _validate(schema: dict[str, Any], args: dict[str, Any]) -> str | None:
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in args:
            return f"missing {key!r}"
    for key, value in args.items():
        if key not in properties:
            return f"unexpected {key!r}"
        spec = properties[key]
        expected = _JSON_TYPES.get(spec.get("type", ""))
        if expected and (not isinstance(value, expected) or (spec["type"] != "boolean" and isinstance(value, bool))):
            return f"{key!r} must be {spec['type']}"
        if "enum" in spec and value not in spec["enum"]:
            return f"{key!r} must be one of {spec['enum']}"
    return None
