"""클래스 원문과 시퀀스 원문을 줄 경계에서 분리한다."""

from dataclasses import dataclass


@dataclass
class Sections:
    before: str
    sequence: str
    after: str

    @property
    def class_code(self) -> str:
        """시퀀스 구간을 빈 줄로 채운 클래스 원문. 줄 번호는 원문과 같게 유지한다."""
        return self.before + "\n" * self.sequence.count("\n") + self.after


def split_sections(code: str) -> Sections | None:
    """원문에서 sequenceDiagram 구간을 떼어 낸다. 헤더가 없으면 None을 돌려준다."""
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
