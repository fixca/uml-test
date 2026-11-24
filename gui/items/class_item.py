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

from umlparser.model import ClassNode

PADDING = 12.0
MIN_WIDTH = 180.0
MIN_SECTION_HEIGHT = 30.0


class ClassItem(QGraphicsObject):
    """클래스 하나를 이름·속성·메서드 3단 박스로 그리고, 끌어서 옮긴 결과를 알린다.

    좌표 원점은 박스 왼쪽 위이며 모델과 layout은 직접 수정하지 않는다.
    """

    # 위치 변경과 더블클릭을 알리는 시그널. layout 갱신은 컨트롤러가 맡는다.
    moved = pyqtSignal(str, float, float)
    double_clicked = pyqtSignal(str)

    def __init__(self, node: ClassNode) -> None:
        super().__init__()
        self.node = node
        # DiagramScene.selected_class_ids()가 찾을 수 있도록 클래스 ID를 붙인다.
        self.setData(0, node.id)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        # 끌기 전 위치를 보관해, 실제로 옮겨진 클래스만 알릴 수 있게 한다.
        self.drag_positions: dict[ClassItem, QPointF] = {}
        self.setZValue(1)
        # 긴 이름과 멤버도 잘리지 않도록 글꼴 크기에 맞춰 박스 크기를 정한다.
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
        """클래스 박스에 쓰는 글꼴을 굵기·기울임·밑줄 설정에 맞춰 만든다."""
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

        # 속성 칸에는 enum이면 값 목록을, 그 외에는 속성을 표시한다.
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
        painter.setPen(QPen(QColor("#334155"), 1.2))
        painter.setBrush(QColor("white"))
        painter.drawRect(self.rect)
        # 세 칸을 구분선으로 나누어 그린다. (이름 칸은 가운데, 나머지는 왼쪽 정렬)
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
        """클릭한 클래스를 선택하고, 끌기 전 위치를 선택된 클래스마다 보관해 둔다."""
        super().mousePressEvent(event)
        scene = self.scene()
        # 선택 처리가 끝난 뒤의 선택 항목이 이번에 함께 움직일 대상이다.
        self.drag_positions.clear()
        if scene is not None and event.button() == Qt.MouseButton.LeftButton:
            for item in scene.selectedItems():
                if isinstance(item, ClassItem):
                    self.drag_positions[item] = QPointF(item.pos())

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """끌기가 끝나면 위치가 바뀐 클래스의 새 좌표만 컨트롤러에 알린다."""
        super().mouseReleaseEvent(event)
        # 클릭만 한 클래스는 알리지 않아 불필요한 Undo 기록을 막는다.
        moved_items = []
        for item, original in self.drag_positions.items():
            if item.pos() != original:
                moved_items.append((item, item.pos()))
        self.drag_positions.clear()
        # 알림은 지연 전달되므로 마우스 이벤트 도중 장면이 다시 그려지지 않는다.
        for item, position in moved_items:
            item.moved.emit(item.node.id, position.x(), position.y())

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """더블클릭한 클래스의 ID를 알려 편집기가 그 정의로 이동하게 한다."""
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.double_clicked.emit(self.node.id)
        else:
            super().mouseDoubleClickEvent(event)
