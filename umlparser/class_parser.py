"""클래스 다이어그램 파서. 담당: 심현보 (B2~B5).

Mermaid classDiagram 문법을 읽어 `ClassDiagram` 모델로 바꾼다.

지원하는 문법
- 머리말 `classDiagram` (생략 가능, 쓰면 첫 문장이어야 한다)
- `class X`, `class X { ... }`, 제네릭 `class X~T~`, 표시 이름 `class X["이름"]`
- `<<interface>>`, `<<abstract>>`, `<<enumeration>>` (블록 안 또는 `<<interface>> X`)
- 멤버: 블록 안의 줄 또는 `X : 멤버`
  - 가시성 `+ - # ~`, 정적 `$`, 추상 `*`
  - 속성 `+String name` 또는 `+name: String`
  - 메서드 `+find(int id, strict) User` 또는 `+find(id: int): User`
  - 열거형(`enum`)의 괄호 없는 멤버는 값(`values`)이 된다
- 관계 6종과 양방향 표기, 다중성 `"1"`, 라벨 `: places`
- `%%` 주석(줄 전체 또는 줄 끝), `direction`·`note`·`style` 등 그림과 무관한
  문장은 무시

관계 정규화
- 화살표 머리(삼각형·마름모·화살촉)가 달린 쪽이 항상 `to`가 된다.
  따라서 상속/구현은 `from` = 자식, `to` = 부모이고,
  합성/집합은 `to` = 전체(마름모 쪽)이다.
- 머리가 없는 `--`, `..`는 쓴 순서대로 `from`, `to`를 정한다.
- `directed`는 연관/의존 선에 화살촉이 있는지만 뜻한다 (`-->`, `..>`는 True,
  `--`, `..`는 False). 상속·구현·합성·집합은 모양이 정해져 있어 항상 False다.

오류 처리
- 잘못된 줄은 건너뛰고 `errors`에 `{line, column, message}`(1부터 셈)를 더한다.
- `parse()`는 어떤 입력에도 예외를 밖으로 던지지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import cast

from umlparser.model import (
    Attribute,
    ClassDiagram,
    ClassKind,
    ClassNode,
    Method,
    Param,
    ParseError,
    Relation,
    RelationKind,
    Source,
    Visibility,
)

# ---------------------------------------------------------------------------
# 문법 표
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^classDiagram(?:-v2)?$")
_IGNORED_RE = re.compile(
    r"^(?:(?:direction|note|click|link|callback|style|classDef|cssClass)\b"
    r"|(?:accTitle|accDescr|title)\s*:)"
)
_CLASS_RE = re.compile(
    r"^class\s+(?P<id>\w+)"
    r"(?:\s*~(?P<generics>[^{\[]*)~)?"
    r'(?:\s*\["(?P<label>[^"]*)"\])?'
    r"(?:\s*:::\s*\w+)?"
    r"\s*(?P<open>\{)?\s*(?P<rest>.*)$"
)
_ANNOTATION_RE = re.compile(r"^<<\s*(?P<name>[^<>]*?)\s*>>\s*(?P<id>\w+)?\s*$")
_MEMBER_LINE_RE = re.compile(r"^(?P<id>\w+)\s*:\s*(?P<member>.*)$")
_RELATION_RE = re.compile(
    r'^(?P<a>\w+)\s*(?:"(?P<am>[^"]*)"\s*)?'
    r"(?P<arrow>o?[<>|*.\-]{2,}o?)"
    r'\s*(?:"(?P<bm>[^"]*)"\s*)?(?P<b>\w+)\s*(?::\s*(?P<label>.*?))?\s*$'
)
_METHOD_RE = re.compile(
    r"^(?P<name>\w+)\s*\((?P<params>.*)\)(?P<cls>[$*]?)"
    r"\s*(?::\s*)?(?P<ret>.*?)\s*(?P<cls2>[$*]?)$"
)
_NAME_RE = re.compile(r"^\w+$")

_ANNOTATION_KINDS: dict[str, ClassKind] = {
    "interface": "interface",
    "abstract": "abstract",
    "enumeration": "enum",
    "enum": "enum",
}

# 화살표 -> (관계 종류, 머리가 달린 쪽). 머리가 없으면 None.
_ARROWS: dict[str, tuple[RelationKind, str | None]] = {
    "<|--": ("inheritance", "left"),
    "--|>": ("inheritance", "right"),
    "<|..": ("realization", "left"),
    "..|>": ("realization", "right"),
    "*--": ("composition", "left"),
    "--*": ("composition", "right"),
    "o--": ("aggregation", "left"),
    "--o": ("aggregation", "right"),
    "<--": ("association", "left"),
    "-->": ("association", "right"),
    "--": ("association", None),
    "<..": ("dependency", "left"),
    "..>": ("dependency", "right"),
    "..": ("dependency", None),
}

# 화살촉 유무로 방향을 표시하는 관계. 나머지는 머리 모양이 종류 자체를 뜻한다.
_ARROW_KINDS: tuple[RelationKind, ...] = ("association", "dependency")

_VISIBILITY_CHARS = "+-#~"


# ---------------------------------------------------------------------------
# 내부 자료 구조
# ---------------------------------------------------------------------------


class _LineError(Exception):
    """한 줄을 읽다 만난 문법 오류. `offset`은 줄 안의 0부터 센 위치."""

    def __init__(self, message: str, offset: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.offset = offset


@dataclass
class _Member:
    """나중에 클래스 종류(kind)를 알고 나서 해석할 멤버 한 줄."""

    text: str
    line: int
    column: int


@dataclass
class _ClassDraft:
    node: ClassNode
    declared: bool = False  # `class X` 문장을 만났는지
    members: list[_Member] = field(default_factory=list)


@dataclass
class _Block:
    """열려 있는 `class X {` 블록."""

    draft: _ClassDraft
    line: int
    column: int


@dataclass
class _State:
    classes: dict[str, _ClassDraft] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    layout_counts: dict[str, int] = field(default_factory=dict)
    block: _Block | None = None
    seen_statement: bool = False
    last_line: int = 0

    def error(self, line: int, column: int, message: str) -> None:
        self.errors.append(ParseError(line=line, column=column, message=message))

    def class_draft(self, class_id: str, line: int, implicit: bool) -> _ClassDraft:
        """클래스를 찾거나 만든다. 명시적으로 쓰이면 implicit을 해제한다."""
        draft = self.classes.get(class_id)
        if draft is None:
            draft = _ClassDraft(
                node=ClassNode(
                    id=class_id,
                    name=class_id,
                    implicit=implicit,
                    source=Source(line, line),
                )
            )
            self.classes[class_id] = draft
        elif draft.node.implicit and not implicit:
            draft.node.implicit = False
            draft.node.source = Source(line, line)
        return draft


# ---------------------------------------------------------------------------
# 문자열 도우미
# ---------------------------------------------------------------------------


def _is_word(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _tilde_to_angle(text: str) -> str:
    """Mermaid 제네릭 `List~List~int~~`를 `List<List<int>>`로 바꾼다."""
    out: list[str] = []
    depth = 0
    for i, ch in enumerate(text):
        if ch != "~":
            out.append(ch)
            continue
        prev = text[i - 1] if i > 0 else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if depth == 0 or (_is_word(prev) and _is_word(nxt)):
            out.append("<")
            depth += 1
        else:
            out.append(">")
            depth -= 1
    return "".join(out)


def _split_top_level(text: str) -> list[str]:
    """괄호 밖의 쉼표로만 나눈다. `Map<K, V> m, int n` -> 두 조각."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in text:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts]


def _split_visibility(text: str) -> tuple[Visibility, str]:
    if text and text[0] in _VISIBILITY_CHARS:
        return cast(Visibility, text[0]), text[1:].lstrip()
    return "", text


def _blank_to_none(text: str | None) -> str | None:
    if text is None:
        return None
    return text.strip() or None


# ---------------------------------------------------------------------------
# 멤버 해석
# ---------------------------------------------------------------------------


def _parse_param(text: str) -> Param:
    if ":" in text:
        name, type_ = (s.strip() for s in text.split(":", 1))
    else:
        tokens = text.split()
        name = tokens[-1] if tokens else ""
        type_ = " ".join(tokens[:-1])
    if not _NAME_RE.match(name):
        raise _LineError(f"파라미터 이름이 올바르지 않습니다: {text!r}")
    return Param(name=name, type=type_ or None)


def _parse_method(visibility: Visibility, text: str, source: Source) -> Method:
    match = _METHOD_RE.match(_tilde_to_angle(text))
    if match is None:
        raise _LineError("메서드 형식이 올바르지 않습니다. 이름과 괄호를 확인하세요.")
    params_text = match["params"].strip()
    params: list[Param] = []
    if params_text:
        pieces = _split_top_level(params_text)
        if any(not piece for piece in pieces):
            raise _LineError("파라미터 목록에 빈 칸이 있습니다.")
        params = [_parse_param(piece) for piece in pieces]
    classifiers = match["cls"] + match["cls2"]
    return Method(
        name=match["name"],
        returns=match["ret"] or None,
        params=params,
        visibility=visibility,
        is_static="$" in classifiers,
        is_abstract="*" in classifiers,
        source=source,
    )


def _parse_attribute(visibility: Visibility, text: str, source: Source) -> Attribute:
    is_static = False
    while text and text[-1] in "$*":
        is_static = is_static or text[-1] == "$"
        text = text[:-1].rstrip()
    text = _tilde_to_angle(text)
    if ":" in text:
        name, type_ = (s.strip() for s in text.split(":", 1))
    else:
        tokens = text.split()
        name = tokens[-1] if tokens else ""
        type_ = " ".join(tokens[:-1])
    if not _NAME_RE.match(name):
        raise _LineError(f"속성 이름이 올바르지 않습니다: {text!r}")
    return Attribute(
        name=name,
        type=type_ or None,
        visibility=visibility,
        is_static=is_static,
        source=source,
    )


def _apply_members(draft: _ClassDraft, state: _State) -> None:
    """모아 둔 멤버 줄을 종류에 맞게 속성·메서드·열거값으로 바꾼다."""
    node = draft.node
    for member in draft.members:
        source = Source(member.line, member.line)
        visibility, text = _split_visibility(member.text.strip())
        try:
            if "(" in text:
                method = _parse_method(visibility, text, source)
                # 인터페이스의 메서드는 `*`를 적지 않아도 추상이다.
                method.is_abstract = method.is_abstract or node.kind == "interface"
                node.methods.append(method)
            elif node.kind == "enum":
                if not text:
                    raise _LineError("열거값이 비어 있습니다.")
                node.values.append(text)
            else:
                node.attributes.append(_parse_attribute(visibility, text, source))
        except _LineError as exc:
            state.error(member.line, member.column + exc.offset, exc.message)


# ---------------------------------------------------------------------------
# 문장 처리
# ---------------------------------------------------------------------------


def _set_kind(draft: _ClassDraft, annotation: str) -> None:
    kind = _ANNOTATION_KINDS.get(annotation.lower())
    if kind is None:
        raise _LineError(
            f"알 수 없는 스테레오타입입니다: <<{annotation}>> "
            "(interface, abstract, enumeration 중 하나)",
            2,
        )
    draft.node.kind = kind


def _close_block(state: _State, end_line: int) -> None:
    if state.block is not None:
        node = state.block.draft.node
        node.source = Source(node.source.line, max(node.source.line, end_line))
        state.block = None


def _report_unclosed(state: _State, end_line: int) -> None:
    block = state.block
    if block is None:
        return
    state.error(
        block.line,
        block.column,
        f"'{block.draft.node.id}' 클래스 블록을 닫는 '}}'가 없습니다.",
    )
    _close_block(state, end_line)


def _handle_class(state: _State, text: str, line: int, indent: int) -> None:
    match = _CLASS_RE.match(text)
    if match is None:
        raise _LineError("클래스 선언 형식이 올바르지 않습니다. 예: class User {", 0)
    draft = state.class_draft(match["id"], line, implicit=False)
    node = draft.node
    if not draft.declared:
        draft.declared = True
        node.source = Source(line, line)
    if match["generics"] is not None:
        generics = _split_top_level(_tilde_to_angle(match["generics"]))
        if any(not g for g in generics):
            raise _LineError(
                "제네릭 타입 이름이 비어 있습니다.", match.start("generics")
            )
        node.generics = generics
    if match["label"] is not None:
        node.name = match["label"]

    rest = match["rest"]
    if match["open"] is None:
        if rest:
            raise _LineError(
                "클래스 선언 뒤에 알 수 없는 내용이 있습니다.", match.start("rest")
            )
        return
    if rest == "}":
        node.source = Source(node.source.line, line)
        return
    state.block = _Block(
        draft=draft, line=line, column=indent + match.start("open") + 1
    )
    if rest:
        raise _LineError(
            "'{' 뒤에서 줄을 바꾼 다음 멤버를 적어야 합니다.", match.start("rest")
        )


def _handle_relation(state: _State, match: re.Match[str], line: int) -> None:
    arrow = match["arrow"]
    if arrow not in _ARROWS:
        raise _LineError(f"알 수 없는 화살표입니다: {arrow}", match.start("arrow"))
    kind, head = _ARROWS[arrow]
    a, b = match["a"], match["b"]
    am, bm = match["am"], match["bm"]
    if head == "left":
        from_, to, from_mult, to_mult = b, a, bm, am
    else:
        from_, to, from_mult, to_mult = a, b, am, bm

    for class_id in (a, b):
        state.class_draft(class_id, line, implicit=True)

    base_key = f"{from_}->{to}"
    count = state.layout_counts.get(base_key, 0) + 1
    state.layout_counts[base_key] = count
    layout_key = base_key if count == 1 else f"{base_key}#{count}"

    label = match["label"]
    state.relations.append(
        Relation(
            id=f"r{len(state.relations) + 1}",
            from_=from_,
            to=to,
            kind=kind,
            directed=kind in _ARROW_KINDS and head is not None,
            from_multiplicity=_blank_to_none(from_mult),
            to_multiplicity=_blank_to_none(to_mult),
            label=_blank_to_none(label),
            layout_key=layout_key,
            source=Source(line, line),
        )
    )


def _handle_block_line(state: _State, text: str, line: int, indent: int) -> bool:
    """블록 안의 줄을 처리한다. 블록 밖 문장으로 다시 읽어야 하면 False."""
    block = state.block
    if block is None:
        return False
    if text == "}":
        _close_block(state, line)
        return True
    if text.startswith("class ") or _known_relation(text):
        # '}'를 빠뜨린 것으로 보고 블록을 닫은 뒤 이 줄을 다시 읽는다.
        _report_unclosed(state, state.last_line)
        return False
    annotation = _ANNOTATION_RE.match(text)
    if annotation is not None:
        if annotation["id"] not in (None, block.draft.node.id):
            raise _LineError("블록 안의 스테레오타입은 그 클래스에만 쓸 수 있습니다.")
        _set_kind(block.draft, annotation["name"])
        return True
    block.draft.members.append(_Member(text=text, line=line, column=indent + 1))
    return True


def _known_relation(text: str) -> bool:
    match = _RELATION_RE.match(text)
    return match is not None and match["arrow"] in _ARROWS


def _handle_statement(state: _State, text: str, line: int, indent: int) -> None:
    if _HEADER_RE.match(text):
        if state.seen_statement:
            raise _LineError("classDiagram은 첫 줄에만 쓸 수 있습니다.")
        state.seen_statement = True
        return
    state.seen_statement = True

    if _IGNORED_RE.match(text):
        return
    if text.startswith("class ") or text == "class":
        _handle_class(state, text, line, indent)
        return
    annotation = _ANNOTATION_RE.match(text)
    if annotation is not None:
        if annotation["id"] is None:
            raise _LineError(
                "스테레오타입 뒤에 클래스 이름을 적어야 합니다. 예: <<interface>> Shape"
            )
        draft = state.class_draft(annotation["id"], line, implicit=False)
        _set_kind(draft, annotation["name"])
        return
    relation = _RELATION_RE.match(text)
    if relation is not None:
        _handle_relation(state, relation, line)
        return
    member = _MEMBER_LINE_RE.match(text)
    if member is not None:
        if not member["member"].strip():
            raise _LineError("':' 뒤에 멤버를 적어야 합니다.", member.end("id"))
        draft = state.class_draft(member["id"], line, implicit=False)
        draft.members.append(
            _Member(
                text=member["member"],
                line=line,
                column=indent + member.start("member") + 1,
            )
        )
        return
    if text == "}":
        raise _LineError("짝이 맞지 않는 '}'입니다.")
    raise _LineError("알 수 없는 문장입니다.")


def _strip_comment(raw: str) -> str:
    """`%%`부터 줄 끝까지를 지운다. `"..."` 따옴표 안의 `%%`는 남긴다."""
    in_quote = False
    for i, ch in enumerate(raw):
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote and raw.startswith("%%", i):
            return raw[:i]
    return raw


def _handle_line(state: _State, raw: str, line: int) -> None:
    raw = _strip_comment(raw)
    text = raw.strip()
    if not text:
        return
    indent = len(raw) - len(raw.lstrip())
    try:
        if state.block is not None and _handle_block_line(state, text, line, indent):
            return
        _handle_statement(state, text, line, indent)
    except _LineError as exc:
        state.error(line, indent + exc.offset + 1, exc.message)
    finally:
        state.last_line = line


# ---------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------


def parse(code: str) -> ClassDiagram:
    """Mermaid classDiagram 코드를 모델로 바꾼다. 예외를 던지지 않는다."""
    if not isinstance(code, str):
        return ClassDiagram(errors=[ParseError(1, 1, "코드는 문자열이어야 합니다.")])

    state = _State()
    for line, raw in enumerate(code.splitlines(), start=1):
        try:
            _handle_line(state, raw, line)
        except Exception:  # noqa: BLE001 - 파서는 예외를 밖으로 내보내지 않는다.
            state.error(line, 1, "이 줄을 읽는 중 알 수 없는 오류가 발생했습니다.")
    _report_unclosed(state, state.last_line)

    for draft in state.classes.values():
        _apply_members(draft, state)

    state.errors.sort(key=lambda e: (e.line, e.column))
    return ClassDiagram(
        classes=[draft.node for draft in state.classes.values()],
        relations=state.relations,
        errors=state.errors,
    )
