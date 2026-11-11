"""모델 → 그림 요소 생성. 담당: 이도훈 (F3, F4)."""

from PyQt6.QtWidgets import QGraphicsScene

from umlparser.model import ClassDiagram
from umlparser.storage import Layout


def build(scene: QGraphicsScene, diagram: ClassDiagram, layout: Layout) -> None:
    raise NotImplementedError
