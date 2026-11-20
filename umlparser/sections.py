"""클래스 원문과 시퀀스 원문을 줄 경계에서 분리한다."""

from dataclasses import dataclass


@dataclass
class Sections:
    before: str
    sequence: str
    after: str

    @property
    def class_code(self) -> str:
        return self.before + "\n" * self.sequence.count("\n") + self.after


def split_sections(code: str) -> Sections | None:
    lines = code.splitlines(keepends=True)
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.partition("%%")[0].strip() == "sequenceDiagram"
        ),
        None,
    )
    if start is None:
        return None
    stop = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].partition("%%")[0].strip() == "classDiagram"
        ),
        len(lines),
    )
    return Sections(
        "".join(lines[:start]), "".join(lines[start:stop]), "".join(lines[stop:])
    )
