"""줄 수가 바뀌어도 줄 번호 영역이 입력 영역을 가리지 않는지 검증한다."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSignalBlocker
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
