"""umlparser.edit 테스트 (B6)."""

from umlparser import parse
from umlparser.edit import append_class, class_block, unique_class_id

CODE = """\
classDiagram
class User {
    <<abstract>>
    -String name
    +login() bool
}
User --> Order
<<interface>> Shape
Shape : +area() double
"""


# ---------------------------------------------------------------- class_block
def test_class_block_returns_declaration() -> None:
    assert class_block(CODE, "User") == (
        "class User {\n    <<abstract>>\n    -String name\n    +login() bool\n}"
    )


def test_class_block_collects_lines_outside_block() -> None:
    assert class_block(CODE, "Shape") == "<<interface>> Shape\nShape : +area() double"


def test_class_block_missing_or_implicit_is_empty() -> None:
    assert class_block(CODE, "Nope") == ""
    assert class_block(CODE, "Order") == ""


# ---------------------------------------------------------------- unique_class_id
def test_unique_class_id() -> None:
    assert unique_class_id(CODE, "Item") == "Item"
    assert unique_class_id(CODE, "User") == "User2"
    assert unique_class_id(CODE + "class User2\n", "User") == "User3"
    assert unique_class_id(CODE + "class User2\n", "User2") == "User3"
    assert unique_class_id(CODE, "Order") == "Order2"  # implicit 클래스도 겹침


# ---------------------------------------------------------------- append_class
def test_append_class_renames_on_conflict() -> None:
    block = class_block(CODE, "User")
    new_code = append_class(CODE, block, "User")
    assert new_code.startswith(CODE)
    assert new_code.endswith(
        "class User2 {\n    <<abstract>>\n    -String name\n    +login() bool\n}\n"
    )

    d = parse(new_code)
    assert d.errors == []
    user2 = next(c for c in d.classes if c.id == "User2")
    assert user2.kind == "abstract"
    assert [m.name for m in user2.methods] == ["login"]


def test_append_class_twice_gives_user3() -> None:
    block = class_block(CODE, "User")
    code = append_class(append_class(CODE, block, "User"), block, "User")
    assert [c.id for c in parse(code).classes if c.id.startswith("User")] == [
        "User",
        "User2",
        "User3",
    ]


def test_append_class_renames_outside_lines() -> None:
    block = class_block(CODE, "Shape")
    new_code = append_class(CODE, block, "Shape")
    assert new_code.endswith("<<interface>> Shape2\nShape2 : +area() double\n")
    shape2 = next(c for c in parse(new_code).classes if c.id == "Shape2")
    assert shape2.kind == "interface"


def test_append_class_keeps_member_types() -> None:
    block = "class Node {\n    +Node next\n}"
    new_code = append_class("class Node\n", block, "Node")
    assert "class Node2 {\n    +Node next\n}" in new_code


def test_append_class_without_trailing_newline() -> None:
    assert append_class("class A", "class B", "B") == "class A\nclass B\n"


def test_append_class_to_empty_code() -> None:
    assert append_class("", "class B", "B") == "class B\n"


def test_append_class_invalid_block_keeps_code() -> None:
    assert append_class(CODE, "", "User") == CODE
    assert append_class(CODE, "A --> B", "A") == CODE


def test_append_class_invalid_new_id_uses_block_name() -> None:
    new_code = append_class(CODE, "class Item", "잘못된 이름!")
    assert new_code.endswith("class Item\n")
