"""Registration point for future diagram-type behavior."""
from dataclasses import dataclass
from typing import Protocol


class DiagramTypeHandler(Protocol):
    name: str
    allow_node_drag: bool
    def allow_message_drag(self) -> bool: ...


@dataclass
class ClassHandler:
    name: str = "class"
    allow_node_drag: bool = True
    def allow_message_drag(self) -> bool: return False


@dataclass
class SequenceHandler:
    name: str = "sequence"
    allow_node_drag: bool = True  # Horizontal participant position only.
    def allow_message_drag(self) -> bool: return False


class TypeRegistry:
    def __init__(self):
        self._handlers: dict[str, DiagramTypeHandler] = {}
        self.register(ClassHandler())
        self.register(SequenceHandler())

    def register(self, handler: DiagramTypeHandler):
        self._handlers[handler.name] = handler

    def get(self, name: str) -> DiagramTypeHandler:
        return self._handlers[name]
