"""일반 숫자열 키의 확대·축소를 모든 다이어그램에서 검증한다."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow
from umlparser.storage import Layout, Project


@pytest.mark.parametrize(
    "code", ["classDiagram\nA --> B\n", "sequenceDiagram\nA->>B: call\n"]
)
@pytest.mark.parametrize("focus", ["editor", "view"])
@pytest.mark.parametrize(
    "key, modifiers",
    [
        (Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier),
        (
            Qt.Key.Key_Equal,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        ),
        (
            Qt.Key.Key_Plus,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        ),
    ],
)
def test_number_row_zoom(
    code: str, focus: str, key: Qt.Key, modifiers: Qt.KeyboardModifier
) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(restore_last=False)
    window.controller.set_project(Project(code, Layout(), None))
    window.show()
    window.activateWindow()
    widget = window.editor if focus == "editor" else window.view
    widget.setFocus()
    app.processEvents()
    try:
        before = window.view.transform().m11()
        QTest.keyClick(widget, key, modifiers)
        assert window.view.transform().m11() == pytest.approx(before * 1.2)
        QTest.keyClick(widget, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        assert window.view.transform().m11() == pytest.approx(before)
        assert window.editor.toPlainText() == code
    finally:
        window.controller.mark_saved("test.umlproj")
        window.controller.timer.stop()
        window.close()
        app.processEvents()
