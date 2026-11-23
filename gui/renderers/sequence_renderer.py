"""시퀀스 참여자와 메시지의 시간순 배치."""

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QBrush, QFontMetricsF, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
)

from gui.canvas import DiagramSignals
from gui.items.relation_item import INK
from gui.renderers.base import Diagram, DiagramRenderer
from gui.sequence_order import participant_key
from umlparser.edit import reorder_participants
from umlparser.sequence import Activation, Participant, Sequence, SequenceDocument
from umlparser.storage import Layout


class ParticipantItem(QGraphicsRectItem):
    def __init__(
        self,
        participant: Participant,
        width: float,
        spacing: float,
        signals: DiagramSignals,
    ) -> None:
        super().__init__(-width / 2, 0, width, 44)
        self.key = participant_key(participant.id)
        self.spacing = spacing
        self.first_x = width / 2
        self.signals = signals
        self.grab_offset = 0.0
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setToolTip("좌우로 드래그하여 참여자 순서를 변경합니다.")
        self.setBrush(QBrush(Qt.GlobalColor.white))
        caption = participant.label
        if participant.kind == "actor":
            caption = f"«actor» {caption}"
        label = QGraphicsSimpleTextItem(caption, self)
        label.setPos(-label.boundingRect().width() / 2, 12)
        label.setZValue(2)  # 활성 구간보다 위에 둔다.
        self.setZValue(2)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.grab_offset = event.scenePos().x() - self.x()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.setX(event.scenePos().x() - self.grab_offset)
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
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
        self.setZValue(1)  # 생명선 위, 머리 글자 아래
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)


def is_closed(sequence: Sequence, activation: Activation) -> bool:
    """끝 메시지에서 실제로 `-`로 닫힌 구간인지(닫히지 않은 구간은 마지막에서 끝남)."""
    last = len(sequence.messages) - 1
    if activation.end < last:
        return True
    message = sequence.messages[activation.end]
    if not message.deactivate or message.sender != activation.participant:
        return False
    # 마지막 메시지가 닫는 구간은 같은 끝 순번 중 가장 깊은 구간이다.
    deepest = max(
        a.depth
        for a in sequence.activations
        if a.participant == activation.participant and a.end == last
    )
    return activation.depth == deepest


def edge_offset(sequence: Sequence, name: str, index: int, toward_right: bool) -> float:
    """메시지 순번에 name이 활성 중이면 선이 닿을 활성 사각형 바깥 변의 x 오프셋."""
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
    # 열 순서는 코드의 참여자 순서(선언 또는 처음 등장한 순서)를 따른다.
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
            # 머리 상자 기준 좌표. 메시지 y는 top + 84 + 64 * 순번이다.
            first = 84 + 64 * activation.start
            last = 84 + 64 * activation.end
            if not is_closed(sequence, activation):
                last += 20
            ActivationItem(activation, first, last, header)
        scene.addItem(header)
    for row, message in enumerate(sequence.messages):
        start, end = columns[message.sender], columns[message.receiver]
        if start != end:
            # 활성 중인 쪽은 생명선 중심이 아니라 활성 사각형의 바깥 변에서 만난다.
            # 방향은 두 생명선의 원래 위치로 정한다.
            rightward = end > start
            start += edge_offset(sequence, message.sender, row, rightward)
            end += edge_offset(sequence, message.receiver, row, not rightward)
        y = top + 84 + 64 * row
        pen = dashed if message.arrow.startswith("--") else QPen(Qt.GlobalColor.black)
        if start == end:
            turn = start + 48
            scene.addLine(start, y, turn, y, pen)
            scene.addLine(turn, y, turn, y + 16, pen)
            start, y = turn, y + 16
        scene.addLine(start, y, end, y, pen)
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
    diagram_type = "sequence"

    def render(
        self,
        scene: QGraphicsScene,
        diagram: Diagram,
        layout: Layout,
        signals: DiagramSignals,
    ) -> None:
        if not isinstance(diagram, SequenceDocument):
            raise TypeError("시퀀스 모델이 필요합니다.")
        scene.clear()
        draw_sequence(scene, diagram.sequence, 0, signals)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def moved_code(
        self, code: str, diagram: Diagram, node_id: str, x: float, y: float
    ) -> str | None:
        # 시퀀스에서는 layout에 아무것도 저장하지 않고 코드만 고친다.
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
