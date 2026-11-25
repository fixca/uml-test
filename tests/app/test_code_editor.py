"""줄 수가 바뀌어도 줄 번호 영역이 입력 영역을 가리지 않는지 검증한다."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QMimeData, QSignalBlocker, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui.code_editor import CodeEditor


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def assert_aligned(editor: CodeEditor) -> None:
    assert editor.viewportMargins().left() == editor.number_width()
    assert editor.numbers.geometry().width() == editor.number_width()


def test_margin_follows_blocked_set_plain_text(app: QApplication) -> None:
    editor = CodeEditor()
    editor.resize(400, 300)
    editor.show()
    with QSignalBlocker(editor):
        editor.setPlainText("\n".join(f"line {i}" for i in range(28)))
    app.processEvents()
    assert editor.blockCount() == 28
    assert_aligned(editor)

    with QSignalBlocker(editor):
        editor.setPlainText("a\nb\nc")
    app.processEvents()
    assert editor.blockCount() == 3
    assert_aligned(editor)


@pytest.mark.parametrize("offset", [0, 3, 7])
@pytest.mark.parametrize(
    "code, fragment",
    [
        ("classDiagram\nclass A\n", "class B"),
        ("sequenceDiagram\nA->>B: hi\n", "B-->>A: reply"),
    ],
)
def test_paste_after_line_not_inside_statement(
    app: QApplication, offset: int, code: str, fragment: str
) -> None:
    from umlparser import parse

    editor = CodeEditor()
    editor.setPlainText(code)
    cursor = editor.textCursor()
    cursor.setPosition(code.index("\n") + 1 + offset)
    editor.setTextCursor(cursor)
    mime = QMimeData()
    mime.setText(fragment)
    editor.insertFromMimeData(mime)
    assert editor.toPlainText() == code.rstrip("\n") + "\n" + fragment + "\n"
    assert not parse(editor.toPlainText()).errors
    editor.deleteLater()


def test_paste_blank_line_and_selection_preserve_original(app: QApplication) -> None:
    from PyQt6.QtGui import QTextCursor

    editor = CodeEditor()
    editor.setPlainText("classDiagram\nclass A\n   ")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    mime = QMimeData()
    mime.setText("class B\r\nclass C\r\n")
    editor.insertFromMimeData(mime)
    assert editor.toPlainText() == "classDiagram\nclass A\nclass B\nclass C\n"
    cursor.setPosition(15)
    cursor.setPosition(18, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    mime.setText("class D")
    editor.insertFromMimeData(mime)
    assert "class A\nclass D\nclass B" in editor.toPlainText()
    editor.deleteLater()


def test_open_brace_inserts_pair(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClicks(editor, "{")
    assert editor.toPlainText() == "{}"
    assert editor.textCursor().position() == 1


def test_open_brace_after_text(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClicks(editor, "class A {")
    assert editor.toPlainText() == "class A {}"
    assert editor.textCursor().position() == len("class A {")


def test_closing_brace_skips_over_existing(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClicks(editor, "{}")
    assert editor.toPlainText() == "{}"
    assert editor.textCursor().position() == 2


def test_open_brace_wraps_selection(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("abc")
    editor.selectAll()
    QTest.keyClicks(editor, "{")
    assert editor.toPlainText() == "{abc}"
    assert editor.textCursor().position() == 4


def test_closing_brace_inserted_when_next_is_not_brace(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClicks(editor, "}")
    assert editor.toPlainText() == "}"


def test_tab_inserts_four_spaces(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == "    "
    assert editor.textCursor().position() == 4
    assert "\t" not in editor.toPlainText()


def test_tab_after_text(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClicks(editor, "abc")
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == "abc    "


def test_tab_replaces_selection(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("abc")
    editor.selectAll()
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == "    "


def test_backspace_removes_tab_indent(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == ""


def test_backspace_removes_indent_after_text(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClicks(editor, "abc")
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == "abc"


def test_backspace_removes_only_one_indent(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == "    "


def test_backspace_removes_one_space_when_fewer_than_four(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClicks(editor, "  ")
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == " "


def test_backspace_removes_only_selection(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("    ")
    editor.selectAll()
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == ""
    editor.setPlainText("     ")
    cursor = editor.textCursor()
    cursor.setPosition(1, cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == "    "


def test_backspace_at_line_start_joins_lines(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("a\nb")
    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == "ab"


def set_cursor(editor: CodeEditor, position: int) -> None:
    cursor = editor.textCursor()
    cursor.setPosition(position)
    editor.setTextCursor(cursor)


def test_backspace_ignores_spaces_after_cursor_in_rtl_line(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("אבגxא    ")
    set_cursor(editor, 5)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == "אבגx    "


def test_backspace_removes_indent_before_text_in_rtl_line(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("אבג    xyz")
    set_cursor(editor, 7)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == "אבגxyz"


def test_open_brace_cursor_is_logical_after_rtl_text(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("אבג")
    set_cursor(editor, 3)
    QTest.keyClicks(editor, "{")
    assert editor.toPlainText() == "אבג{}"
    assert editor.textCursor().position() == 4


def test_closing_brace_skip_is_logical_in_rtl_line(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("אבג{}")
    set_cursor(editor, 4)
    QTest.keyClicks(editor, "}")
    assert editor.toPlainText() == "אבג{}"
    assert editor.textCursor().position() == 5


def test_shift_tab_does_not_insert_spaces(app: QApplication) -> None:
    editor = CodeEditor()
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert editor.toPlainText() == ""


def test_shift_tab_keeps_selection_text(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("abc")
    editor.selectAll()
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert editor.toPlainText() == "abc"
