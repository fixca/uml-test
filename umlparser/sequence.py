"""Mermaid 참여자 선언과 시간순 메시지를 읽는다."""

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from umlparser.model import ClassDiagram, ParseError


@dataclass
class Participant:
    id: str
    label: str
    kind: str
    line: int


@dataclass
class Message:
    sender: str
    arrow: str
    receiver: str
    label: str


@dataclass
class Sequence:
    participants: dict[str, Participant] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)


@dataclass
class SequenceDocument(ClassDiagram):
    type: str = "sequence"
    sequence: Sequence = field(default_factory=Sequence)

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "sequence": asdict(self.sequence)}


_DECLARATION = re.compile(r"(actor|participant)\s+([\w.-]+)(?:\s+as\s+(.+))?")
_MESSAGE = re.compile(
    r"([\w.-]+?)\s*(-->>|->>|-->|->|--x|-x|--\)|-\))\s*([\w.-]+)\s*:\s*(.*)"
)


def read_sequence(lines: list[tuple[int, str]], document: SequenceDocument) -> None:
    sequence = document.sequence
    for number, raw in lines:
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        if match := _DECLARATION.fullmatch(line):
            kind, name, alias = match.groups()
            sequence.participants[name] = Participant(name, alias or name, kind, number)
        elif match := _MESSAGE.fullmatch(line):
            sender, arrow, receiver, label = match.groups()
            for name in (sender, receiver):
                sequence.participants.setdefault(
                    name, Participant(name, name, "participant", number)
                )
            sequence.messages.append(Message(sender, arrow, receiver, label))
        else:
            document.errors.append(
                ParseError(number, 1, "지원하지 않는 시퀀스 구문입니다.")
            )
