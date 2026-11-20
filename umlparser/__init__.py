"""다이어그램 코드 파싱 진입점."""

from umlparser.class_parser import parse as parse_class
from umlparser.model import ClassDiagram, ParseError
from umlparser.sections import split_sections
from umlparser.sequence import SequenceDocument, read_sequence

MIXED_MESSAGE = "클래스 다이어그램과 시퀀스 다이어그램은 한 문서에 함께 쓸 수 없습니다."


def parse(code: str) -> ClassDiagram | SequenceDocument:
    sections = split_sections(code) if isinstance(code, str) else None
    if sections is None:
        return parse_class(code)
    document = SequenceDocument(type="sequence")
    first = len(sections.before.splitlines()) + 2
    read_sequence(list(enumerate(sections.sequence.splitlines()[1:], first)), document)
    # 한 문서에는 한 종류의 다이어그램만 쓸 수 있다. 클래스 구간은 모델에 넣지 않는다.
    has_class = any(
        line.partition("%%")[0].strip() for line in sections.class_code.splitlines()
    )
    if has_class:
        header = first - 1
        if any(
            line.partition("%%")[0].strip() for line in sections.before.splitlines()
        ):
            line = header
        else:
            # 시퀀스 뒤의 classDiagram 줄
            line = header + len(sections.sequence.splitlines())
        document.errors.append(ParseError(line, 1, MIXED_MESSAGE))
    document.errors.sort(key=lambda error: (error.line, error.column))
    return document


__all__ = ["parse"]
