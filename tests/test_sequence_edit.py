"""umlparser.edit.reorder_participants 테스트."""

from umlparser import parse
from umlparser.edit import reorder_participants
from umlparser.sequence import SequenceDocument

DECLARED = (
    "sequenceDiagram\n"
    "    actor User as 사용자\n"
    "    participant API\n"
    "    %% 로그인\n"
    "\n"
    "    User->>API: 요청\n"
    "    API-->>User: 응답\n"
)


def participants(code: str) -> list[str]:
    document = parse(code)
    assert isinstance(document, SequenceDocument)
    return list(document.sequence.participants)


def test_declared_participants_move_under_header_keeping_text() -> None:
    result = reorder_participants(DECLARED, ["API", "User"])
    assert result.splitlines()[:3] == [
        "sequenceDiagram",
        "    participant API",
        "    actor User as 사용자",
    ]
    assert participants(result) == ["API", "User"]
    label = parse(result).sequence.participants["User"]
    assert (label.label, label.kind) == ("사용자", "actor")


def test_message_comment_and_blank_lines_keep_relative_order() -> None:
    result = reorder_participants(DECLARED, ["API", "User"])
    assert result.splitlines()[3:] == DECLARED.splitlines()[3:]


def test_implicit_participants_get_declarations() -> None:
    code = "sequenceDiagram\n    A->>B: x\n"
    result = reorder_participants(code, ["B", "A"])
    assert result == (
        "sequenceDiagram\n    participant B\n    participant A\n    A->>B: x\n"
    )
    assert participants(result) == ["B", "A"]


def test_unchangeable_input_returns_original() -> None:
    assert reorder_participants(DECLARED, ["User", "API"]) == DECLARED
    assert reorder_participants(DECLARED, ["API"]) == DECLARED
    assert reorder_participants(DECLARED, ["API", "Other"]) == DECLARED
    broken = DECLARED + "nonsense !\n"
    assert reorder_participants(broken, ["API", "User"]) == broken
    classes = "classDiagram\nclass A\nclass B\n"
    assert reorder_participants(classes, ["B", "A"]) == classes


def test_crlf_is_preserved() -> None:
    code = "sequenceDiagram\r\n    A->>B: x\r\n"
    result = reorder_participants(code, ["B", "A"])
    assert result == (
        "sequenceDiagram\r\n    participant B\r\n    participant A\r\n"
        "    A->>B: x\r\n"
    )
