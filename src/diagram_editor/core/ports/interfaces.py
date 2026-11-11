"""Narrow, framework-agnostic contracts."""
from typing import Protocol
from diagram_editor.core.domain.models import DiagramDocument, Snapshot


class ParserPort(Protocol):
    def parse(self, source: str, previous: DiagramDocument | None = None) -> DiagramDocument: ...


class RepositoryPort(Protocol):
    def save(self, path: str, snapshot: Snapshot) -> None: ...
    def load(self, path: str) -> Snapshot: ...


class ExporterPort(Protocol):
    format_name: str
    def export(self, scene: object, path: str, options: object) -> None: ...
