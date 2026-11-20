"""아직 전용 렌더러가 없는 다이어그램 종류의 임시 렌더러."""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QGraphicsScene

from gui.canvas import DiagramSignals
from gui.renderers.base import Diagram, DiagramRenderer
from umlparser.storage import Layout


class OtherDiagramRenderer(DiagramRenderer):
    def render(
        self,
        scene: QGraphicsScene,
        diagram: Diagram,
        layout: Layout,
        signals: DiagramSignals,
    ) -> None:
        """안내 문구만 그리고 NotImplementedError를 던진다."""
        message = f"'{diagram.type}' 다이어그램은 아직 지원하지 않습니다."
        # 이전 종류의 그림이 남지 않게 먼저 지운다.
        scene.clear()
        text = scene.addSimpleText(message)
        text.setBrush(QBrush(QColor("#64748b")))
        bounds: QRectF = text.sceneBoundingRect()
        scene.setSceneRect(bounds.adjusted(-40, -40, 40, 40))
        raise NotImplementedError(message)
