"""One document's editable state. All state transitions occur on the UI/application thread."""
from __future__ import annotations
from copy import deepcopy
from diagram_editor.core.domain.models import (DiagramDocument, Snapshot,
    ValidationState, new_document_id)
from diagram_editor.modules.history.manager import CommandManager
from diagram_editor.modules.mermaid.parser import ParseError, SubsetMermaidParser
from diagram_editor.modules.mermaid.source_sync import SourceSync, SourceSyncError
from diagram_editor.modules.events.bus import EventBus, Event


DEFAULT_CLASS = """classDiagram
    class User {
        +String name
        +login()
    }
    class Service {
        +execute()
    }
    User --> Service : calls
"""
DEFAULT_SEQUENCE = """sequenceDiagram
    participant User
    participant Server
    User->>Server: Request
    Server-->>User: Response
"""


class DocumentSession:
    def __init__(self, source: str = DEFAULT_CLASS, *, parser=None,
                 bus: EventBus | None = None, document_id: str | None = None):
        self.document_id = document_id or new_document_id()
        self.parser = parser or SubsetMermaidParser()
        self.sync = SourceSync(self.parser)
        self.bus = bus or EventBus()
        self.source = source
        self.document = DiagramDocument("class")
        self.source_revision = 0
        self.edit_revision = 0
        self.valid_revision = -1
        self.project_path: str | None = None
        self.saved_revision = -1
        self.recovery_revision = -1
        self.status = ValidationState.VALIDATING
        self.diagnostics = ""
        self.save_error = False
        self.history = CommandManager()
        self.validate(self.source_revision)

    def _emit(self, name: str, payload=None):
        self.bus.emit(Event(name, self.document_id, self.edit_revision, payload))

    def snapshot(self) -> Snapshot:
        return Snapshot(self.document_id, self.source, deepcopy(self.document),
                        self.source_revision, self.valid_revision, self.project_path,
                        self.saved_revision, self.status.value, self.diagnostics, self.edit_revision)

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot, *, parser=None, bus=None) -> "DocumentSession":
        # Never parse before recovering the last-good model (error source may be invalid).
        self = cls.__new__(cls)
        self.document_id = snapshot.document_id
        self.parser = parser or SubsetMermaidParser()
        self.sync = SourceSync(self.parser)
        self.bus = bus or EventBus()
        self.source = snapshot.source
        self.document = deepcopy(snapshot.document)
        self.source_revision = snapshot.source_revision
        self.edit_revision = snapshot.edit_revision
        self.valid_revision = snapshot.valid_revision
        self.project_path = snapshot.project_path
        self.saved_revision = snapshot.saved_revision
        self.recovery_revision = -1
        self.status = ValidationState.VALIDATING
        self.diagnostics = ""
        self.save_error = False
        self.history = CommandManager()
        self.validate(self.source_revision)
        return self

    def begin_source_edit(self, source: str):
        if source == self.source:
            return False
        before = self.snapshot()
        self.source = source
        self.source_revision += 1
        self.edit_revision += 1
        self.status = ValidationState.VALIDATING
        self.diagnostics = ""
        self._emit("SourceChanged")
        self._emit("ValidationStarted")
        self.history.record(before, self.snapshot(), "source")
        return True

    def validate(self, requested_revision: int, parsed: DiagramDocument | Exception | None = None) -> bool:
        if requested_revision != self.source_revision:
            return False
        if parsed is None:
            try:
                parsed = self.parser.parse(self.source, deepcopy(self.document))
            except Exception as exc:
                parsed = exc
        if isinstance(parsed, Exception):
            self.status = ValidationState.INVALID if isinstance(parsed, ParseError) else ValidationState.RUNTIME_ERROR
            self.diagnostics = str(parsed)
            self._emit("ValidationFailed", self.diagnostics)
            return False
        self.document = parsed
        self.valid_revision += 1
        self.status = ValidationState.VALID
        self.diagnostics = ""
        self._emit("ValidationSucceeded")
        self._emit("DocumentChanged")
        return True

    def _commit_gui_source(self, candidate: str):
        if self.status != ValidationState.VALID:
            raise SourceSyncError("검증 중이거나 오류 상태에서는 구조를 변경할 수 없습니다")
        if candidate == self.source:
            return
        before = self.snapshot()
        # Parse first. This is the atomic boundary: neither the old source nor
        # model is modified before all checks have succeeded.
        replacement = self.parser.parse(candidate, deepcopy(self.document))
        self.source = candidate
        self.source_revision += 1
        self.edit_revision += 1
        self.document = replacement
        self.valid_revision += 1
        self.diagnostics = ""
        self.history.record(before, self.snapshot(), "diagram")
        self._emit("SourceChanged")
        self._emit("DocumentChanged")

    def add_node(self, name: str):
        self._commit_gui_source(self.sync.add_node(self.source, self.document, name))

    def delete(self, selected_ids: set[str]):
        if self.status != ValidationState.VALID:
            raise SourceSyncError("오류 또는 검증 중에는 삭제할 수 없습니다")
        self._commit_gui_source(self.sync.delete(self.source, self.document, selected_ids))

    def copy(self, selected_ids: set[str]) -> dict:
        return self.sync.copy(self.document, selected_ids)

    def paste(self, clipboard: dict):
        if self.status != ValidationState.VALID:
            raise SourceSyncError("오류 또는 검증 중에는 붙여넣을 수 없습니다")
        self._commit_gui_source(self.sync.paste(self.source, self.document, clipboard))

    def move_node(self, node_id: str, x: float, y: float):
        self.move_nodes([(node_id, x, y)])

    def move_nodes(self, positions: list[tuple[str, float, float]]):
        """Atomically commit a multi-selection drag as a single Undo step."""
        if self.status != ValidationState.VALID:
            raise SourceSyncError("오류 또는 검증 중에는 이동할 수 없습니다")
        updates = {}
        for node_id, x, y in positions:
            node = self.document.node_by_id(node_id)
            if not node:
                raise SourceSyncError(f"대상 노드를 찾지 못했습니다: {node_id}")
            if self.document.diagram_type == "sequence":
                y = node.y  # Participant order on the vertical time axis is immutable.
            updates[node_id] = (round(float(x), 2), round(float(y), 2))
        if not any((self.document.node_by_id(oid).x, self.document.node_by_id(oid).y) != coord
                   for oid, coord in updates.items()):
            return
        before = self.snapshot()
        for node_id, (x, y) in updates.items():
            node = self.document.node_by_id(node_id)
            node.x, node.y = x, y
        self.edit_revision += 1
        self.valid_revision += 1
        self.history.record(before, self.snapshot(), "diagram")
        self._emit("DocumentChanged")

    def _restore(self, snapshot: Snapshot):
        source_changed = snapshot.source != self.source
        self.source = snapshot.source
        self.document = deepcopy(snapshot.document)
        if source_changed:
            self.source_revision += 1
        self.edit_revision += 1  # Live session edit revisions never roll back.
        self.valid_revision += 1
        self.status = ValidationState.VALIDATING
        self.diagnostics = ""
        self._emit("SourceChanged")
        self._emit("ValidationStarted")

    def undo(self) -> bool:
        state = self.history.undo(self.status.value)
        if state is None:
            return False
        self._restore(state)
        return True

    def redo(self) -> bool:
        state = self.history.redo(self.status.value)
        if state is None:
            return False
        self._restore(state)
        return True
