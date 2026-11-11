"""umlparser.model 의 to_dict() / from_dict() 왕복 테스트."""

import copy
import json
from typing import Any

import pytest

from umlparser.model import (
    CLASS_KINDS,
    RELATION_KINDS,
    VISIBILITIES,
    Attribute,
    ClassDiagram,
    ClassNode,
    Method,
    ModelError,
    Param,
    ParseError,
    Relation,
    Source,
)


def round_trip(diagram: ClassDiagram) -> ClassDiagram:
    """모델 → dict → 모델."""
    return ClassDiagram.from_dict(diagram.to_dict())


def full_diagram() -> ClassDiagram:
    """모든 칸을 기본값이 아닌 값으로 채운 다이어그램."""
    return ClassDiagram(
        classes=[
            ClassNode(
                id="Repository",
                name="Repository",
                kind="interface",
                generics=["T", "ID"],
                attributes=[
                    Attribute("count", "int", "-", is_static=True, source=Source(3, 3)),
                ],
                methods=[
                    Method(
                        "findById",
                        "T",
                        [Param("id", "ID"), Param("strict")],
                        "+",
                        is_abstract=True,
                        source=Source(4, 4),
                    ),
                    Method("reset", None, [], "#", is_static=True, source=Source(5, 5)),
                ],
                source=Source(2, 6),
            ),
            ClassNode(
                id="Status",
                name="Status",
                kind="enum",
                values=["ACTIVE", "INACTIVE"],
                source=Source(7, 10),
            ),
            ClassNode(
                id="사용자", name="사용자", kind="abstract", source=Source(11, 11)
            ),
            ClassNode(id="Order", name="Order", implicit=True, source=Source(12, 12)),
        ],
        relations=[
            Relation(
                id="r1",
                from_="사용자",
                to="Order",
                kind="association",
                directed=True,
                from_multiplicity="1",
                to_multiplicity="0..*",
                label="places",
                layout_key="사용자->Order",
                source=Source(12, 12),
            ),
            Relation(
                id="r2",
                from_="사용자",
                to="Order",
                kind="composition",
                layout_key="사용자->Order#2",
                source=Source(13, 13),
            ),
        ],
        errors=[ParseError(14, 5, "알 수 없는 화살표입니다.")],
    )


# ---------------------------------------------------------------- 왕복
def test_empty_diagram_round_trip() -> None:
    d = ClassDiagram()
    assert round_trip(d) == d


def test_full_diagram_round_trip() -> None:
    d = full_diagram()
    assert round_trip(d) == d


def test_round_trip_through_json_text() -> None:
    d = full_diagram()
    text = json.dumps(d.to_dict(), ensure_ascii=False)
    assert ClassDiagram.from_dict(json.loads(text)) == d


def test_two_round_trips_are_stable() -> None:
    d = full_diagram()
    assert round_trip(round_trip(d)) == d


def test_dict_model_dict_round_trip() -> None:
    data = full_diagram().to_dict()
    original = copy.deepcopy(data)
    assert ClassDiagram.from_dict(data).to_dict() == original
    assert data == original  # from_dict()가 입력을 바꾸지 않는다.


@pytest.mark.parametrize("kind", CLASS_KINDS)
def test_every_class_kind_round_trip(kind: Any) -> None:
    d = ClassDiagram(classes=[ClassNode(id="A", name="A", kind=kind)])
    assert round_trip(d) == d


@pytest.mark.parametrize("kind", RELATION_KINDS)
def test_every_relation_kind_round_trip(kind: Any) -> None:
    d = ClassDiagram(relations=[Relation("r1", "A", "B", kind, layout_key="A->B")])
    assert round_trip(d) == d


@pytest.mark.parametrize("visibility", VISIBILITIES)
def test_every_visibility_round_trip(visibility: Any) -> None:
    node = ClassNode(
        id="A",
        name="A",
        attributes=[Attribute("x", "int", visibility)],
        methods=[Method("f", "void", [], visibility)],
    )
    d = ClassDiagram(classes=[node])
    assert round_trip(d) == d


# ---------------------------------------------------------------- to_dict 모양
def test_to_dict_keys_follow_class_model_md() -> None:
    data = full_diagram().to_dict()
    cls = data["classes"][0]
    assert list(data) == ["version", "type", "classes", "relations", "errors"]
    assert list(cls) == [
        "id",
        "name",
        "kind",
        "generics",
        "attributes",
        "methods",
        "values",
        "implicit",
        "source",
    ]
    assert list(cls["attributes"][0]) == [
        "name",
        "type",
        "visibility",
        "isStatic",
        "source",
    ]
    assert list(cls["methods"][0]) == [
        "name",
        "returns",
        "params",
        "visibility",
        "isStatic",
        "isAbstract",
        "source",
    ]
    assert list(data["relations"][0]) == [
        "id",
        "from",
        "to",
        "kind",
        "directed",
        "fromMultiplicity",
        "toMultiplicity",
        "label",
        "layoutKey",
        "source",
    ]


def test_to_dict_values() -> None:
    data = full_diagram().to_dict()
    assert data["classes"][0]["source"] == {"line": 2, "endLine": 6}
    assert data["classes"][0]["methods"][0]["params"][1] == {
        "name": "strict",
        "type": None,
    }
    assert data["relations"][0]["from"] == "사용자"
    assert data["relations"][0]["layoutKey"] == "사용자->Order"
    assert data["errors"][0] == {
        "line": 14,
        "column": 5,
        "message": "알 수 없는 화살표입니다.",
    }


def test_to_dict_keeps_none_keys() -> None:
    rel = full_diagram().to_dict()["relations"][1]
    assert "label" in rel
    assert rel["label"] is None


def test_to_dict_returns_copy() -> None:
    d = full_diagram()
    d.to_dict()["classes"][0]["generics"].append("X")
    assert d.classes[0].generics == ["T", "ID"]


# ---------------------------------------------------------------- from_dict 기본값
def test_from_dict_empty_dict_gives_default_diagram() -> None:
    assert ClassDiagram.from_dict({}) == ClassDiagram()


def test_from_dict_minimal_class() -> None:
    d = ClassDiagram.from_dict({"classes": [{"id": "User"}]})
    assert d.classes[0] == ClassNode(id="User", name="User")


def test_from_dict_minimal_relation() -> None:
    d = ClassDiagram.from_dict(
        {"relations": [{"id": "r1", "from": "A", "to": "B", "kind": "dependency"}]}
    )
    rel = d.relations[0]
    assert rel.layout_key == "A->B"
    assert rel.directed is False
    assert rel.label is None


def test_from_dict_end_line_defaults_to_line() -> None:
    d = ClassDiagram.from_dict({"classes": [{"id": "A", "source": {"line": 7}}]})
    assert d.classes[0].source == Source(7, 7)


# ---------------------------------------------------------------- from_dict 오류
@pytest.mark.parametrize(
    "data",
    [
        pytest.param([], id="최상위가 dict가 아님"),
        pytest.param({"version": 2}, id="version 불일치"),
        pytest.param({"type": "flow"}, id="모르는 type"),
        pytest.param({"type": "sequence"}, id="sequence는 아직 미지원"),
        pytest.param({"classes": "User"}, id="classes가 목록이 아님"),
        pytest.param({"classes": [{"name": "User"}]}, id="class id 없음"),
        pytest.param({"classes": [{"id": "A", "kind": "bad"}]}, id="모르는 kind"),
        pytest.param(
            {
                "classes": [
                    {"id": "A", "attributes": [{"name": "x", "isStatic": "yes"}]}
                ]
            },
            id="isStatic이 글자",
        ),
        pytest.param(
            {"classes": [{"id": "A", "methods": [{"name": "f", "visibility": "!"}]}]},
            id="모르는 visibility",
        ),
        pytest.param({"classes": [{"id": "A", "generics": [1]}]}, id="generics에 숫자"),
        pytest.param(
            {"relations": [{"id": "r1", "from": "A", "to": "B"}]},
            id="relation kind 없음",
        ),
        pytest.param(
            {"relations": [{"id": "r1", "to": "B", "kind": "association"}]},
            id="relation from 없음",
        ),
        pytest.param(
            {"errors": [{"line": "3", "column": 1, "message": "x"}]}, id="line이 글자"
        ),
        pytest.param(
            {"errors": [{"line": True, "column": 1, "message": "x"}]}, id="line이 bool"
        ),
        pytest.param({"classes": [{"id": "A", "source": 3}]}, id="source가 dict 아님"),
    ],
)
def test_from_dict_bad_data_raises_model_error(data: Any) -> None:
    with pytest.raises(ModelError):
        ClassDiagram.from_dict(data)


def test_model_error_is_value_error() -> None:
    assert issubclass(ModelError, ValueError)


def test_model_error_message_shows_where() -> None:
    with pytest.raises(ModelError, match=r"classes\[1\]\.kind"):
        ClassDiagram.from_dict({"classes": [{"id": "A"}, {"id": "B", "kind": "bad"}]})
