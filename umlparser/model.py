"""공통 모델 dataclass와 to_dict/from_dict. 담당: 심현보 (B1).

필드는 docs/00-common.md 5.1을 따른다.
"""

from dataclasses import dataclass, field


@dataclass
class ParseError:
    line: int
    column: int
    message: str


@dataclass
class ClassNode:
    pass  # B1에서 필드를 채운다.


@dataclass
class Relation:
    pass  # B1에서 필드를 채운다.


@dataclass
class ClassDiagram:
    version: int = 1
    type: str = "class"
    classes: list[ClassNode] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
