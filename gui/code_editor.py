"""줄 번호와 진단을 표시하는 코드 편집기."""

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QResizeEvent,
)
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from umlparser.model import ParseError


class LineNumbers(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.number_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:
        self.editor.paint_numbers(event)


class CodeEditor(QPlainTextEdit):
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setUndoRedoEnabled(False)
        self.numbers = LineNumbers(self)
        self.blockCountChanged.connect(self.update_margin)
        self.updateRequest.connect(self.update_numbers)
        self.update_margin()

    def number_width(self) -> int:
        return 12 + self.fontMetrics().horizontalAdvance("9") * len(
            str(self.blockCount())
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo_requested.emit()
            event.accept()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self.redo_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def update_margin(self, count: int = 0) -> None:
        self.setViewportMargins(self.number_width(), 0, 0, 0)

    def update_numbers(self, rect: QRect, dy: int) -> None:
        if dy:
            self.numbers.scroll(0, dy)
        else:
            self.numbers.update(0, rect.y(), self.number_width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_margin()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        bounds = self.contentsRect()
        self.numbers.setGeometry(
            QRect(bounds.left(), bounds.top(), self.number_width(), bounds.height())
        )

    def paint_numbers(self, event: QPaintEvent) -> None:
        painter = QPainter(self.numbers)
        painter.fillRect(event.rect(), QColor("#eeeeee"))
        painter.setPen(QColor("#555555"))
        block = self.firstVisibleBlock()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self.number_width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(block.blockNumber() + 1),
                )
            top += height
            block = block.next()

    def set_errors(self, errors: list[ParseError]) -> None:
        selections = []
        for line in sorted({error.line for error in errors}):
            block = self.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.cursor = self.textCursor()
            selection.cursor.setPosition(block.position())
            selection.format.setBackground(QColor("#ffdddd"))
            selection.format.setProperty(
                selection.format.Property.FullWidthSelection, True
            )
            selections.append(selection)
        self.setExtraSelections(selections)
        self.setToolTip("\n".join(f"{e.line}번째 줄: {e.message}" for e in errors))

    def goto_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(
            max(1, min(line, self.blockCount())) - 1
        )
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()
