"""다이어그램 코드 파싱 진입점."""

from umlparser.class_parser import parse as parse_class
from umlparser.model import ClassDiagram, ParseError
from umlparser.sections import split_sections
from umlparser.sequence import SequenceDocument, read_sequence

MIXED_MESSAGE = "클래스 다이어그램과 시퀀스 다이어그램은 한 문서에 함께 쓸 수 없습니다."


def parse(code: str) -> ClassDiagram | SequenceDocument:
    """원문을 파싱해 클래스 모델이나 시퀀스 모델을 돌려준다. 오류는 errors에 담긴다."""
    sections = split_sections(code) if isinstance(code, str) else None
    if sections is None:
        return parse_class(code)
    document = SequenceDocument(type="sequence")
    first = len(sections.before.splitlines()) + 2
    read_sequence(list(enumerate(sections.sequence.splitlines()[1:], first)), document)
    # 시퀀스 문서에 클래스 내용이 섞이면 오류로 알린다. (클래스 구간은 무시한다.)
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
            # 시퀀스 뒤에 붙은 classDiagram 줄을 오류 위치로 삼는다.
            line = header + len(sections.sequence.splitlines())
        document.errors.append(ParseError(line, 1, MIXED_MESSAGE))
    document.errors.sort(key=lambda error: (error.line, error.column))
    return document


__all__ = ["parse"]
