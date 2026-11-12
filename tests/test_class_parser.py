"""umlparser.class_parser.parse() 테스트 (B2~B5)."""

import time

import pytest

from umlparser import parse
from umlparser.model import Attribute, Method, Param, Source

EXAMPLE = """\
classDiagram
%% 주문 예시
class Repository~T, ID~ {
    <<interface>>
    +findById(ID id) T*
    +count()$ int
}
class Status {
    <<enumeration>>
    ACTIVE
    INACTIVE
}
class User["사용자"] {
    -String name
    +List~Order~ orders
    #int total$
    +place(order: Order, int qty): bool
}
<<abstract>> Shape
Shape : +area()* double
User "1" --> "0..*" Order : places
UserRepository ..|> Repository
"""


def by_id(code: str) -> dict:
    return {c.id: c for c in parse(code).classes}


# ---------------------------------------------------------------- 클래스 선언
def test_example_has_no_errors() -> None:
    assert parse(EXAMPLE).errors == []


def test_class_order_follows_first_appearance() -> None:
    ids = [c.id for c in parse(EXAMPLE).classes]
    assert ids == ["Repository", "Status", "User", "Shape", "Order", "UserRepository"]


def test_class_block_source_lines() -> None:
    classes = by_id(EXAMPLE)
    assert classes["Repository"].source == Source(3, 7)
    assert classes["Status"].source == Source(8, 12)
    assert classes["Shape"].source == Source(19, 19)


def test_simple_class_without_body() -> None:
    node = parse("classDiagram\nclass User").classes[0]
    assert (node.id, node.name, node.kind, node.implicit) == (
        "User",
        "User",
        "class",
        False,
    )
    assert node.source == Source(2, 2)


def test_empty_braces_on_one_line() -> None:
    d = parse("class A {}\nclass B {\n}")
    assert d.errors == []
    assert [c.source for c in d.classes] == [Source(1, 1), Source(2, 3)]


def test_label_sets_name() -> None:
    assert by_id(EXAMPLE)["User"].name == "사용자"


def test_generics() -> None:
    assert by_id(EXAMPLE)["Repository"].generics == ["T", "ID"]
    assert parse("class Box~List~T~~").classes[0].generics == ["List<T>"]


def test_korean_class_id() -> None:
    d = parse("class 사용자 {\n    +이름 String\n}")
    assert d.errors == []
    assert d.classes[0].id == "사용자"


@pytest.mark.parametrize(
    ("annotation", "kind"),
    [
        ("interface", "interface"),
        ("abstract", "abstract"),
        ("enumeration", "enum"),
        ("Interface", "interface"),
    ],
)
def test_annotation_kinds(annotation: str, kind: str) -> None:
    inside = parse(f"class A {{\n<<{annotation}>>\n}}").classes[0]
    outside = parse(f"<<{annotation}>> A").classes[0]
    assert inside.kind == outside.kind == kind


def test_enum_values() -> None:
    node = by_id(EXAMPLE)["Status"]
    assert node.values == ["ACTIVE", "INACTIVE"]
    assert node.attributes == []


def test_comment_and_ignored_statements() -> None:
    d = parse('classDiagram\ndirection LR\n%% class Hidden\nnote for A "x"\nclass A')
    assert d.errors == []
    assert [c.id for c in d.classes] == ["A"]


def test_empty_code() -> None:
    d = parse("")
    assert (d.classes, d.relations, d.errors) == ([], [], [])


# ---------------------------------------------------------------- 멤버
def test_attributes() -> None:
    attrs = by_id(EXAMPLE)["User"].attributes
    assert attrs == [
        Attribute("name", "String", "-", False, Source(14, 14)),
        Attribute("orders", "List<Order>", "+", False, Source(15, 15)),
        Attribute("total", "int", "#", True, Source(16, 16)),
    ]


def test_attribute_colon_style_and_no_type() -> None:
    attrs = parse("class A {\n+id: int\nflag\n}").classes[0].attributes
    assert [(a.name, a.type, a.visibility) for a in attrs] == [
        ("id", "int", "+"),
        ("flag", None, ""),
    ]


def test_methods() -> None:
    repo = by_id(EXAMPLE)["Repository"]
    assert repo.methods == [
        Method("findById", "T", [Param("id", "ID")], "+", False, True, Source(5, 5)),
        Method("count", "int", [], "+", True, False, Source(6, 6)),
    ]


def test_method_param_styles() -> None:
    method = by_id(EXAMPLE)["User"].methods[0]
    assert method.params == [Param("order", "Order"), Param("qty", "int")]
    assert method.returns == "bool"


def test_method_generic_params() -> None:
    m = parse("class A {\n+put(Map~K, V~ m, n) void\n}").classes[0].methods[0]
    assert m.params == [Param("m", "Map<K, V>"), Param("n")]


def test_member_line_outside_block() -> None:
    shape = by_id(EXAMPLE)["Shape"]
    assert shape.kind == "abstract"
    assert shape.methods[0].is_abstract
    assert shape.methods[0].returns == "double"
    assert shape.methods[0].source == Source(20, 20)


def test_enum_method_is_still_method() -> None:
    node = parse("class E {\n<<enumeration>>\nA\nlabel() String\n}").classes[0]
    assert node.values == ["A"]
    assert [m.name for m in node.methods] == ["label"]


# ---------------------------------------------------------------- 관계
@pytest.mark.parametrize(
    ("line", "kind", "from_", "to", "directed"),
    [
        ("A <|-- B", "inheritance", "B", "A", False),
        ("B --|> A", "inheritance", "B", "A", False),
        ("A <|.. B", "realization", "B", "A", False),
        ("B ..|> A", "realization", "B", "A", False),
        ("A *-- B", "composition", "B", "A", False),
        ("B --* A", "composition", "B", "A", False),
        ("A o-- B", "aggregation", "B", "A", False),
        ("B --o A", "aggregation", "B", "A", False),
        ("A --> B", "association", "A", "B", True),
        ("B <-- A", "association", "A", "B", True),
        ("A -- B", "association", "A", "B", False),
        ("A ..> B", "dependency", "A", "B", True),
        ("B <.. A", "dependency", "A", "B", True),
        ("A .. B", "dependency", "A", "B", False),
    ],
)
def test_relation_kinds_and_direction(
    line: str, kind: str, from_: str, to: str, directed: bool
) -> None:
    d = parse(line)
    assert d.errors == []
    rel = d.relations[0]
    assert (rel.kind, rel.from_, rel.to, rel.directed) == (kind, from_, to, directed)


def test_relation_multiplicity_and_label() -> None:
    rel = parse(EXAMPLE).relations[0]
    assert (rel.from_, rel.to) == ("User", "Order")
    assert (rel.from_multiplicity, rel.to_multiplicity) == ("1", "0..*")
    assert rel.label == "places"
    assert rel.source == Source(21, 21)


def test_multiplicity_follows_normalization() -> None:
    rel = parse('Car "1" *-- "4" Wheel').relations[0]
    assert (rel.from_, rel.from_multiplicity) == ("Wheel", "4")
    assert (rel.to, rel.to_multiplicity) == ("Car", "1")


def test_relation_ids_and_layout_keys() -> None:
    d = parse("A --> B\nA --> B\nB <-- A\nB --> A")
    assert [r.id for r in d.relations] == ["r1", "r2", "r3", "r4"]
    assert [r.layout_key for r in d.relations] == [
        "A->B",
        "A->B#2",
        "A->B#3",
        "B->A",
    ]


def test_implicit_classes() -> None:
    classes = by_id(EXAMPLE)
    assert classes["Order"].implicit
    assert classes["Order"].source == Source(21, 21)
    assert not classes["User"].implicit


def test_later_declaration_clears_implicit() -> None:
    d = parse("A --> B\nclass B {\n+x\n}")
    b = by_id("A --> B\nclass B {\n+x\n}")["B"]
    assert d.errors == []
    assert not b.implicit
    assert b.source == Source(2, 4)


# ---------------------------------------------------------------- 오류 (B4)
def test_bad_line_is_skipped_and_rest_parsed() -> None:
    d = parse("class A\n이건 잘못된 줄\nclass B")
    assert [c.id for c in d.classes] == ["A", "B"]
    assert len(d.errors) == 1
    assert (d.errors[0].line, d.errors[0].column) == (2, 1)


def test_unknown_arrow_column() -> None:
    d = parse("  A -> B")
    assert d.relations == []
    err = d.errors[0]
    assert (err.line, err.column) == (1, 5)
    assert "화살표" in err.message


def test_unclosed_block_at_end() -> None:
    d = parse("class A {\n+int x")
    assert d.errors[0].line == 1
    assert d.classes[0].attributes[0].name == "x"
    assert d.classes[0].source == Source(1, 2)


def test_missing_brace_before_next_class() -> None:
    d = parse("class A {\n+int x\nclass B {\n+int y\n}")
    assert [e.line for e in d.errors] == [1]
    classes = by_id("class A {\n+int x\nclass B {\n+int y\n}")
    assert classes["A"].source == Source(1, 2)
    assert [a.name for a in classes["B"].attributes] == ["y"]


def test_bad_member_reports_error_and_keeps_others() -> None:
    d = parse("class A {\n  +int ok\n  +bad(int\n}")
    assert [a.name for a in d.classes[0].attributes] == ["ok"]
    assert (d.errors[0].line, d.errors[0].column) == (3, 3)


def test_stray_brace_and_unknown_annotation() -> None:
    d = parse("}\n<<service>> A")
    assert [e.line for e in d.errors] == [1, 2]


def test_header_only_first() -> None:
    d = parse("class A\nclassDiagram")
    assert d.errors[0].line == 2


def test_error_messages_are_korean() -> None:
    d = parse("??")
    assert all(any("가" <= ch <= "힣" for ch in e.message) for e in d.errors)


@pytest.mark.parametrize(
    "code",
    [
        "class",
        "class {",
        "<<>>",
        "A : ",
        "class A {\n()\n}",
        "class A {\n+f(,) int\n}",
        'A "1 --> B',
        "~~~~",
        "\x00\t\r\n",
        "}}}}",
    ],
)
def test_never_raises(code: str) -> None:
    parse(code)


def test_non_string_input_returns_error() -> None:
    d = parse(None)  # type: ignore[arg-type]
    assert d.errors and d.classes == []


# ---------------------------------------------------------------- 성능 (B5)
def test_performance_30_classes_40_relations() -> None:
    lines = ["classDiagram"]
    for i in range(30):
        lines += [
            f"class C{i} {{",
            "    -String name",
            "    +int count$",
            "    +find(int id, String key) C0",
            "}",
        ]
    for i in range(40):
        lines.append(f'C{i % 30} "1" --> "*" C{(i * 7 + 1) % 30} : uses')
    code = "\n".join(lines)

    parse(code)  # 정규식 컴파일 캐시 등 첫 호출 비용 제외
    runs = 20
    start = time.perf_counter()
    for _ in range(runs):
        d = parse(code)
    elapsed_ms = (time.perf_counter() - start) * 1000 / runs

    assert d.errors == []
    assert (len(d.classes), len(d.relations)) == (30, 40)
    assert elapsed_ms <= 10
