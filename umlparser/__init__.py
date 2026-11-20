"""다이어그램 코드 파싱 진입점."""

from umlparser.class_parser import parse as parse_class
from umlparser.model import ClassDiagram
from umlparser.sections import split_sections
from umlparser.sequence import SequenceDocument, read_sequence


def parse(code: str) -> ClassDiagram:
    sections = split_sections(code) if isinstance(code, str) else None
    if sections is None:
        return parse_class(code)
    classes = parse_class(sections.class_code)
    has_class = any(
        line.partition("%%")[0].strip() for line in sections.class_code.splitlines()
    )
    document = SequenceDocument(
        type="mixed" if has_class else "sequence",
        classes=classes.classes,
        relations=classes.relations,
        errors=classes.errors,
    )
    first = len(sections.before.splitlines()) + 2
    read_sequence(list(enumerate(sections.sequence.splitlines()[1:], first)), document)
    document.errors.sort(key=lambda error: (error.line, error.column))
    return document


__all__ = ["parse"]
