"""Thread-safe publish/subscribe event bus — the integration seam between subsystems.

Handlers run synchronously in the publisher's thread. Consumers that must run on
another thread (e.g. the Qt UI) are responsible for marshalling.
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger("jarvis.core.events")

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: type, handler: Handler) -> Callable[[], None]:
        """Register `handler` for events of exactly `event_type`. Returns an unsubscribe function."""
        with self._lock:
            self._handlers[event_type].append(handler)

        def unsubscribe() -> None:
            with self._lock:
                if handler in self._handlers[event_type]:
                    self._handlers[event_type].remove(handler)

        return unsubscribe

    def publish(self, event: Any) -> None:
        with self._lock:
            handlers = list(self._handlers[type(event)])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # One broken subscriber must not break the publisher or other subscribers.
                log.exception("Event handler %r failed for %r", handler, event)
