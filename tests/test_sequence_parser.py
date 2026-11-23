"""시퀀스 메시지의 +/- 활성 구간 파싱과 참여자 순서 변경 테스트."""

from pathlib import Path

import pytest

from umlparser import parse
from umlparser.edit import reorder_participants
from umlparser.sequence import Activation, Message, SequenceDocument

HEADER = "sequenceDiagram\n"


def read(code: str) -> SequenceDocument:
    document = parse(HEADER + code)
    assert isinstance(document, SequenceDocument)
    return document


def test_activation_pair_has_no_fake_participant() -> None:
    document = read("A->>+B: 요청\nB-->>-A: 응답\n")
    assert not document.errors
    assert list(document.sequence.participants) == ["A", "B"]
    assert document.sequence.messages == [
        Message("A", "->>", "B", "요청", activate=True),
        Message("B", "-->>", "A", "응답", deactivate=True),
    ]
    assert document.sequence.activations == [Activation("B", 0, 1, 0)]


def test_nested_activations() -> None:
    document = read("A->>+B: a\nA->>+B: b\nB-->>-A: c\nB-->>-A: d\n")
    assert not document.errors
    assert document.sequence.activations == [
        Activation("B", 0, 3, 0),
        Activation("B", 1, 2, 1),
    ]


def test_unclosed_activation_ends_at_last_message() -> None:
    document = read("A->>+B: x\nA->>C: y\n")
    assert not document.errors
    assert document.sequence.activations == [Activation("B", 0, 1, 0)]


def test_deactivating_inactive_participant_is_an_error() -> None:
    document = parse(HEADER + "A-->>-B: x\n")
    assert [(e.line, e.message) for e in document.errors] == [
        (2, "A은(는) 활성화되어 있지 않습니다.")
    ]
    assert len(document.sequence.messages) == 1


def test_spaces_around_modifier_are_allowed() -> None:
    document = read("A ->> + B : x\nB -->> - A : y\n")
    assert not document.errors
    assert list(document.sequence.participants) == ["A", "B"]
    assert document.sequence.activations == [Activation("B", 0, 1, 0)]


@pytest.mark.parametrize(
    "arrow", ["->>", "-->>", "->", "-->", "-x", "--x", "-)", "--)"]
)
def test_every_arrow_keeps_its_shape_with_modifier(arrow: str) -> None:
    document = read(f"A{arrow}+B: x\nB{arrow}-A: y\n")
    assert not document.errors
    assert [m.arrow for m in document.sequence.messages] == [arrow, arrow]
    assert list(document.sequence.participants) == ["A", "B"]
    assert document.sequence.activations == [Activation("B", 0, 1, 0)]


def test_self_message_activation() -> None:
    document = read("A->>+A: x\nA->>-A: y\n")
    assert not document.errors
    assert document.sequence.activations == [Activation("A", 0, 1, 0)]


def test_plain_example_has_no_activations() -> None:
    code = (
        Path(__file__).parent.parent / "examples" / "sequence-example.mmd"
    ).read_text(encoding="utf-8")
    document = parse(code)
    assert isinstance(document, SequenceDocument)
    assert not document.errors
    assert document.sequence.activations == []


def test_reorder_participants_keeps_activations() -> None:
    code = HEADER + "A->>+B: x\nB-->>-A: y\n"
    result = reorder_participants(code, ["B", "A"])
    assert result != code
    before = read("A->>+B: x\nB-->>-A: y\n")
    after = parse(result)
    assert isinstance(after, SequenceDocument)
    assert not after.errors
    assert list(after.sequence.participants) == ["B", "A"]
    assert after.sequence.activations == before.sequence.activations
    assert "A->>+B: x" in result and "B-->>-A: y" in result
