"""시퀀스 참여자와 메시지의 시간순 배치."""

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QBrush, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from gui.canvas import DiagramSignals
from gui.items.relation_item import INK
from gui.renderers.base import Diagram, DiagramRenderer
from gui.sequence_order import participant_key
from umlparser.edit import reorder_participants
from umlparser.sequence import Activation, Participant, Sequence, SequenceDocument
from umlparser.storage import Layout


class ParticipantItem(QGraphicsRectItem):
    """시퀀스 참여자의 머리 상자(또는 사람 모양). 좌우로 끌어 참여자 순서를 바꾼다."""

    def __init__(
        self,
        participant: Participant,
        width: float,
        spacing: float,
        signals: DiagramSignals,
    ) -> None:
        super().__init__(-width / 2, 0, width, 44)
        self.is_actor = participant.kind == "actor"
        if self.is_actor:
            self.setRect(-width / 2, -44, width, 88)
        self.key = participant_key(participant.id)
        self.setData(0, self.key)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.press_x = 0.0
        self.spacing = spacing
        self.first_x = width / 2
        self.signals = signals
        self.grab_offset = 0.0
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setToolTip("좌우로 드래그하여 참여자 순서를 변경합니다.")
        self.setBrush(QBrush(Qt.GlobalColor.white))
        caption = participant.label
        label = QGraphicsSimpleTextItem(caption, self)
        label.setPos(-label.boundingRect().width() / 2, 12)
        label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        label.setZValue(2)  # 글자가 활성 구간에 가려지지 않게 한다.
        self.setZValue(2)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """참여자를 상자로, actor는 사람 모양으로 그린다."""
        if not self.is_actor:
            super().paint(painter, option, widget)
            return
        painter.save()
        painter.setPen(QPen(INK, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, -35), 7, 7)
        body = QPainterPath(QPointF(0, -28))
        body.lineTo(0, -8)
        body.moveTo(-15, -22)
        body.lineTo(15, -22)
        body.moveTo(-13, 7)
        body.lineTo(0, -8)
        body.lineTo(13, 7)
        painter.drawPath(body)
        if self.isSelected() and widget is not None:
            painter.setPen(QPen(Qt.GlobalColor.blue, 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect())
        painter.restore()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """끌기를 시작할 때 누른 위치를 기억해 둔다."""
        super().mousePressEvent(event)
        self.press_x = event.scenePos().x()
        self.grab_offset = event.scenePos().x() - self.x()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """끄는 동안 참여자를 마우스를 따라 좌우로 움직인다."""
        self.setX(event.scenePos().x() - self.grab_offset)
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """끌기를 끝내면 놓인 열 번호를 컨트롤러에 알려 참여자 순서를 바꾸게 한다."""
        super().mouseReleaseEvent(event)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if abs(event.scenePos().x() - self.press_x) < 1:
            event.accept()
            return
        x = event.scenePos().x() - self.grab_offset
        column = round((x - self.first_x) / self.spacing)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        signals, key = self.signals, self.key
        QTimer.singleShot(0, lambda: signals.moved.emit(key, float(column), 0.0))
        event.accept()


ACTIVATION_WIDTH = 10.0
ACTIVATION_STEP = 5.0


class ActivationItem(QGraphicsRectItem):
    """생명선 위의 활성 구간. 머리 상자의 자식이라 드래그에 함께 움직인다."""

    def __init__(
        self,
        activation: Activation,
        top: float,
        bottom: float,
        parent: QGraphicsRectItem,
    ) -> None:
        left = -ACTIVATION_WIDTH / 2 + activation.depth * ACTIVATION_STEP
        super().__init__(left, top, ACTIVATION_WIDTH, bottom - top, parent)
        self.activation = activation
        self.setBrush(QBrush(Qt.GlobalColor.white))
        self.setPen(QPen(INK, 1.4))
        self.setZValue(1)  # 생명선 위, 참여자 이름 아래에 그린다.
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)


def is_closed(sequence: Sequence, activation: Activation) -> bool:
    """활성 구간이 `-`로 닫혔는지 알려 준다. 안 닫힌 구간은 마지막 메시지에서 끝난다."""
    last = len(sequence.messages) - 1
    if activation.end < last:
        return True
    message = sequence.messages[activation.end]
    if not message.deactivate or message.sender != activation.participant:
        return False
    # 마지막 메시지의 `-`는 같은 시점에 끝나는 구간 중 가장 안쪽 구간만 닫는다.
    deepest = max(
        a.depth
        for a in sequence.activations
        if a.participant == activation.participant and a.end == last
    )
    return activation.depth == deepest


def edge_offset(sequence: Sequence, name: str, index: int, toward_right: bool) -> float:
    """참여자가 활성 중이면 메시지 선을 생명선 중심에서 비껴 닿게 할 x 간격을 돌려준다.

    가장 깊은 활성 구간 기준이며, 활성이 아니면 0이다.
    """
    depths = [
        a.depth
        for a in sequence.activations
        if a.participant == name and a.start <= index <= a.end
    ]
    if not depths:
        return 0.0
    reach = ACTIVATION_WIDTH / 2 + max(depths) * ACTIVATION_STEP
    return reach if toward_right else -reach


def draw_sequence(
    scene: QGraphicsScene,
    sequence: Sequence,
    top: float,
    signals: DiagramSignals,
) -> None:
    """참여자 머리 상자·생명선·활성 구간과 시간순 메시지 화살표를 장면에 그린다."""
    metrics = QFontMetricsF(scene.font())
    width = max(
        [100.0]
        + [
            metrics.horizontalAdvance(p.label) + 80
            for p in sequence.participants.values()
        ]
    )
    spacing = max(
        [width + 48]
        + [metrics.horizontalAdvance(m.label) + 70 for m in sequence.messages]
    )
    columns = {}
    dashed = QPen(Qt.GlobalColor.darkGray)
    dashed.setStyle(Qt.PenStyle.DashLine)
    # 참여자를 코드의 순서대로 왼쪽부터 열로 나열한다.
    for index, participant in enumerate(sequence.participants.values()):
        x = width / 2 + index * spacing
        columns[participant.id] = x
        header = ParticipantItem(participant, width, spacing, signals)
        lifeline = QGraphicsLineItem(
            0, header.rect().bottom(), 0, 80 + 64 * len(sequence.messages), header
        )
        lifeline.setPen(dashed)
        lifeline.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        header.setPos(x, top)
        for activation in sequence.activations:
            if activation.participant != participant.id:
                continue
            # 활성 구간이 시작·끝 메시지의 높이에 걸치도록 위치를 정한다.
            first = 84 + 64 * activation.start
            last = 84 + 64 * activation.end
            if not is_closed(sequence, activation):
                last += 20
            ActivationItem(activation, first, last, header)
        scene.addItem(header)
    for row, message in enumerate(sequence.messages):
        start, end = columns[message.sender], columns[message.receiver]
        if start != end:
            # 메시지가 향하는 쪽으로 양 끝점을 각 참여자의 활성 깊이만큼 조정한다.
            rightward = end > start
            start += edge_offset(sequence, message.sender, row, rightward)
            end += edge_offset(sequence, message.receiver, row, not rightward)
        y = top + 84 + 64 * row
        pen = dashed if message.arrow.startswith("--") else QPen(Qt.GlobalColor.black)
        # 자기 자신에게 보내는 메시지는 옆으로 나갔다 돌아오는 고리로 그린다.
        if start == end:
            turn = start + 48
            scene.addLine(start, y, turn, y, pen)
            scene.addLine(turn, y, turn, y + 16, pen)
            start, y = turn, y + 16
        scene.addLine(start, y, end, y, pen)
        # 화살표 종류에 맞는 끝 모양(채운 삼각형, 열린 화살촉, X)을 그린다.
        direction = 1 if end > start else -1
        back = end - direction * 9
        if message.arrow.endswith(">>"):
            scene.addPolygon(
                QPolygonF(
                    [QPointF(end, y), QPointF(back, y - 5), QPointF(back, y + 5)]
                ),
                QPen(),
                QBrush(Qt.GlobalColor.black),
            )
        elif message.arrow.endswith(")"):
            scene.addLine(back, y - 5, end, y)
            scene.addLine(back, y + 5, end, y)
        elif message.arrow.endswith("x"):
            scene.addLine(end - 4, y - 4, end + 4, y + 4)
            scene.addLine(end - 4, y + 4, end + 4, y - 4)
        label = scene.addSimpleText(message.label, scene.font())
        label.setPos(
            min(start, end) + 6, top + 84 + 64 * row - label.boundingRect().height()
        )


class SequenceRenderer(DiagramRenderer):
    """시퀀스 다이어그램을 그리고, 참여자 이동을 원문의 선언 순서 변경으로 반영한다."""

    diagram_type = "sequence"

    def render(
        self,
        scene: QGraphicsScene,
        diagram: Diagram,
        layout: Layout,
        signals: DiagramSignals,
    ) -> None:
        """시퀀스 모델을 장면에 다시 그리고 선택했던 참여자의 선택을 되살린다."""
        if not isinstance(diagram, SequenceDocument):
            raise TypeError("시퀀스 모델이 필요합니다.")
        selected = {item.data(0) for item in scene.selectedItems()}
        scene.clear()
        draw_sequence(scene, diagram.sequence, 0, signals)
        for item in scene.items():
            if isinstance(item, ParticipantItem):
                item.setSelected(item.key in selected)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def moved_code(
        self, code: str, diagram: Diagram, node_id: str, x: float, y: float
    ) -> str | None:
        """참여자를 옮긴 결과를 선언 순서가 바뀐 새 원문으로 돌려준다."""
        if not isinstance(diagram, SequenceDocument) or not node_id.startswith(
            "sequence:"
        ):
            return code
        order = list(diagram.sequence.participants)
        name = node_id.removeprefix("sequence:")
        if name not in order:
            return code
        order.remove(name)
        order.insert(max(0, min(round(x), len(order))), name)
        return reorder_participants(code, order)
