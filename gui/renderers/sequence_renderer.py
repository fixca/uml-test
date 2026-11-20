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
from gui.renderers.base import Diagram, DiagramRenderer
from gui.sequence_order import ordered_ids, participant_key
from umlparser.sequence import Participant, Sequence, SequenceDocument
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


def draw_sequence(
    scene: QGraphicsScene,
    sequence: Sequence,
    top: float,
    layout: Layout,
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
    for index, name in enumerate(ordered_ids(sequence, layout)):
        participant = sequence.participants[name]
        x = width / 2 + index * spacing
        columns[participant.id] = x
        header = ParticipantItem(participant, width, spacing, signals)
        lifeline = QGraphicsLineItem(
            0, header.rect().bottom(), 0, 80 + 64 * len(sequence.messages), header
        )
        lifeline.setPen(dashed)
        lifeline.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        header.setPos(x, top)
        scene.addItem(header)
    for row, message in enumerate(sequence.messages):
        start, end = columns[message.sender], columns[message.receiver]
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
        draw_sequence(scene, diagram.sequence, 0, layout, signals)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
