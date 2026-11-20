"""클래스와 시퀀스 모델을 독립된 그림 요소로 한 장면에 배치한다."""

from PyQt6.QtWidgets import QGraphicsScene

from gui.canvas import DiagramSignals
from gui.renderers.base import Diagram
from gui.renderers.class_renderer import ClassDiagramRenderer
from gui.renderers.sequence_renderer import draw_sequence
from umlparser.sequence import SequenceDocument
from umlparser.storage import Layout


class MixedRenderer(ClassDiagramRenderer):
    diagram_type = "mixed"

    def render(
        self,
        scene: QGraphicsScene,
        diagram: Diagram,
        layout: Layout,
        signals: DiagramSignals,
    ) -> None:
        if not isinstance(diagram, SequenceDocument):
            raise TypeError("복합 다이어그램 모델이 필요합니다.")
        super().render(scene, diagram, layout, signals)
        top = -180 - 64 * len(diagram.sequence.messages)
        draw_sequence(scene, diagram.sequence, top, layout, signals)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
