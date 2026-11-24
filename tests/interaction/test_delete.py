"""선택 삭제와 원문, 이력, 키보드 포커스의 통합 검증."""

import os
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow
from umlparser import parse
from umlparser.storage import Layout, Project


@pytest.fixture
def window() -> Iterator[MainWindow]:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(restore_last=False)
    window.show()
    window.activateWindow()
    app.processEvents()
    yield window
    window.controller.timer.stop()
    window.controller.mark_saved("test.umlproj")
    window.close()
    app.processEvents()


def select(window: MainWindow, *names: str) -> None:
    for item in window.scene.items():
        if item.data(0) in names:
            item.setSelected(True)
    window.view.setFocus()
    QApplication.processEvents()


def test_class_delete_and_history(window: MainWindow) -> None:
    code = (
        "classDiagram\nclass A {\n +name: str\n}\nclass B\n"
        "A : +run()\n<<interface>> A\nA --> B\nB --> C\n"
    )
    window.controller.set_project(Project(code, Layout(), None))
    original = window.controller.snapshot()
    select(window, "A")
    QTest.keyClick(window.view, Qt.Key.Key_Delete)
    assert {n.id for n in window.controller.diagram.classes} == {"B", "C"}
    assert len(window.controller.diagram.relations) == 1
    assert "A" not in window.controller.project.layout.nodes
    assert window.controller.dirty
    window.controller.undo()
    assert window.controller.snapshot() == original
    window.controller.redo()
    assert "A" not in {n.id for n in window.controller.diagram.classes}


def test_implicit_peer_and_multiple_selection(window: MainWindow) -> None:
    window.controller.set_project(
        Project("classDiagram\nA --> B\nclass C\n", Layout(), None)
    )
    select(window, "A", "C")
    window.actions["delete"].trigger()
    assert {n.id for n in window.controller.diagram.classes} == {"B"}


def test_sequence_click_delete(window: MainWindow) -> None:
    code = (
        "sequenceDiagram\nparticipant A\nparticipant B\nparticipant C\n"
        "A->>+B: start\nB-->>-C: done\n"
    )
    window.controller.set_project(Project(code, Layout(), None))
    item = next(i for i in window.scene.items() if i.data(0) == "sequence:A")
    point = window.view.mapFromScene(item.mapToScene(item.rect().center()))
    QTest.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QApplication.processEvents()
    assert window.scene.selected_class_ids() == ["sequence:A"]
    QTest.keyClick(window.view, Qt.Key.Key_Delete)
    result = parse(window.controller.project.code)
    assert not result.errors
    assert set(result.sequence.participants) == {"B", "C"}
    assert len(result.sequence.messages) == 1
    assert not result.sequence.messages[0].deactivate
    window.controller.undo()
    assert window.controller.project.code == code


def test_editor_delete_and_invalid_code(window: MainWindow) -> None:
    window.controller.set_project(Project("classDiagram\nclass A\n", Layout(), None))
    select(window, "A")
    window.editor.setFocus()
    cursor = window.editor.textCursor()
    cursor.setPosition(0)
    window.editor.setTextCursor(cursor)
    QTest.keyClick(window.editor, Qt.Key.Key_Delete)
    assert window.editor.toPlainText().startswith("lassDiagram")
    before = window.controller.snapshot()
    window.view.setFocus()
    window.actions["delete"].trigger()
    assert window.controller.snapshot() == before
