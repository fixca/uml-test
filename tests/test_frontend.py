"""Qt 이벤트 루프와 실제 파서로 프론트엔드 흐름을 검증한다."""

import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QGraphicsItem, QGraphicsScene

from gui.canvas import DiagramScene
from gui.code_editor import CodeEditor
from gui.controller import Controller
from gui.main_window import ExportDialog, MainWindow
from umlparser.model import ClassDiagram, ParseError
from umlparser.storage import Layout, Project, StorageError


@pytest.fixture(scope="session")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def build(scene: QGraphicsScene, diagram: ClassDiagram, layout: Layout) -> None:
    scene.clear()
    for index, node in enumerate(diagram.classes):
        position = layout.nodes.setdefault(node.id, (index * 200.0, 0.0))
        item = scene.addRect(0, 0, 120, 80)
        item.setPos(*position)
        item.setData(0, node.id)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)


@pytest.fixture
def controller(app: QApplication) -> Iterator[Controller]:
    editor = CodeEditor()
    scene = DiagramScene()
    controller = Controller(editor, scene, build)
    controller.set_project(
        Project(
            "classDiagram\nclass User\nclass Admin\nUser --> Admin\n", Layout(), None
        )
    )
    yield controller
    controller.timer.stop()
    editor.deleteLater()
    scene.deleteLater()


def test_editor_lines_and_errors(app: QApplication) -> None:
    editor = CodeEditor()
    editor.setPlainText("a\nb\nc")
    editor.set_errors([ParseError(2, 1, "오류"), ParseError(99, 1, "범위 밖")])
    assert len(editor.extraSelections()) == 1
    editor.goto_line(2)
    assert editor.textCursor().blockNumber() == 1
    editor.goto_line(999)
    assert editor.textCursor().blockNumber() == 2
    editor.set_errors([])
    assert editor.extraSelections() == []
    editor.deleteLater()


def test_debounce_uses_latest_input(controller: Controller) -> None:
    controller.editor.setPlainText("classDiagram\nclass One")
    controller.editor.setPlainText("classDiagram\nclass Two")
    assert not controller.valid
    assert controller.history_index == 0
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()
    assert controller.valid
    assert [node.id for node in controller.diagram.classes] == ["Two"]
    assert controller.history_index == 1


def test_invalid_keeps_picture_and_blocks_mutations(controller: Controller) -> None:
    before = controller.snapshot()
    items = controller.scene.items()
    controller.editor.setPlainText("classDiagram\ninvalid !")
    controller.move_node("User", 44, 55)
    controller.flush()
    assert not controller.valid
    assert len(controller.scene.items()) == len(items)
    controller.toggle_edge("relation-4")
    assert not controller.paste_class("class X", (20, 20))
    assert controller.project.layout == before.layout
    assert len(controller.editor.extraSelections()) == 1


def test_unified_history_and_savepoint(controller: Controller) -> None:
    original = controller.snapshot()
    controller.editor.appendPlainText("class Guest")
    controller.flush()
    controller.scene.signals.moved.emit("User", 80, 90)
    assert controller.project.layout.nodes["User"] == (80, 90)
    controller.mark_saved("test.umlproj")
    assert not controller.dirty
    controller.undo()
    assert controller.dirty
    assert "Guest" in controller.project.code
    controller.undo()
    assert controller.snapshot() == original
    controller.redo()
    controller.redo()
    assert not controller.dirty


def test_pending_undo_and_redo_branch(controller: Controller) -> None:
    original = controller.project.code
    controller.editor.appendPlainText("class Guest")
    controller.undo()
    assert controller.project.code == original
    controller.editor.appendPlainText("class Other")
    controller.flush()
    controller.redo()
    assert "Other" in controller.project.code
    assert "Guest" not in controller.project.code


def test_signals_and_navigation(controller: Controller) -> None:
    key = controller.diagram.relations[0].layout_key
    controller.scene.signals.edge_toggled.emit(key)
    assert controller.project.layout.edges[key] == "orthogonal"
    controller.scene.signals.edge_toggled.emit(key)
    assert controller.project.layout.edges[key] == "straight"
    controller.scene.signals.double_clicked.emit("Admin")
    assert controller.editor.textCursor().blockNumber() == 2
    before = controller.snapshot()
    controller.move_node("missing", 0, 0)
    controller.move_node("User", float("nan"), 0)
    controller.toggle_edge("missing")
    assert before == controller.snapshot()


def test_paste_is_atomic_and_uses_new_ids(controller: Controller) -> None:
    block = controller.copy_class("User")
    assert block is not None
    assert controller.paste_class(block, (24, 24))
    assert controller.paste_class(block, (48, 48))
    assert controller.project.layout.nodes["User2"] == (24, 24)
    assert controller.project.layout.nodes["User3"] == (48, 48)
    controller.undo()
    assert "User3" not in controller.project.code
    before = controller.snapshot()
    assert not controller.paste_class("class A\nclass B", (1, 1))
    assert not controller.paste_class("nonsense !", (1, 1))
    assert not controller.paste_class("User: +foo", (1, 1))
    assert before == controller.snapshot()


def test_flush_preserves_selection(controller: Controller) -> None:
    item = controller.scene.items()[0]
    item.setSelected(True)
    controller.flush()
    assert controller.scene.selectedItems() == [item]


def test_history_limit(controller: Controller) -> None:
    for index in range(110):
        controller.move_node("User", index + 1, 50)
    assert len(controller.history) == 101
    for _ in range(100):
        controller.undo()
    assert controller.history_index == 0


def test_new_document_cancels_pending_input(controller: Controller) -> None:
    controller.editor.appendPlainText("class Abandoned")
    controller.set_project(Project("classDiagram\nclass New", Layout(), None))
    assert not controller.timer.isActive()
    assert not controller.dirty
    assert len(controller.history) == 1
    assert "Abandoned" not in controller.project.code


def test_window_file_save_and_failure(app: QApplication, tmp_path: Path) -> None:
    window = MainWindow(restore_last=False)
    window.controller.builder = build
    window.controller.validate()
    path = str(tmp_path / "test.umlproj")
    window.controller.project.path = path
    window.editor.appendPlainText("class Saved")
    with patch("gui.main_window.storage.set_last_path"):
        assert window.save_file()
        assert not window.controller.dirty
        assert window.load_path(path)
    assert "Saved" in window.editor.toPlainText()
    window.editor.appendPlainText("class Unsaved")
    with (
        patch("gui.main_window.storage.save", side_effect=StorageError("失敗")),
        patch("gui.main_window.QMessageBox.warning"),
    ):
        assert not window.save_file()
    assert window.controller.dirty
    window.controller.mark_saved(path)
    window.close()


def test_export_options(app: QApplication) -> None:
    window = MainWindow(restore_last=False)
    dialog = ExportDialog(window)
    assert dialog.options() == ("svg", 1.0)
    assert not dialog.scales.isEnabled()
    dialog.formats.setCurrentIndex(1)
    dialog.scales.setCurrentIndex(2)
    assert dialog.options() == ("png", 4.0)
    dialog.formats.setCurrentIndex(0)
    assert dialog.options() == ("svg", 1.0)
    window.close()


def test_editor_keyboard_undo_uses_unified_history(app: QApplication) -> None:
    window = MainWindow(restore_last=False)
    window.controller.builder = build
    window.controller.validate()
    original = window.editor.toPlainText()
    window.show()
    window.editor.setFocus()
    app.processEvents()
    window.editor.appendPlainText("class Keyboard")
    QTest.keyClick(window.editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.editor.toPlainText() == original
    QTest.keyClick(window.editor, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert "Keyboard" in window.editor.toPlainText()
    window.controller.mark_saved("test.umlproj")
    window.close()


@pytest.mark.parametrize("fail", [False, True])
def test_export_restores_selection(
    app: QApplication,
    tmp_path: Path,
    fail: bool,
) -> None:
    window = MainWindow(restore_last=False)
    window.controller.builder = build
    window.controller.validate()
    selected = window.scene.items()[0]
    selected.setSelected(True)
    path = tmp_path / "diagram.svg"

    def exporter(scene: QGraphicsScene, filename: str, fmt: str, scale: float) -> None:
        from umlparser.export import export_scene

        assert not scene.selectedItems()
        if fail:
            raise OSError("쓰기 실패")
        export_scene(scene, filename, fmt, scale)

    with (
        patch("gui.main_window.ExportDialog.exec", return_value=1),
        patch("gui.main_window.QFileDialog.exec", return_value=1),
        patch("gui.main_window.QFileDialog.selectedFiles", return_value=[str(path)]),
        patch("gui.main_window.export_scene", side_effect=exporter),
        patch("gui.main_window.QMessageBox.warning") as warning,
    ):
        window.export_file()
        assert warning.called == fail
    assert selected.isSelected()
    if not fail:
        assert "<svg" in path.read_text(encoding="utf-8")
    window.controller.mark_saved("test.umlproj")
    window.close()


def test_cancel_save_preserves_document(app: QApplication) -> None:
    from PyQt6.QtWidgets import QMessageBox

    window = MainWindow(restore_last=False)
    window.editor.appendPlainText("class Keep")
    before = window.editor.toPlainText()
    with patch(
        "gui.main_window.QMessageBox.exec",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        window.new_file()
        assert not window.close()
    assert window.editor.toPlainText() == before
    with (
        patch(
            "gui.main_window.QMessageBox.exec",
            return_value=QMessageBox.StandardButton.Save,
        ),
        patch("gui.main_window.QFileDialog.exec", return_value=0),
    ):
        window.new_file()
    assert window.editor.toPlainText() == before
    window.controller.mark_saved("test.umlproj")
    window.close()
