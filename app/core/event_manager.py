"""Small publish/subscribe event bus.

Why: UI pages must react to changes (for example a new project) without
importing each other. The event bus keeps those dependencies out of the UI.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import logging

logger = logging.getLogger(__name__)


class EventManager:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable) -> None:
        if callback not in self._subscribers[event]:
            self._subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> None:
        callbacks = self._subscribers.get(event, [])
        if callback in callbacks:
            callbacks.remove(callback)

    def emit(self, event: str, *args, **kwargs) -> None:
        for callback in list(self._subscribers.get(event, [])):
            try:
                callback(*args, **kwargs)
            except Exception:  # noqa: BLE001 - one broken listener must not stop others
                logger.exception("Event listener failed for %s", event)
