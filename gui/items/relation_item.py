"""관계선, 화살표 머리, 다중성 라벨. 담당: 이도훈 (F2).

상속 / 구현 / 연관 / 집합 / 합성 / 의존의 UML 표기를 그린다.
layout.edges의 모드에 따라 직선 또는 직각 꺾은 선으로 표시한다.
클릭은 장면의 edge_toggled 시그널로 전달한다.
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
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
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
    ) -> None:
        super().__init__()
        self.relation = relation
        self.source = source
        self.target = target
        self.mode = mode
        # 클래스 박스 뒤에 선을 놓아 박스 내부를 가리지 않게 한다.
        self.setZValue(-1)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        pen = QPen(INK, 1.4)
        if relation.kind in ("realization", "dependency"):
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.pressed = False
        self.decorations: list[QGraphicsItem] = []
        self.update_geometry()

    def _route(self) -> list[QPointF]:
        """장면 좌표로 시작점·꺾이는 점·끝점을 순서대로 반환한다."""
        source = self.source.mapRectToScene(self.source.rect)
        target = self.target.mapRectToScene(self.target.rect)
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
        elif kind in ("association", "dependency") and self.relation.directed:
            self._head(points[-1], points[-2], "open")

        self._label(
            self.relation.from_multiplicity, self._near_endpoint(points[0], points[1])
        )
        self._label(
            self.relation.to_multiplicity, self._near_endpoint(points[-1], points[-2])
        )
        self._label(self.relation.label, self._midpoint(points) + QPointF(0, -14))

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

    @staticmethod
    def _near_endpoint(point: QPointF, neighbor: QPointF) -> QPointF:
        """다중성 라벨을 끝점에서 선 안쪽으로, 선 옆으로 조금 띄운다."""
        delta = neighbor - point
        length = hypot(delta.x(), delta.y()) or 1
        unit = delta / length
        return point + unit * 40 + QPointF(-unit.y(), unit.x()) * 14

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

    def shape(self) -> QPainterPath:
        """얇은 선 주변도 클릭할 수 있게 클릭 판정 폭을 넓힌다."""
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0)
        return stroker.createStroke(self.path())

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-5, -5, 5, 5)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.pressed = event.button() == Qt.MouseButton.LeftButton
        if self.pressed:
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        clicked = self.pressed and self.shape().contains(event.pos())
        self.pressed = False
        event.accept()
        scene = self.scene()
        if not clicked or scene is None:
            return
        signals = getattr(scene, "signals", None)
        if signals is None:
            return
        layout_key = self.relation.layout_key

        def notify_controller() -> None:
            # 다른 입력이 먼저 장면을 다시 만들었으면 지난 클릭을 버린다.
            try:
                if self.scene() is scene:
                    signals.edge_toggled.emit(layout_key)
            except RuntimeError:
                # scene.clear()로 C++ 아이템이 이미 삭제된 경우다.
                return

        # 이벤트 처리 중 컨트롤러가 scene.clear()로 자신을 지우지 않게 한다.
        QTimer.singleShot(0, notify_controller)
