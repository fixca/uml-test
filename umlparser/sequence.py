"""Mermaid 참여자 선언과 시간순 메시지를 읽는다.

메시지 화살표 뒤의 `+`/`-` 축약 표기로 활성 구간(activation)을 계산한다.
- `A->>+B`는 받는 쪽(B)을 활성화하고, `B-->>-A`는 보내는 쪽(B)의 가장 안쪽
  활성 구간을 끝낸다. 같은 참여자를 여러 번 `+`하면 구간이 중첩된다(depth).
- 구간은 시작 메시지 순번(start)부터 끝 메시지 순번(end)까지이며, 시작한
  순서(start, depth 오름차순)로 `Sequence.activations`에 담는다.
- 닫히지 않은 구간은 오류가 아니며 마지막 메시지에서 끝난 것으로 본다.
- 활성화되지 않은 참여자를 `-`로 끝내면 그 줄에 오류를 더한다.
- `activate`/`deactivate` 키워드 문장은 지원하지 않는다.
"""

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
    implicit: bool = False  # 선언 없이 메시지에서 처음 나온 참여자


@dataclass
class Message:
    sender: str
    arrow: str
    receiver: str
    label: str
    activate: bool = False  # 원문에 `+`가 있었는지
    deactivate: bool = False  # 원문에 `-`가 있었는지


@dataclass
class Activation:
    participant: str
    start: int  # 활성화한 메시지의 순번(messages 인덱스, 0부터)
    end: int  # 끝낸 메시지의 순번. 끝까지 닫히지 않으면 마지막 메시지 순번
    depth: int  # 같은 참여자 안에서의 중첩 깊이(0부터)


@dataclass
class Sequence:
    participants: dict[str, Participant] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)
    activations: list[Activation] = field(default_factory=list)


@dataclass
class SequenceDocument(ClassDiagram):
    type: str = "sequence"
    sequence: Sequence = field(default_factory=Sequence)

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "sequence": asdict(self.sequence)}


_DECLARATION = re.compile(r"(actor|participant)\s+([\w.-]+)(?:\s+as\s+(.+))?")
# 이름은 `-`로 시작할 수 없다. 그래야 `B-->>-A`의 `-`가 이름에 섞이지 않는다.
_MESSAGE = re.compile(
    r"([\w.][\w.-]*?)\s*(-->>|->>|-->|->|--x|-x|--\)|-\))"
    r"\s*([+-])?\s*([\w.][\w.-]*)\s*:\s*(.*)"
)


def read_sequence(lines: list[tuple[int, str]], document: SequenceDocument) -> None:
    sequence = document.sequence
    # 참여자별 열린 활성 구간의 시작 메시지 순번
    stacks: dict[str, list[int]] = {}
    for number, raw in lines:
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        if match := _DECLARATION.fullmatch(line):
            kind, name, alias = match.groups()
            sequence.participants[name] = Participant(name, alias or name, kind, number)
        elif match := _MESSAGE.fullmatch(line):
            sender, arrow, mod, receiver, label = match.groups()
            for name in (sender, receiver):
                sequence.participants.setdefault(
                    name,
                    Participant(name, name, "participant", number, implicit=True),
                )
            sequence.messages.append(
                Message(
                    sender,
                    arrow,
                    receiver,
                    label,
                    activate=mod == "+",
                    deactivate=mod == "-",
                )
            )
            index = len(sequence.messages) - 1
            if mod == "-":
                stack = stacks.get(sender, [])
                if stack:
                    depth = len(stack) - 1
                    sequence.activations.append(
                        Activation(sender, stack.pop(), index, depth)
                    )
                else:
                    document.errors.append(
                        ParseError(
                            number, 1, f"{sender}은(는) 활성화되어 있지 않습니다."
                        )
                    )
            elif mod == "+":
                stacks.setdefault(receiver, []).append(index)
        else:
            document.errors.append(
                ParseError(number, 1, "지원하지 않는 시퀀스 구문입니다.")
            )
    # 닫히지 않은 구간은 마지막 메시지에서 끝난 것으로 본다.
    last = len(sequence.messages) - 1
    for name, stack in stacks.items():
        for depth, start in enumerate(stack):
            sequence.activations.append(Activation(name, start, last, depth))
    sequence.activations.sort(key=lambda a: (a.start, a.depth))
