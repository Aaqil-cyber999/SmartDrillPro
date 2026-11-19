"""Bridge publish/subscribe events into Qt signals.

The event bus may be emitted from worker threads. Qt signals are thread-safe
and deliver queued callbacks on the GUI thread when the receiver lives there.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject, Signal

from app.core.event_manager import EventManager


class QtEventBridge(QObject):
    event_received = Signal(str, tuple)

    def __init__(
        self,
        events: EventManager,
        names: Iterable[str],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._events = events
        self._callbacks: dict[str, object] = {}
        for name in names:
            callback = self._make_callback(name)
            events.subscribe(name, callback)
            self._callbacks[name] = callback

    def _make_callback(self, name: str):
        def callback(*args) -> None:
            self.event_received.emit(name, tuple(args))
        return callback

    def close(self) -> None:
        for name, callback in self._callbacks.items():
            self._events.unsubscribe(name, callback)
        self._callbacks.clear()
