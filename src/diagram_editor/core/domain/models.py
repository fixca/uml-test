"""Qt-free, serializable domain data and session snapshots."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4
import copy


class ValidationState(str, Enum):
    VALID = "VALID"
    VALIDATING = "VALIDATING"
    INVALID = "INVALID"
    RUNTIME_ERROR = "RUNTIME_ERROR"


@dataclass
class Node:
    id: str
    key: str
    label: str
    kind: str = "class"
    x: float = 0.0
    y: float = 0.0
    width: float = 170.0
    height: float = 72.0
    members: list[str] = field(default_factory=list)
    line_start: int = -1
    line_end: int = -1   # exclusive
    explicit: bool = False


@dataclass
class Edge:
    id: str
    source: str       # Node key
    target: str       # Node key
    relation: str
    label: str = ""
    kind: str = "relation"
    line_start: int = -1
    line_end: int = -1
    order: int = 0


@dataclass
class DiagramDocument:
    diagram_type: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    # Structural constraints such as sequence notes/activation blocks.
    decorations: list[dict[str, Any]] = field(default_factory=list)

    def node_by_id(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def edge_by_id(self, edge_id: str) -> Edge | None:
        return next((e for e in self.edges if e.id == edge_id), None)


@dataclass
class Snapshot:
    document_id: str
    source: str
    document: DiagramDocument
    source_revision: int
    valid_revision: int
    project_path: str | None
    saved_revision: int = -1
    status: str = ValidationState.VALID.value
    diagnostics: str = ""
    edit_revision: int = 0  # Monotonic session edit revision, including layout-only edits.

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Snapshot":
        doc = data.get("document") or {}
        nodes = [Node(**n) for n in doc.get("nodes", [])]
        edges = [Edge(**e) for e in doc.get("edges", [])]
        return cls(
            document_id=data["document_id"], source=data["source"],
            document=DiagramDocument(doc.get("diagram_type", "class"), nodes, edges, doc.get("decorations", [])),
            source_revision=int(data["source_revision"]), valid_revision=int(data["valid_revision"]),
            project_path=data.get("project_path"), saved_revision=int(data.get("saved_revision", -1)),
            status=data.get("status", "VALID"), diagnostics=data.get("diagnostics", ""),
            edit_revision=int(data.get("edit_revision", data["source_revision"])),
        )

    def clone(self) -> "Snapshot":
        return copy.deepcopy(self)


def new_document_id() -> str:
    return str(uuid4())


def new_object_id() -> str:
    return str(uuid4())
