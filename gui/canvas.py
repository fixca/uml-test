"""팩토리에 전달할 장면과 공통 상호작용 시그널."""

from PyQt6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget


class DiagramSignals(QObject):
    moved = pyqtSignal(str, float, float)
    double_clicked = pyqtSignal(str)
    edge_toggled = pyqtSignal(str)


class DiagramScene(QGraphicsScene):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.signals = DiagramSignals(self)

    def selected_class_ids(self) -> list[str]:
        return list(
            dict.fromkeys(
                item.data(0)
                for item in self.selectedItems()
                if isinstance(item.data(0), str)
            )
        )


class DiagramView(QGraphicsView):
    PAN_MARGIN_PX = 64

    def __init__(self, scene: DiagramScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.pan_position: QPoint | None = None

    def center_canvas(self, point: QPointF) -> None:
        # 화면 여백은 뷰에서만 관리해 내보내는 그림의 크기를 유지한다.
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        margin = QRectF(visible)
        margin.moveCenter(point)
        area = self.scene().sceneRect().united(margin.adjusted(-2, -2, 2, 2))
        self.setSceneRect(area)
        self.centerOn(point)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_position = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.pan_position is not None:
            position = event.position().toPoint()
            center = self.viewport().rect().center()
            target = self.mapToScene(center + self.pan_position - position)
            viewport = self.viewport().rect()
            margin = min(
                self.PAN_MARGIN_PX, viewport.width() / 4, viewport.height() / 4
            )
            padding = margin / self.transform().m11()
            bounds = (
                self.scene().sceneRect().adjusted(-padding, -padding, padding, padding)
            )
            self.center_canvas(
                QPointF(
                    max(bounds.left(), min(target.x(), bounds.right())),
                    max(bounds.top(), min(target.y(), bounds.bottom())),
                )
            )
            self.pan_position = position
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_position = None
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def zoom_by(self, steps: float, anchor: QPoint | None = None) -> None:
        current = self.transform().m11()
        target = max(0.1, min(4.0, current * 1.2 ** max(-32, min(32, steps))))
        if target == current:
            return
        center = self.viewport().rect().center()
        anchor = center if anchor is None else anchor
        before = self.mapToScene(anchor)
        self.scale(target / current, target / current)
        self.center_canvas(before + (self.mapToScene(center) - self.mapToScene(anchor)))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            self.zoom_by(delta / 120, event.position().toPoint())
        event.accept()
