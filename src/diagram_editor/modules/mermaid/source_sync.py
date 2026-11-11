"""Minimal line-oriented source patches with fail-closed safety checks."""
from __future__ import annotations
import re
from diagram_editor.core.domain.models import DiagramDocument, Edge, Node
from diagram_editor.modules.mermaid.parser import SubsetMermaidParser, ParseError


class SourceSyncError(ValueError):
    pass


def _lines(source: str):
    return source.splitlines(keepends=True)


def _unique_key(name: str, used: set[str]) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]", "_", name).strip("_-") or "Class"
    if not re.match(r"[A-Za-z_]", name):
        name = "N_" + name
    candidate = name
    i = 2
    while candidate in used:
        candidate = f"{name}_{i}"
        i += 1
    used.add(candidate)
    return candidate


class SourceSync:
    def __init__(self, parser: SubsetMermaidParser):
        self.parser = parser

    def _verify(self, text: str, before: DiagramDocument) -> str:
        try:
            new = self.parser.parse(text, before)
        except ParseError as e:
            raise SourceSyncError(f"패치 후 문법 확인 실패: {e}") from e
        if new.diagram_type != before.diagram_type:
            raise SourceSyncError("다이어그램 유형 변경은 지원하지 않습니다")
        return text

    def delete(self, source: str, doc: DiagramDocument, selected_ids: set[str]) -> str:
        selected_nodes = [n for n in doc.nodes if n.id in selected_ids]
        selected_edges = [e for e in doc.edges if e.id in selected_ids]
        if not selected_nodes and not selected_edges:
            raise SourceSyncError("선택한 객체가 없습니다")
        removed_nodes = {n.key for n in selected_nodes}
        remove: set[int] = set()
        source_lines = source.splitlines()
        if doc.diagram_type == "class":
            # Only remove the lines that *belong* to the selected class;
            # unrelated declarations, comments and their order remain intact.
            for node in selected_nodes:
                in_body = False
                for i, raw in enumerate(source_lines):
                    t = raw.strip()
                    if in_body:
                        remove.add(i)
                        if t == "}":
                            in_body = False
                        continue
                    if re.fullmatch(r"class\s+" + re.escape(node.key) + r"(?:\s*\[.*\])?\s*\{?", t):
                        remove.add(i)
                        in_body = t.endswith("{")
                    elif re.match(r"^" + re.escape(node.key) + r"\s*:", t):
                        remove.add(i)
            for edge in doc.edges:
                if edge.id in selected_ids or edge.source in removed_nodes or edge.target in removed_nodes:
                    if edge.line_start < 0:
                        raise SourceSyncError("관계의 소스 위치를 찾을 수 없습니다")
                    remove.add(edge.line_start)
        else:
            # A participant cannot be deleted while a message refers to it,
            # unless that message is also explicitly selected.
            to_remove_edges = {e.id for e in selected_edges}
            for node in selected_nodes:
                if any((e.source == node.key or e.target == node.key) and e.id not in to_remove_edges for e in doc.edges):
                    raise SourceSyncError("참가자를 삭제하기 전에 연결된 메시지를 모두 선택해야 합니다")
                if not node.explicit:
                    raise SourceSyncError("암묵적으로 선언된 참가자는 원문에서 먼저 명시적으로 선언해야 삭제할 수 있습니다")
                remove.add(node.line_start)
            for e in selected_edges:
                if e.line_start < 0:
                    raise SourceSyncError("메시지 원문 위치를 찾을 수 없습니다")
                remove.add(e.line_start)
        if not remove:
            raise SourceSyncError("삭제 가능한 소스 범위가 없습니다")
        lines = _lines(source)
        text = "".join(ln for i, ln in enumerate(lines) if i not in remove)
        return self._verify(text, doc)

    def add_node(self, source: str, doc: DiagramDocument, requested: str) -> str:
        used = {n.key for n in doc.nodes}
        key = _unique_key(requested, used)
        if doc.diagram_type == "class":
            addition = f"class {key}\n"
        else:
            addition = f"participant {key}\n"
        prefix = "" if source.endswith("\n") or not source else "\n"
        return self._verify(source + prefix + addition, doc)

    def paste(self, source: str, doc: DiagramDocument, clip: dict) -> str:
        if clip.get("diagram_type") != doc.diagram_type:
            raise SourceSyncError("다른 유형의 다이어그램 객체는 붙여넣을 수 없습니다")
        used = {n.key for n in doc.nodes}
        copied_nodes = clip.get("nodes", [])
        copied_edges = clip.get("edges", [])
        if not copied_nodes and not copied_edges:
            raise SourceSyncError("클립보드가 비어 있습니다")
        map_keys: dict[str, str] = {}
        out: list[str] = []
        if doc.diagram_type == "class":
            for n in copied_nodes:
                key = _unique_key(n["key"] + "_copy", used)
                map_keys[n["key"]] = key
                members = n.get("members", [])
                if members:
                    out.append(f"class {key} {{\n")
                    out.extend(f"    {member}\n" for member in members)
                    out.append("}\n")
                else:
                    out.append(f"class {key}\n")
            for e in copied_edges:
                a = map_keys.get(e["source"], e["source"])
                b = map_keys.get(e["target"], e["target"])
                if a not in used or b not in used:
                    raise SourceSyncError("붙여넣은 관계가 존재하지 않는 노드를 참조합니다")
                out.append(f"{a} {e['relation']} {b}" + (f" : {e['label']}" if e.get("label") else "") + "\n")
        else:
            for n in copied_nodes:
                key = _unique_key(n["key"] + "_copy", used)
                map_keys[n["key"]] = key
                out.append(f"participant {key}" + (f" as {n['label']}" if n.get("label") and n["label"] != n["key"] else "") + "\n")
            for e in copied_edges:
                a = map_keys.get(e["source"], e["source"])
                b = map_keys.get(e["target"], e["target"])
                if a not in used or b not in used:
                    raise SourceSyncError("붙여넣은 메시지의 참가자가 없습니다")
                out.append(f"{a}{e['relation']}{b}: {e['label']}\n")
        prefix = "" if source.endswith("\n") or not source else "\n"
        return self._verify(source + prefix + "".join(out), doc)

    @staticmethod
    def copy(doc: DiagramDocument, ids: set[str]) -> dict:
        nodes = [n for n in doc.nodes if n.id in ids]
        chosen_node_keys = {n.key for n in nodes}
        # Internal relations of copied node sets are included. Independently
        # selected edges are copied only when their endpoints can be resolved.
        edges = [e for e in doc.edges if e.id in ids or
                 (e.source in chosen_node_keys and e.target in chosen_node_keys)]
        return {
            "diagram_type": doc.diagram_type,
            "nodes": [{"key": n.key, "label": n.label, "kind": n.kind,
                       "members": list(n.members)} for n in nodes],
            "edges": [{"source": e.source, "target": e.target,
                       "relation": e.relation, "label": e.label} for e in edges],
        }
