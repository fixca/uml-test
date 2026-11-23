"""관계선, 화살표 머리, 다중성 라벨. 담당: 이도훈 (F2, F4).

상속 / 구현 / 연관 / 집합 / 합성 / 의존의 UML 표기를 그린다.
layout.edges의 모드에 따라 직선 또는 직각 꺾은 선으로 표시한다.
각 선분 클릭으로 중앙 조절점을 추가하고 드래그 결과를 edge_bent로 전달한다.
"""

from itertools import pairwise
from math import hypot

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QMenu,
    QStyleOptionGraphicsItem,
    QWidget,
)

from gui.items.class_item import ClassItem
from umlparser.model import Relation

INK = QColor("#334155")
HEAD_LENGTH = 16.0
HEAD_HALF_WIDTH = 7.0


def _boundary(box: QRectF, toward: QPointF) -> QPointF:
    """중심에서 toward로 향하는 광선과 박스 외곽의 교점."""
    center = box.center()
    dx, dy = toward.x() - center.x(), toward.y() - center.y()
    if dx == 0 and dy == 0:
        return QPointF(box.right(), center.y())
    scale = min(
        box.width() / (2 * abs(dx)) if dx else float("inf"),
        box.height() / (2 * abs(dy)) if dy else float("inf"),
    )
    return center + QPointF(dx * scale, dy * scale)


class RelationLabel(QGraphicsSimpleTextItem):
    """관계선이 글자를 가리지 않도록 라벨 뒤를 흰색으로 채운다."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.fillRect(self.boundingRect(), QColor("white"))
        super().paint(painter, option, widget)


class BendHandle(QGraphicsEllipseItem):
    """선택한 관계의 경유점. 내보내기에는 조절점을 그리지 않는다."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if widget is not None:
            super().paint(painter, option, widget)


class RelationItem(QGraphicsPathItem):
    """파서가 정규화한 to 쪽에 삼각형·마름모·화살촉을 둔다.

    관계선과 라벨은 클래스 선택 ID를 갖지 않는다.
    """

    def __init__(
        self,
        relation: Relation,
        source: ClassItem,
        target: ClassItem,
        mode: str = "straight",
        bends: list[tuple[float, float]] | None = None,
    ) -> None:
        super().__init__()
        self.relation = relation
        self.source = source
        self.target = target
        self.mode = mode
        self.bends = [QPointF(x, y) for x, y in (bends or [])]
        self.drag_index: int | None = None
        self.dragged = False
        self.pending_segment: int | None = None
        self.drag_pending = False
        self.original_bends: list[QPointF] = []
        self.original_pending: int | None = None
        self.setToolTip(
            "선분 클릭: 임시 점 표시 / 점 드래그: 경유 위치 변경 / 우클릭: 꺾임 제거"
        )
        # 클래스 박스 뒤에 선을 놓아 박스 내부를 가리지 않게 한다.
        self.setZValue(-1)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        pen = QPen(INK, 1.4)
        if relation.kind in ("realization", "dependency"):
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.pressed = False
        self.decorations: list[QGraphicsItem] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_geometry()

    def _route(self) -> list[QPointF]:
        """장면 좌표로 시작점·꺾이는 점·끝점을 순서대로 반환한다."""
        source = self.source.mapRectToScene(self.source.rect)
        target = self.target.mapRectToScene(self.target.rect)
        if self.bends:
            return [
                _boundary(source, self.bends[0]),
                *self.bends,
                _boundary(target, self.bends[-1]),
            ]
        if self.source is self.target:
            # 자기 관계는 외부 루프가 있어야 보인다. 두 모드 모두 루프로 표시한다.
            start = QPointF(source.right(), source.center().y())
            end = QPointF(source.center().x(), source.top())
            return [
                start,
                start + QPointF(40, 0),
                QPointF(source.right() + 40, source.top() - 40),
                end - QPointF(0, 40),
                end,
            ]
        if self.mode != "orthogonal":
            return [
                _boundary(source, target.center()),
                _boundary(target, source.center()),
            ]

        dx = target.center().x() - source.center().x()
        dy = target.center().y() - source.center().y()
        # 중심 거리만 보면 넓은 박스의 안쪽으로 선이 되돌아갈 수 있다.
        # 실제 박스 사이에 빈 공간이 있는 축을 우선해 연결한다.
        horizontal_gap = (
            source.right() < target.left() or target.right() < source.left()
        )
        vertical_gap = source.bottom() < target.top() or target.bottom() < source.top()
        use_horizontal = horizontal_gap and (not vertical_gap or abs(dx) > abs(dy))
        if use_horizontal:
            start = QPointF(
                source.right() if dx >= 0 else source.left(), source.center().y()
            )
            end = QPointF(
                target.left() if dx >= 0 else target.right(), target.center().y()
            )
            middle = (start.x() + end.x()) / 2
            points = [start, QPointF(middle, start.y()), QPointF(middle, end.y()), end]
        else:
            start = QPointF(
                source.center().x(), source.bottom() if dy >= 0 else source.top()
            )
            end = QPointF(
                target.center().x(), target.top() if dy >= 0 else target.bottom()
            )
            middle = (start.y() + end.y()) / 2
            points = [start, QPointF(start.x(), middle), QPointF(end.x(), middle), end]
        return [
            point for i, point in enumerate(points) if not i or point != points[i - 1]
        ]

    def update_geometry(self) -> None:
        """F4에서 이동 중 호출할 수 있는 경로 갱신 함수."""
        # 갱신할 때 이전 머리와 라벨이 중복해서 남지 않도록 제거한다.
        for item in self.decorations:
            item.setParentItem(None)
            if item.scene() is not None:
                item.scene().removeItem(item)
        self.decorations.clear()
        points = self._route()
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        self.setPath(path)
        if len(points) < 2:
            return

        # from_→to 순서의 경로. UML 종류에 따라 머리를 둘 끝점이 다르다.
        kind = self.relation.kind
        if kind in ("inheritance", "realization"):
            self._head(points[-1], points[-2], "triangle")
        elif kind in ("aggregation", "composition"):
            self._head(points[-1], points[-2], "diamond", filled=kind == "composition")
            # 방향 있는 집합·합성은 마름모 반대쪽(from_) 끝에 열린 화살촉이 더 붙는다.
            if self.relation.directed:
                self._head(points[0], points[1], "open")
        elif kind in ("association", "dependency") and self.relation.directed:
            self._head(points[-1], points[-2], "open")

        self._multiplicity(self.relation.from_multiplicity, points[0], self.source)
        self._multiplicity(self.relation.to_multiplicity, points[-1], self.target)
        self._label(self.relation.label, self._midpoint(points) + QPointF(0, -14))
        handle_points = list(self.bends)
        preview = self.preview_point()
        if preview is not None:
            handle_points.append(preview)
        for point in handle_points:
            handle = BendHandle(-6, -6, 12, 12, self)
            handle.setPos(point)
            handle.setPen(QPen(QColor("#2563eb"), 1.5))
            handle.setBrush(QColor("white"))
            handle.setZValue(3)
            handle.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            handle.setVisible(self.isSelected())
            self.decorations.append(handle)

    def preview_point(self) -> QPointF | None:
        """저장하지 않은 조절점의 현재 선분 중점."""
        if self.pending_segment is None:
            return None
        route = self._route()
        index = self.pending_segment
        if index + 1 >= len(route):
            return None
        return (route[index] + route[index + 1]) / 2

    def itemChange(
        self, change: QGraphicsItem.GraphicsItemChange, value: object
    ) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if not value:
                self.pending_segment = None
            self.update_geometry()
        return super().itemChange(change, value)

    def _head(
        self, tip: QPointF, previous: QPointF, shape: str, filled: bool = False
    ) -> None:
        vector = previous - tip
        length = hypot(vector.x(), vector.y())
        if length == 0:
            return
        # 선 방향과 그 수직 방향을 이용하면 대각선에서도 머리가 회전한다.
        unit = vector / length
        normal = QPointF(-unit.y(), unit.x())
        base = tip + unit * HEAD_LENGTH
        left, right = base + normal * HEAD_HALF_WIDTH, base - normal * HEAD_HALF_WIDTH
        path = QPainterPath()
        if shape == "open":
            path.moveTo(left)
            path.lineTo(tip)
            path.lineTo(right)
        else:
            vertices = (
                [tip, left, tip + unit * (HEAD_LENGTH * 2), right]
                if shape == "diamond"
                else [tip, left, right]
            )
            path.addPolygon(QPolygonF(vertices))
            path.closeSubpath()
        item = QGraphicsPathItem(path, self)
        item.setPen(QPen(INK, 1.4))  # 머리 외곽은 점선 관계에서도 실선이다.
        if shape != "open":
            item.setBrush(INK if filled else QColor("white"))
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.decorations.append(item)

    def _multiplicity(
        self, text: str | None, endpoint: QPointF, node: ClassItem
    ) -> None:
        """글자 가장자리를 클래스 경계에서 6px 띄워 끝점 옆에 둔다."""
        if not text:
            return
        item = RelationLabel(text, self)
        item.setBrush(INK)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        box = node.mapRectToScene(node.rect)
        width, height = item.boundingRect().width(), item.boundingRect().height()
        sides = [
            (
                abs(endpoint.x() - box.left()),
                QPointF(box.left() - width - 6, endpoint.y() - height - 10),
            ),
            (
                abs(endpoint.x() - box.right()),
                QPointF(box.right() + 6, endpoint.y() - height - 10),
            ),
            (
                abs(endpoint.y() - box.top()),
                QPointF(endpoint.x() + 10, box.top() - height - 6),
            ),
            (
                abs(endpoint.y() - box.bottom()),
                QPointF(endpoint.x() + 10, box.bottom() + 6),
            ),
        ]
        item.setPos(min(sides, key=lambda side: side[0])[1])
        self.decorations.append(item)

    @staticmethod
    def _midpoint(points: list[QPointF]) -> QPointF:
        """꺾은 선 전체 길이의 절반 지점. 두 끝점의 평균과는 다르다."""
        lengths = [hypot((b - a).x(), (b - a).y()) for a, b in pairwise(points)]
        remaining = sum(lengths) / 2
        for start, end, length in zip(points, points[1:], lengths):
            if length and remaining <= length:
                return start + (end - start) * (remaining / length)
            remaining -= length
        return points[0]

    def _label(self, text: str | None, center: QPointF) -> None:
        if not text:
            return
        item = RelationLabel(text, self)
        item.setBrush(INK)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        item.setPos(center - item.boundingRect().center())
        self.decorations.append(item)

    # ---------------------------------------------------------------- F4 상호작용

    def shape(self) -> QPainterPath:
        """얇은 선 주변도 클릭할 수 있게 클릭 판정 폭을 넓힌다."""
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0)
        shape = stroker.createStroke(self.path())
        if self.isSelected():
            for point in self.bends:
                shape.addEllipse(point, 8, 8)
            preview = self.preview_point()
            if preview is not None:
                shape.addEllipse(preview, 8, 8)
        return shape

    def boundingRect(self) -> QRectF:
        """넓힌 클릭 영역이 Qt의 후보 아이템 탐색에서도 포함되도록 한다."""
        return super().boundingRect().adjusted(-8, -8, 8, 8)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """왼쪽 클릭만 받는다. 아직 선 모드나 layout은 변경하지 않는다."""
        self.pressed = event.button() == Qt.MouseButton.LeftButton
        if self.pressed:
            self.dragged = False
            self.drag_index = next(
                (
                    index
                    for index, point in enumerate(self.bends)
                    if self.isSelected()
                    and hypot((point - event.pos()).x(), (point - event.pos()).y()) <= 8
                ),
                None,
            )
            preview = self.preview_point()
            self.drag_pending = (
                self.drag_index is None
                and self.isSelected()
                and preview is not None
                and hypot((preview - event.pos()).x(), (preview - event.pos()).y()) <= 8
            )
            self.original_bends = [QPointF(point) for point in self.bends]
            self.original_pending = self.pending_segment
            self.setSelected(True)
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self.pressed:
            event.ignore()
            return
        if self.drag_index is None and not self.drag_pending:
            event.accept()
            return
        distance = (
            event.screenPos() - event.buttonDownScreenPos(Qt.MouseButton.LeftButton)
        ).manhattanLength()
        if distance < QApplication.startDragDistance():
            event.accept()
            return
        if self.drag_pending:
            route = self._route()
            self.drag_index = self.pending_segment
            if self.drag_index is None:
                return
            self.bends = [QPointF(point) for point in route[1:-1]]
            self.bends.insert(self.drag_index, event.pos())
            self.pending_segment = None
            self.drag_pending = False
        self.dragged = True
        self.bends[self.drag_index] = event.pos()
        self.update_geometry()
        event.accept()

    @staticmethod
    def _segment_distance(point: QPointF, start: QPointF, end: QPointF) -> float:
        delta = end - start
        length_squared = delta.x() ** 2 + delta.y() ** 2
        offset = point - start
        ratio = (
            max(
                0.0,
                min(
                    1.0,
                    (offset.x() * delta.x() + offset.y() * delta.y()) / length_squared,
                ),
            )
            if length_squared
            else 0.0
        )
        distance = point - (start + delta * ratio)
        return hypot(distance.x(), distance.y())

    def _notify_bends(self) -> None:
        scene = self.scene()
        signals = getattr(scene, "signals", None)
        if signals is None:
            return
        key = self.relation.layout_key
        points = [(point.x(), point.y()) for point in self.bends]

        def notify_controller() -> None:
            try:
                if self.scene() is scene:
                    signals.edge_bent.emit(key, points)
            except RuntimeError:
                return

        QTimer.singleShot(0, notify_controller)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        if not self.bends:
            event.ignore()
            return
        menu = QMenu()
        remove = menu.addAction("가장 가까운 꺾임 제거")
        reset = menu.addAction("모든 꺾임 제거")
        nearest = min(
            range(len(self.bends)),
            key=lambda i: hypot(
                (self.bends[i] - event.pos()).x(), (self.bends[i] - event.pos()).y()
            ),
        )
        action = menu.exec(event.screenPos())
        if action == remove:
            self.bends.pop(nearest)
        elif action == reset:
            self.bends.clear()
        else:
            event.accept()
            return
        self.pending_segment = None
        self.update_geometry()
        self._notify_bends()
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """클릭은 가운데 조절점을 만들고, 점 드래그는 경유 위치를 저장한다."""
        if self.pressed and self.drag_index is not None and self.dragged:
            if event.screenPos() == event.buttonDownScreenPos(
                Qt.MouseButton.LeftButton
            ):
                self.bends = self.original_bends
                self.pending_segment = self.original_pending
                self.pressed = False
                self.drag_index = None
                self.update_geometry()
                event.accept()
                return
            self.bends[self.drag_index] = event.pos()
            self.update_geometry()
            self.pressed = False
            self.drag_index = None
            self._notify_bends()
            event.accept()
            return
        clicked = self.pressed and self.shape().contains(event.pos())
        self.pressed = False
        event.accept()
        if not clicked:
            return
        # 이미 있는 점을 클릭한 경우에는 경유점을 중복해서 만들지 않는다.
        if any(
            hypot((point - event.pos()).x(), (point - event.pos()).y()) <= 8
            for point in self.bends
        ):
            return
        route = self._route()
        index = min(
            range(len(route) - 1),
            key=lambda i: self._segment_distance(event.pos(), route[i], route[i + 1]),
        )
        self.pending_segment = index
        self.update_geometry()
