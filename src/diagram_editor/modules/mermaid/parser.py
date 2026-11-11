"""Offline structural adapter for a conservative, documented Mermaid subset.

This is *not* the official Mermaid JS parser. Unknown structural statements fail
closed; no invalid candidate will overwrite the previous valid document.
"""
from __future__ import annotations
import re
from collections import Counter
from diagram_editor.core.domain.models import DiagramDocument, Edge, Node, new_object_id


class ParseError(ValueError):
    def __init__(self, message: str, line: int | None = None, kind: str = "syntax"):
        self.line = line
        self.kind = kind
        super().__init__(f"{line}행: {message}" if line is not None else message)


CLASS_RELATION = re.compile(
    r"^([A-Za-z_][\w-]*)\s+(<\|--|--\|>|\*--|--\*|o--|--o|<-->|<--|-->|\.\.>|<\.\.|\.\.|--|\.\.\|>|<\|\.\.)\s+"
    r"([A-Za-z_][\w-]*)(?:\s*:\s*(.+))?$"
)
CLASS_DECLARE = re.compile(r"^class\s+([A-Za-z_][\w-]*)(?:\s*\[\s*\"?([^\]\"]+)\"?\s*\])?(\s*\{)?\s*$")
CLASS_INLINE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.+)$")
SEQ_PARTICIPANT = re.compile(r"^(participant|actor)\s+([A-Za-z_][\w-]*)(?:\s+as\s+(.+))?$", re.I)
SEQ_MESSAGE = re.compile(r"^([A-Za-z_]\w*(?:-\w+)*)\s*(-->>|->>|-->|->|--x|-x|--\)|-\))\s*([A-Za-z_]\w*(?:-\w+)*)([+-])?\s*:\s*(.*)$")
SEQ_NOTE = re.compile(r"^Note\s+(left of|right of|over)\s+([\w,-]+)\s*:\s*(.+)$", re.I)
SEQ_BLOCK = re.compile(r"^(loop|alt|opt|par|critical|break|rect|box)\b\s*(.*)$", re.I)
SEQ_OPTION = re.compile(r"^(else|and|option)\b\s*(.*)$", re.I)


class SubsetMermaidParser:
    """Parse only syntax that the GUI can represent/safely patch."""
    def parse(self, source: str, previous: DiagramDocument | None = None) -> DiagramDocument:
        lines = source.splitlines()
        first = next(((i, s.strip()) for i, s in enumerate(lines)
                      if s.strip() and not s.strip().startswith("%%")), None)
        if first is None:
            return DiagramDocument("class")
        index, header = first
        if header == "classDiagram" or header == "classDiagram-v2":
            doc = self._parse_class(lines, index)
        elif header == "sequenceDiagram":
            doc = self._parse_sequence(lines, index)
        else:
            raise ParseError("classDiagram 또는 sequenceDiagram 머리글이 필요합니다", index + 1)
        self._preserve_identity(doc, previous)
        self._initial_layout(doc, previous)
        return doc

    @staticmethod
    def _is_ignored(t: str) -> bool:
        return not t or t.startswith("%%")

    def _parse_class(self, lines: list[str], header_index: int) -> DiagramDocument:
        doc = DiagramDocument("class")
        by_key: dict[str, Node] = {}
        def ensure(key: str, at: int = -1, explicit: bool = False, label: str | None = None) -> Node:
            if key not in by_key:
                n = Node(new_object_id(), key, label or key, "class", line_start=at, line_end=at + 1 if at >= 0 else -1, explicit=explicit)
                by_key[key] = n
                doc.nodes.append(n)
            n = by_key[key]
            if explicit:
                n.explicit = True
                if at >= 0 and (n.line_start < 0 or at < n.line_start):
                    n.line_start = at
                    n.line_end = at + 1
                if label:
                    n.label = label
            return n
        in_block: Node | None = None
        for idx in range(header_index + 1, len(lines)):
            t = lines[idx].strip()
            if self._is_ignored(t):
                continue
            if in_block:
                if t == "}":
                    in_block.line_end = idx + 1
                    in_block = None
                elif t in ("{",) or "{" in t or "}" in t:
                    raise ParseError("클래스 블록 내부의 중첩 괄호는 지원하지 않습니다", idx + 1, "unsupported")
                else:
                    in_block.members.append(t)
                continue
            match = CLASS_DECLARE.fullmatch(t)
            if match:
                n = ensure(match[1], idx, True, match[2])
                if match[3]:
                    in_block = n
                continue
            if t == "}":
                raise ParseError("대응되는 클래스 블록 시작이 없습니다", idx + 1)
            match = CLASS_RELATION.fullmatch(t)
            if match:
                left, op, right, label = match.groups()
                ensure(left)
                ensure(right)
                doc.edges.append(Edge(new_object_id(), left, right, op, label or "", line_start=idx, line_end=idx + 1, order=len(doc.edges)))
                continue
            match = CLASS_INLINE.fullmatch(t)
            if match:
                n = ensure(match[1], idx, True)
                n.members.append(match[2])
                # A second declaration line must not make a discontinuous range
                if n.line_start < 0:
                    n.line_start = idx
                n.line_end = max(n.line_end, idx + 1)
                continue
            raise ParseError("지원하지 않거나 잘못된 클래스 문법: " + t[:65], idx + 1, "unsupported")
        if in_block:
            raise ParseError("클래스 블록을 닫는 }가 없습니다", len(lines))
        return doc

    def _parse_sequence(self, lines: list[str], header_index: int) -> DiagramDocument:
        doc = DiagramDocument("sequence")
        by_key: dict[str, Node] = {}
        stack: list[tuple[str, int]] = []
        def ensure(key: str, at: int = -1, label: str | None = None, explicit: bool = False, kind: str = "participant"):
            if key not in by_key:
                n = Node(new_object_id(), key, label or key, kind, width=144, height=54, line_start=at, line_end=at+1 if at>=0 else -1, explicit=explicit)
                by_key[key] = n
                doc.nodes.append(n)
            n = by_key[key]
            if explicit:
                n.explicit = True
                n.line_start = at
                n.line_end = at + 1
                if label:
                    n.label = label
                n.kind = kind
            return n
        for idx in range(header_index + 1, len(lines)):
            t = lines[idx].strip()
            if self._is_ignored(t):
                continue
            m = SEQ_PARTICIPANT.fullmatch(t)
            if m:
                ensure(m[2], idx, m[3], True, m[1].lower())
                continue
            m = SEQ_MESSAGE.fullmatch(t)
            if m:
                left, arrow, right, activation, text = m.groups()
                ensure(left)
                ensure(right)
                doc.edges.append(Edge(new_object_id(), left, right, arrow, text, "message", idx, idx+1, len(doc.edges)))
                continue
            m = SEQ_NOTE.fullmatch(t)
            if m:
                targets = [x.strip() for x in m[2].split(",")]
                if any(not re.fullmatch(r"[A-Za-z_]\w*(?:-\w+)*", x) for x in targets):
                    raise ParseError("노트 대상 참가자 이름이 잘못되었습니다", idx + 1)
                for k in targets: ensure(k)
                doc.decorations.append({"kind": "note", "position": m[1], "targets": targets,
                                        "text": m[3], "line": idx, "order": len(doc.edges)})
                continue
            if re.fullmatch(r"(?:activate|deactivate)\s+[A-Za-z_][\w-]*", t, re.I):
                action, target = t.split()
                ensure(target)
                doc.decorations.append({"kind": action.lower(), "target": target, "line": idx, "order": len(doc.edges)})
                continue
            m = SEQ_BLOCK.fullmatch(t)
            if m:
                stack.append((m[1].lower(), idx))
                doc.decorations.append({"kind": "block_start", "block": m[1].lower(), "text": m[2], "line": idx, "order": len(doc.edges)})
                continue
            if t.lower() == "end":
                if not stack:
                    raise ParseError("대응되는 시퀀스 그룹 시작이 없습니다", idx + 1)
                kind, start = stack.pop()
                doc.decorations.append({"kind": "block_end", "block": kind, "line": idx, "order": len(doc.edges)})
                continue
            m = SEQ_OPTION.fullmatch(t)
            if m and stack:
                doc.decorations.append({"kind": "block_option", "text": t, "line": idx, "order": len(doc.edges)})
                continue
            if t.startswith("autonumber") and t == "autonumber":
                doc.decorations.append({"kind": "autonumber", "line": idx})
                continue
            raise ParseError("지원하지 않거나 잘못된 시퀀스 문법: " + t[:65], idx + 1, "unsupported")
        if stack:
            raise ParseError("시퀀스 그룹을 닫는 end가 없습니다", len(lines))
        return doc

    @staticmethod
    def _preserve_identity(doc: DiagramDocument, previous: DiagramDocument | None):
        if not previous or doc.diagram_type != previous.diagram_type:
            return
        old_nodes = {n.key: n for n in previous.nodes}
        matched_ids: set[str] = set()
        for n in doc.nodes:
            prev = old_nodes.get(n.key)
            if prev is None and n.explicit and n.line_start >= 0:
                # Rename heuristic only if exactly one unmatched old declaration sits on the same line.
                candidates = [p for p in previous.nodes if p.explicit and p.line_start == n.line_start and p.id not in matched_ids]
                if len(candidates) == 1:
                    prev = candidates[0]
            if prev and prev.id not in matched_ids:
                n.id = prev.id
                n.x, n.y = prev.x, prev.y
                matched_ids.add(prev.id)
        old_edges: dict[tuple[str,str,str,str,int], list[Edge]] = {}
        for e in previous.edges:
            sig = (e.source, e.target, e.relation, e.label, e.order)
            old_edges.setdefault(sig, []).append(e)
        for e in doc.edges:
            sig = (e.source, e.target, e.relation, e.label, e.order)
            if old_edges.get(sig):
                e.id = old_edges[sig].pop(0).id

    @staticmethod
    def _initial_layout(doc: DiagramDocument, previous: DiagramDocument | None):
        preserved = {n.id for n in previous.nodes} if previous and previous.diagram_type == doc.diagram_type else set()
        if doc.diagram_type == "class":
            for i, node in enumerate(doc.nodes):
                node.height = max(72, 52 + len(node.members) * 22)
                if node.id not in preserved:
                    node.x = float((i % 3) * 260 + 40)
                    node.y = float((i // 3) * 210 + 42)
        else:
            for i, node in enumerate(doc.nodes):
                if node.id not in preserved:
                    node.x = float(i * 220 + 75)
                    node.y = 36.0
