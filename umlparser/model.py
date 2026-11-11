"""공통 모델 dataclass와 to_dict/from_dict. 담당: 심현보 (B1).

필드는 docs/00-common.md 5.1과 class-model.md를 따른다.
Python 이름은 snake_case(`from_`, `layout_key`), JSON 키는 class-model.md
이름(`from`, `layoutKey`)을 쓰고 `to_dict()`/`from_dict()`로 오간다.

`from_dict()`는 외부 데이터(파일 등)를 받으므로, 모양이 잘못된 입력은
`ModelError`로 알린다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, get_args

ClassKind = Literal["class", "abstract", "interface", "enum"]
RelationKind = Literal[
    "inheritance",
    "realization",
    "association",
    "aggregation",
    "composition",
    "dependency",
]
Visibility = Literal["+", "-", "#", "~", ""]

CLASS_KINDS: tuple[str, ...] = get_args(ClassKind)
RELATION_KINDS: tuple[str, ...] = get_args(RelationKind)
VISIBILITIES: tuple[str, ...] = get_args(Visibility)

MODEL_VERSION = 1


class ModelError(ValueError):
    """`from_dict()`에 들어온 데이터의 모양이 class-model.md와 다를 때."""


# ---------------------------------------------------------------------------
# from_dict 입력 검사 헬퍼
# ---------------------------------------------------------------------------


def _require_dict(data: Any, where: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ModelError(f"{where}: 객체(dict)여야 합니다.")
    return data


def _get_str(
    data: dict[str, Any], key: str, where: str, default: str | None = None
) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ModelError(f"{where}.{key}: 문자열이어야 합니다.")
    return value


def _get_opt_str(data: dict[str, Any], key: str, where: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise ModelError(f"{where}.{key}: 문자열 또는 null이어야 합니다.")
    return value


def _get_bool(
    data: dict[str, Any], key: str, where: str, default: bool = False
) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ModelError(f"{where}.{key}: true/false여야 합니다.")
    return value


def _get_int(
    data: dict[str, Any], key: str, where: str, default: int | None = None
) -> int:
    value = data.get(key, default)
    # bool은 int의 하위 타입이므로 따로 막는다.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelError(f"{where}.{key}: 정수여야 합니다.")
    return value


def _get_list(data: dict[str, Any], key: str, where: str) -> list[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ModelError(f"{where}.{key}: 배열이어야 합니다.")
    return value


def _get_str_list(data: dict[str, Any], key: str, where: str) -> list[str]:
    items = _get_list(data, key, where)
    if not all(isinstance(item, str) for item in items):
        raise ModelError(f"{where}.{key}: 문자열 배열이어야 합니다.")
    return list(items)


def _get_choice(
    data: dict[str, Any], key: str, where: str, choices: tuple[str, ...], default: str
) -> str:
    value = _get_str(data, key, where, default)
    if value not in choices:
        raise ModelError(
            f"{where}.{key}: {choices} 중 하나여야 합니다. (받은 값: {value!r})"
        )
    return value


def _get_source(data: dict[str, Any], where: str) -> Source:
    if "source" not in data:
        return Source()
    return Source.from_dict(data["source"], f"{where}.source")


# ---------------------------------------------------------------------------
# 모델
# ---------------------------------------------------------------------------


@dataclass
class Source:
    """코드 위치. 줄 번호는 1부터 센다."""

    line: int = 1
    end_line: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"line": self.line, "endLine": self.end_line}

    @classmethod
    def from_dict(cls, data: Any, where: str = "source") -> Source:
        d = _require_dict(data, where)
        line = _get_int(d, "line", where)
        return cls(line=line, end_line=_get_int(d, "endLine", where, line))


@dataclass
class Param:
    """메서드 파라미터. 타입이 없으면 `type`은 None."""

    name: str
    type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type}

    @classmethod
    def from_dict(cls, data: Any, where: str = "param") -> Param:
        d = _require_dict(data, where)
        return cls(name=_get_str(d, "name", where), type=_get_opt_str(d, "type", where))


@dataclass
class Attribute:
    name: str
    type: str | None = None
    visibility: Visibility = ""
    is_static: bool = False
    source: Source = field(default_factory=Source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "visibility": self.visibility,
            "isStatic": self.is_static,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Any, where: str = "attribute") -> Attribute:
        d = _require_dict(data, where)
        return cls(
            name=_get_str(d, "name", where),
            type=_get_opt_str(d, "type", where),
            visibility=_get_choice(d, "visibility", where, VISIBILITIES, ""),
            is_static=_get_bool(d, "isStatic", where),
            source=_get_source(d, where),
        )


@dataclass
class Method:
    name: str
    returns: str | None = None
    params: list[Param] = field(default_factory=list)
    visibility: Visibility = ""
    is_static: bool = False
    is_abstract: bool = False
    source: Source = field(default_factory=Source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "returns": self.returns,
            "params": [p.to_dict() for p in self.params],
            "visibility": self.visibility,
            "isStatic": self.is_static,
            "isAbstract": self.is_abstract,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Any, where: str = "method") -> Method:
        d = _require_dict(data, where)
        return cls(
            name=_get_str(d, "name", where),
            returns=_get_opt_str(d, "returns", where),
            params=[
                Param.from_dict(p, f"{where}.params[{i}]")
                for i, p in enumerate(_get_list(d, "params", where))
            ],
            visibility=_get_choice(d, "visibility", where, VISIBILITIES, ""),
            is_static=_get_bool(d, "isStatic", where),
            is_abstract=_get_bool(d, "isAbstract", where),
            source=_get_source(d, where),
        )


@dataclass
class ClassNode:
    """클래스/인터페이스/추상/열거형 하나."""

    id: str
    name: str
    kind: ClassKind = "class"
    generics: list[str] = field(default_factory=list)
    attributes: list[Attribute] = field(default_factory=list)
    methods: list[Method] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    implicit: bool = False
    source: Source = field(default_factory=Source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "generics": list(self.generics),
            "attributes": [a.to_dict() for a in self.attributes],
            "methods": [m.to_dict() for m in self.methods],
            "values": list(self.values),
            "implicit": self.implicit,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Any, where: str = "class") -> ClassNode:
        d = _require_dict(data, where)
        class_id = _get_str(d, "id", where)
        return cls(
            id=class_id,
            name=_get_str(d, "name", where, class_id),
            kind=_get_choice(d, "kind", where, CLASS_KINDS, "class"),
            generics=_get_str_list(d, "generics", where),
            attributes=[
                Attribute.from_dict(a, f"{where}.attributes[{i}]")
                for i, a in enumerate(_get_list(d, "attributes", where))
            ],
            methods=[
                Method.from_dict(m, f"{where}.methods[{i}]")
                for i, m in enumerate(_get_list(d, "methods", where))
            ],
            values=_get_str_list(d, "values", where),
            implicit=_get_bool(d, "implicit", where),
            source=_get_source(d, where),
        )


@dataclass
class Relation:
    """관계선 하나. 상속/구현은 from_ = 자식, to = 부모로 정규화한다."""

    id: str
    from_: str
    to: str
    kind: RelationKind
    directed: bool = False
    from_multiplicity: str | None = None
    to_multiplicity: str | None = None
    label: str | None = None
    layout_key: str = ""
    source: Source = field(default_factory=Source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from": self.from_,
            "to": self.to,
            "kind": self.kind,
            "directed": self.directed,
            "fromMultiplicity": self.from_multiplicity,
            "toMultiplicity": self.to_multiplicity,
            "label": self.label,
            "layoutKey": self.layout_key,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Any, where: str = "relation") -> Relation:
        d = _require_dict(data, where)
        from_ = _get_str(d, "from", where)
        to = _get_str(d, "to", where)
        return cls(
            id=_get_str(d, "id", where),
            from_=from_,
            to=to,
            kind=_get_choice(d, "kind", where, RELATION_KINDS, ""),
            directed=_get_bool(d, "directed", where),
            from_multiplicity=_get_opt_str(d, "fromMultiplicity", where),
            to_multiplicity=_get_opt_str(d, "toMultiplicity", where),
            label=_get_opt_str(d, "label", where),
            layout_key=_get_str(d, "layoutKey", where, f"{from_}->{to}"),
            source=_get_source(d, where),
        )


@dataclass
class ParseError:
    """파싱 오류. line·column은 1부터 센다."""

    line: int
    column: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"line": self.line, "column": self.column, "message": self.message}

    @classmethod
    def from_dict(cls, data: Any, where: str = "error") -> ParseError:
        d = _require_dict(data, where)
        return cls(
            line=_get_int(d, "line", where),
            column=_get_int(d, "column", where, 1),
            message=_get_str(d, "message", where),
        )


@dataclass
class ClassDiagram:
    """클래스 다이어그램 최상위 모델. 오류가 있어도 파싱된 부분은 채워진다."""

    version: int = MODEL_VERSION
    type: str = "class"
    classes: list[ClassNode] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "type": self.type,
            "classes": [c.to_dict() for c in self.classes],
            "relations": [r.to_dict() for r in self.relations],
            "errors": [e.to_dict() for e in self.errors],
        }

    @classmethod
    def from_dict(cls, data: Any) -> ClassDiagram:
        where = "diagram"
        d = _require_dict(data, where)
        version = _get_int(d, "version", where, MODEL_VERSION)
        if version != MODEL_VERSION:
            raise ModelError(
                f"{where}.version: 지원하지 않는 버전입니다. (받은 값: {version})"
            )
        diagram_type = _get_str(d, "type", where, "class")
        if diagram_type != "class":
            raise ModelError(
                f"{where}.type: 'class'여야 합니다. (받은 값: {diagram_type!r})"
            )
        return cls(
            version=version,
            type=diagram_type,
            classes=[
                ClassNode.from_dict(c, f"classes[{i}]")
                for i, c in enumerate(_get_list(d, "classes", where))
            ],
            relations=[
                Relation.from_dict(r, f"relations[{i}]")
                for i, r in enumerate(_get_list(d, "relations", where))
            ],
            errors=[
                ParseError.from_dict(e, f"errors[{i}]")
                for i, e in enumerate(_get_list(d, "errors", where))
            ],
        )
