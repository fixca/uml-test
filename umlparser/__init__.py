"""다이어그램 코드 파싱 진입점."""

from umlparser.class_parser import parse as parse_class
from umlparser.model import ClassDiagram
from umlparser.sequence import SequenceDocument, read_sequence


def parse(code: str) -> ClassDiagram:
    if isinstance(code, str):
        lines = list(enumerate(code.splitlines(), 1))
        for index, line in lines:
            if not line.strip() or line.lstrip().startswith("%%"):
                continue
            if line.strip() == "sequenceDiagram":
                document = SequenceDocument()
                read_sequence(lines[index:], document)
                return document
            break
    return parse_class(code)


__all__ = ["parse"]
