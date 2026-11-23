"""코드 편집 헬퍼. 담당: 심현보 (B6).

캔버스 복사/붙여넣기(F12)에서 쓴다.
- 복사: `class_block(code, "User")` -> User를 정의하는 코드 줄들
- 붙여넣기: `append_class(code, block, "User")` -> 이름이 겹치면 `User2`,
  `User3`처럼 바꿔 코드 끝에 붙인 새 코드

- 시퀀스 참여자 드래그: `reorder_participants(code, ["B", "A"])` -> 참여자
  선언 순서를 바꾼 새 코드

코드 위치는 `parse()` 결과의 `source`를 쓰고, 직접 다시 파싱하지 않는다.
"""

from __future__ import annotations

import re

from umlparser import parse as parse_document
from umlparser.class_parser import parse
from umlparser.model import ClassNode
from umlparser.sequence import SequenceDocument

_ID_RE = re.compile(r"^\w+$")


def _declared_class(code: str, class_id: str | None = None) -> ClassNode | None:
    """`class_id`(없으면 첫 번째)인, 코드에 직접 선언된 클래스를 찾는다."""
    declarations = set(
        re.findall(r"(?m)^[ \t]*(?:class|<<[^<>\n]+>>)[ \t]+(\w+)", code)
    )
    for node in parse(code).classes:
        if node.implicit or node.id not in declarations:
            continue
        if class_id is None or node.id == class_id:
            return node
    return None


def class_block(code: str, class_id: str) -> str:
    """클래스를 정의하는 코드 줄들을 원래 순서대로 돌려준다 (복사용).

    선언 블록(`class X { ... }`)과 블록 밖의 `X : 멤버`,
    `<<interface>> X` 줄을 모두 포함한다. 관계 줄은 포함하지 않는다.
    관계에서만 쓰인(implicit) 클래스는 독립된 클래스 선언으로 복사한다.
    클래스가 없거나 원문에 오류가 있으면 빈 문자열을 돌려준다.
    """
    diagram = parse(code)
    if diagram.errors:
        return ""
    for candidate in diagram.classes:
        if candidate.id == class_id and candidate.implicit:
            return f"class {candidate.id}"
    node = _declared_class(code, class_id)
    if node is None:
        return ""

    lines = code.splitlines()
    numbers = set(range(node.source.line, node.source.end_line + 1))
    name = re.escape(class_id)
    outside = re.compile(rf"^\s*(?:{name}\s*:|<<[^<>]*>>\s*{name}\s*$)")
    numbers.update(i for i, text in enumerate(lines, start=1) if outside.match(text))
    return "\n".join(lines[n - 1] for n in sorted(numbers) if 1 <= n <= len(lines))


def unique_class_id(code: str, base_id: str) -> str:
    """코드에 없는 클래스 id를 만든다. `User`가 있으면 `User2`, `User3`, ..."""
    taken = {node.id for node in parse(code).classes}
    if base_id not in taken:
        return base_id
    stem = re.sub(r"\d+$", "", base_id) or base_id
    number = 2
    while f"{stem}{number}" in taken:
        number += 1
    return f"{stem}{number}"


def _rename_declarations(block: str, old_id: str, new_id: str) -> str:
    """선언 위치의 클래스 이름만 바꾼다. 멤버 타입 등 다른 곳은 그대로 둔다."""
    old = re.escape(old_id)
    patterns = [
        re.compile(rf"^(\s*class\s+){old}(?!\w)"),
        re.compile(rf"^(\s*<<[^<>]*>>\s*){old}(?!\w)"),
        re.compile(rf"^(\s*){old}(?=\s*:)"),
    ]
    renamed: list[str] = []
    for line in block.splitlines(keepends=True):
        for pattern in patterns:
            line = pattern.sub(lambda m: m.group(1) + new_id, line, count=1)
        renamed.append(line)
    return "".join(renamed)


def append_class(code: str, block: str, new_id: str) -> str:
    """`block`의 클래스 이름을 `new_id`로 바꿔 코드 끝에 붙인다 (붙여넣기용).

    `new_id`가 이미 있으면 `User2`, `User3`처럼 겹치지 않는 이름을 쓴다.
    `new_id`가 이름으로 쓸 수 없는 글자면 block의 원래 이름을 기준으로 한다.
    `block`에 선언된 클래스가 없으면(클립보드 내용이 잘못됨) 코드를 그대로 돌려준다.
    """
    source = _declared_class(block)
    if source is None:
        return code

    base_id = new_id if _ID_RE.match(new_id) else source.id
    target_id = unique_class_id(code, base_id)
    body = _rename_declarations(block, source.id, target_id).strip("\n")

    if not code.strip():
        return f"{body}\n"
    separator = "" if code.endswith("\n") else "\n"
    return f"{code}{separator}{body}\n"


def _is_header(line: str) -> bool:
    return line.partition("%%")[0].strip() == "sequenceDiagram"


def reorder_participants(code: str, order: list[str]) -> str:
    """시퀀스 참여자 선언을 order 순서로 다시 쓴 코드.

    바꿀 수 없으면 code를 그대로 돌려준다.
    """
    document = parse_document(code)
    if not isinstance(document, SequenceDocument) or document.type != "sequence":
        return code
    if document.errors:
        return code
    participants = document.sequence.participants
    current = list(participants)
    if len(order) != len(set(order)) or set(order) != set(current) or order == current:
        return code

    lines = code.splitlines(keepends=True)
    header = next((i for i, line in enumerate(lines) if _is_header(line)), None)
    if header is None:
        return code
    newline = next(
        (
            "\r\n" if line.endswith("\r\n") else "\n"
            for line in lines
            if line.endswith("\n")
        ),
        "\n",
    )
    first_content = next(
        (
            line
            for line in lines[header + 1 :]
            if line.strip() and not line.strip().startswith("%%")
        ),
        None,
    )
    indent = "    "
    if first_content is not None:
        indent = first_content[: len(first_content) - len(first_content.lstrip())]

    # 선언 줄은 원래 글자 그대로 꺼내고, 암시적 참여자는 새 선언 줄을 만든다.
    declared: dict[str, str] = {}
    for participant in participants.values():
        if participant.implicit:
            continue
        index = participant.line - 1
        if not header < index < len(lines):
            return code
        declared[participant.id] = lines[index]
    removed = {participants[name].line - 1 for name in declared}

    block: list[str] = []
    for name in order:
        text = declared.get(name)
        if text is None:
            text = f"{indent}participant {name}{newline}"
        elif not text.endswith(("\n", "\r")):
            text += newline
        block.append(text)
    rest = [line for i, line in enumerate(lines) if i not in removed]
    result = "".join(rest[: header + 1] + block + rest[header + 1 :])

    # 다시 읽어 순서와 표시 이름이 의도대로가 아니면 원문을 유지한다.
    check = parse_document(result)
    if (
        not isinstance(check, SequenceDocument)
        or check.errors
        or list(check.sequence.participants) != order
        or any(
            (p.label, p.kind) != (participants[p.id].label, participants[p.id].kind)
            for p in check.sequence.participants.values()
        )
    ):
        return code
    return result
