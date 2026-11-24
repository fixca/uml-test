"""줄 번호와 진단을 표시하는 코드 편집기."""

from PyQt6.QtCore import QMimeData, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QPalette,
    QResizeEvent,
    QTextCharFormat,
    QTextCursor,
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
        self.document().blockCountChanged.connect(self.update_margin)
        self.updateRequest.connect(self.update_numbers)
        self.update_margin()

    def number_width(self) -> int:
        return 12 + self.fontMetrics().horizontalAdvance("9") * len(
            str(self.blockCount())
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Undo·Redo 단축키는 편집기 대신 앱 전체의 Undo·Redo 요청으로 보낸다."""
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo_requested.emit()
            event.accept()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self.redo_requested.emit()
            event.accept()
        elif event.text() == "{":
            self.insert_brace_pair()
            event.accept()
        elif event.text() == "}" and self.skip_closing_brace():
            event.accept()
        else:
            super().keyPressEvent(event)

    def insert_brace_pair(self) -> None:
        """`{`를 입력하면 `}`를 함께 넣고 커서를 둘 사이에 둔다."""
        cursor = self.textCursor()
        selected = cursor.selectedText()
        cursor.beginEditBlock()
        cursor.insertText("{" + selected + "}")
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def skip_closing_brace(self) -> bool:
        """커서 바로 뒤가 `}`이면 새로 넣지 않고 한 칸 건너뛴다."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        if self.document().characterAt(cursor.position()) != "}":
            return False
        cursor.movePosition(QTextCursor.MoveOperation.Right)
        self.setTextCursor(cursor)
        return True

    def insertFromMimeData(self, source: QMimeData) -> None:
        """붙여넣은 코드가 현재 문장과 합쳐지지 않도록 별도 줄에 삽입한다."""
        if not source.hasText() or not source.text():
            return
        text = source.text().replace("\r\n", "\n").replace("\r", "\n")
        cursor = self.textCursor()
        cursor.beginEditBlock()
        # 선택한 원문을 지우지 않도록 선택 영역의 마지막 줄 뒤에 붙인다.
        # 그 줄에 내용이 있으면 다음 줄에, 비었거나 공백뿐이면 그 줄에 붙인다.
        cursor.setPosition(cursor.selectionEnd())
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        if cursor.block().text().strip():
            cursor.insertText("\n")
        else:
            cursor.movePosition(
                QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()
        cursor.insertText(text.rstrip("\n"))
        if cursor.atEnd():
            cursor.insertText("\n")
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def update_margin(self, count: int = 0) -> None:
        """줄 번호가 들어갈 왼쪽 여백을 줄 수에 맞춰 넓히거나 좁힌다."""
        self.setViewportMargins(self.number_width(), 0, 0, 0)
        self.update_numbers_geometry()

    def update_numbers(self, rect: QRect, dy: int) -> None:
        """편집기가 스크롤되거나 갱신될 때 줄 번호 영역도 함께 갱신한다."""
        if dy:
            self.numbers.scroll(0, dy)
        else:
            self.numbers.update(0, rect.y(), self.number_width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_margin()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_numbers_geometry()

    def update_numbers_geometry(self) -> None:
        bounds = self.contentsRect()
        self.numbers.setGeometry(
            QRect(bounds.left(), bounds.top(), self.number_width(), bounds.height())
        )

    def paint_numbers(self, event: QPaintEvent) -> None:
        """화면에 보이는 줄마다 줄 번호를 그린다."""
        painter = QPainter(self.numbers)
        painter.fillRect(event.rect(), self.palette().color(QPalette.ColorRole.Window))
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
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
        """오류가 있는 줄에 물결 밑줄을 긋고 오류 메시지를 툴팁으로 보여 준다."""
        selections = []
        for line in sorted({error.line for error in errors}):
            block = self.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(block)
            cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            selection.cursor = cursor
            selection.format.setUnderlineStyle(
                QTextCharFormat.UnderlineStyle.WaveUnderline
            )
            selection.format.setUnderlineColor(QColor("#d32f2f"))
            if not cursor.hasSelection():
                selection.format.setBackground(QColor("#ffdddd"))
                selection.format.setProperty(
                    selection.format.Property.FullWidthSelection, True
                )
            selections.append(selection)
        self.setExtraSelections(selections)
        self.setToolTip("\n".join(f"{e.line}번째 줄: {e.message}" for e in errors))

    def goto_line(self, line: int) -> None:
        """지정한 줄(범위 밖이면 가까운 줄)로 커서를 옮기고 화면 가운데에 보인다."""
        block = self.document().findBlockByNumber(
            max(1, min(line, self.blockCount())) - 1
        )
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()
