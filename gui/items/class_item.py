"""클래스 박스. 담당: 이도훈 (F1, F4).

이름 / 속성 / 메서드 3단으로 표시한다. enum의 속성 칸에는 값 목록을 넣는다.
static은 밑줄, abstract는 기울임으로 표시한다.
모델은 읽기만 하며, 위치 저장은 팩토리와 컨트롤러가 담당한다.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from gui.theme import canvas_color
from umlparser.model import ClassNode

PADDING = 12.0
MIN_WIDTH = 180.0
MIN_SECTION_HEIGHT = 30.0


class ClassItem(QGraphicsObject):
    """좌표 원점은 박스 왼쪽 위. 모델과 layout을 직접 수정하지 않는다."""

    # 실제 layout 갱신은 컨트롤러가 맡고, View는 변경 의도만 전달한다.
    moved = pyqtSignal(str, float, float)
    double_clicked = pyqtSignal(str)

    def __init__(self, node: ClassNode) -> None:
        super().__init__()
        self.node = node
        # DiagramScene.selected_class_ids()가 읽는 공통 선택 ID.
        self.setData(0, node.id)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        # 여러 클래스를 함께 옮길 때도 각각의 시작 위치를 비교한다.
        self.drag_positions: dict[ClassItem, QPointF] = {}
        self.setZValue(1)
        # 실제 글꼴 크기로 박스를 계산해 긴 이름과 멤버가 잘리지 않게 한다.
        self.sections = self._make_sections()
        self.section_heights = [
            max(
                MIN_SECTION_HEIGHT,
                2 * PADDING + sum(QFontMetricsF(font).height() for _, font in rows),
            )
            for rows in self.sections
        ]
        width = max(
            [MIN_WIDTH]
            + [
                QFontMetricsF(font).horizontalAdvance(text) + 2 * PADDING
                for rows in self.sections
                for text, font in rows
            ]
        )
        self.rect = QRectF(0, 0, width, sum(self.section_heights))

    @staticmethod
    def _font(
        *, bold: bool = False, italic: bool = False, underline: bool = False
    ) -> QFont:
        font = QFont()
        font.setPointSizeF(10)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        return font

    def _make_sections(self) -> list[list[tuple[str, QFont]]]:
        """각 칸에 표시할 (문자열, 글꼴) 목록을 만든다."""
        node = self.node
        header = []
        if node.kind in ("interface", "enum"):
            stereotype = "interface" if node.kind == "interface" else "enumeration"
            header.append((f"<<{stereotype}>>", self._font()))
        name = node.name
        if node.generics:
            name += "<" + ", ".join(node.generics) + ">"
        header.append((name, self._font(bold=True, italic=node.kind == "abstract")))

        # enum은 일반 속성 대신 선언된 값들을 순서대로 표시한다.
        attributes = []
        if node.kind == "enum":
            attributes = [(value, self._font()) for value in node.values]
        else:
            for attribute in node.attributes:
                text = attribute.visibility + attribute.name
                if attribute.type:
                    text += f": {attribute.type}"
                attributes.append((text, self._font(underline=attribute.is_static)))

        methods = []
        for method in node.methods:
            params = ", ".join(
                f"{p.name}: {p.type}" if p.type else p.name for p in method.params
            )
            text = f"{method.visibility}{method.name}({params})"
            if method.returns:
                text += f": {method.returns}"
            methods.append(
                (
                    text,
                    self._font(italic=method.is_abstract, underline=method.is_static),
                )
            )
        return [header, attributes, methods]

    def boundingRect(self) -> QRectF:
        """선 두께까지 포함한 그리기 영역. 선택 테두리가 잘리지 않게 한다."""
        return self.rect.adjusted(-2, -2, 2, 2)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setPen(QPen(canvas_color(self.scene(), "#334155"), 1.2))
        painter.setBrush(canvas_color(self.scene(), "#ffffff"))
        painter.drawRect(self.rect)
        # 이름 칸은 가운데 정렬, 속성·메서드 칸은 왼쪽 정렬한다.
        top = 0.0
        for index, (rows, height) in enumerate(
            zip(self.sections, self.section_heights)
        ):
            if index:
                painter.drawLine(
                    self.rect.topLeft() + QPointF(0, top),
                    self.rect.topRight() + QPointF(0, top),
                )
            y = top + PADDING
            for text, font in rows:
                painter.setFont(font)
                row_height = QFontMetricsF(font).height()
                alignment = (
                    Qt.AlignmentFlag.AlignHCenter
                    if index == 0
                    else Qt.AlignmentFlag.AlignLeft
                )
                painter.drawText(
                    QRectF(PADDING, y, self.rect.width() - 2 * PADDING, row_height),
                    alignment | Qt.AlignmentFlag.AlignVCenter,
                    text,
                )
                y += row_height
            top += height
        if self.isSelected():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#2563eb"), 2))
            painter.drawRect(self.rect)

    # ---------------------------------------------------------------- F4 상호작용

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Qt 기본 선택·드래그를 사용하고 이동 전 좌표만 보관한다."""
        super().mousePressEvent(event)
        scene = self.scene()
        # Qt의 기본 선택 처리가 끝난 뒤, 이번에 이동할 선택 항목을 저장한다.
        self.drag_positions.clear()
        if scene is not None and event.button() == Qt.MouseButton.LeftButton:
            for item in scene.selectedItems():
                if isinstance(item, ClassItem):
                    self.drag_positions[item] = QPointF(item.pos())

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """드래그가 끝났을 때 이동한 클래스만 컨트롤러에 알린다."""
        super().mouseReleaseEvent(event)
        # 단순 클릭은 moved를 보내지 않아 불필요한 Undo 기록을 만들지 않는다.
        moved_items = []
        for item, original in self.drag_positions.items():
            if item.pos() != original:
                moved_items.append((item, item.pos()))
        self.drag_positions.clear()
        # factory가 이 시그널을 지연 전달하므로 이벤트 도중 장면이 지워지지 않는다.
        for item, position in moved_items:
            item.moved.emit(item.node.id, position.x(), position.y())

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """클래스 ID만 전달한다. 원문 줄 찾기와 편집기 이동은 컨트롤러 역할이다."""
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.double_clicked.emit(self.node.id)
        else:
            super().mouseDoubleClickEvent(event)
