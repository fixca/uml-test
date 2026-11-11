"""In-process, local event bus. Subscriptions are scoped and reversible."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Event:
    name: str
    document_id: str
    revision: int
    payload: Any = None


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(self, name: str, callback: Callable[[Event], None]) -> Callable[[], None]:
        self._subscribers[name].append(callback)
        def unsubscribe():
            if callback in self._subscribers[name]:
                self._subscribers[name].remove(callback)
        return unsubscribe

    def emit(self, event: Event) -> None:
        for callback in tuple(self._subscribers.get(event.name, [])):
            try:
                callback(event)
            except Exception:
                # A failing observer cannot roll back the committed command.
                import logging
                logging.exception("EventBus subscriber error: %s", event.name)
