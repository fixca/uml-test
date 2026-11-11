"""메인 창과 파일·클립보드·내보내기 사용자 흐름."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsView,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from gui.canvas import DiagramScene
from gui.code_editor import CodeEditor
from gui.controller import Controller
from umlparser import storage
from umlparser.export import export_scene


class ExportDialog(QDialog):
    def __init__(self, parent: QMainWindow) -> None:
        super().__init__(parent)
        self.setWindowTitle("다이어그램 내보내기")
        self.formats = QComboBox(self)
        self.formats.addItems(["SVG", "PNG", "JPEG"])
        self.scales = QComboBox(self)
        self.scales.addItems(["1x", "2x", "4x"])
        self.scales.setEnabled(False)
        self.formats.currentIndexChanged.connect(self.format_changed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow("형식", self.formats)
        form.addRow("배율", self.scales)
        form.addRow(buttons)

    def format_changed(self, index: int) -> None:
        self.scales.setEnabled(index != 0)

    def options(self) -> tuple[str, float]:
        fmt = self.formats.currentText().lower()
        scale = (1.0, 2.0, 4.0)[self.scales.currentIndex()] if fmt != "svg" else 1.0
        return fmt, scale


class MainWindow(QMainWindow):
    def __init__(self, restore_last: bool = True) -> None:
        super().__init__()
        self.resize(1200, 800)
        self.editor = CodeEditor(self)
        self.scene = DiagramScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.view)
        splitter.setSizes([400, 800])
        self.setCentralWidget(splitter)
        self.controller = Controller(self.editor, self.scene)
        self.controller.status.connect(self.statusBar().showMessage)
        self.controller.changed.connect(self.update_state)
        self.actions: dict[str, QAction] = {}
        self.copy_origin: tuple[str, tuple[float, float]] | None = None
        self.create_menus()
        self.controller.set_project(storage.new_project())
        if restore_last:
            path = storage.last_path()
            if path and not self.load_path(path):
                self.statusBar().showMessage(
                    "마지막 파일을 열지 못해 새 문서를 열었습니다."
                )

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("파일")
        edit_menu = self.menuBar().addMenu("편집")
        view_menu = self.menuBar().addMenu("보기")
        entries = [
            (
                file_menu,
                "new",
                "새로 만들기",
                QKeySequence.StandardKey.New,
                self.new_file,
            ),
            (file_menu, "open", "열기…", QKeySequence.StandardKey.Open, self.open_file),
            (file_menu, "save", "저장", QKeySequence.StandardKey.Save, self.save_file),
            (
                file_menu,
                "save_as",
                "다른 이름으로 저장…",
                QKeySequence.StandardKey.SaveAs,
                self.save_as,
            ),
            (file_menu, "export", "내보내기…", "Ctrl+E", self.export_file),
            (
                edit_menu,
                "undo",
                "실행 취소",
                QKeySequence.StandardKey.Undo,
                self.controller.undo,
            ),
            (
                edit_menu,
                "redo",
                "다시 실행",
                QKeySequence.StandardKey.Redo,
                self.controller.redo,
            ),
            (edit_menu, "copy", "복사", QKeySequence.StandardKey.Copy, self.copy),
            (
                edit_menu,
                "paste",
                "붙여넣기",
                QKeySequence.StandardKey.Paste,
                self.paste,
            ),
            (
                view_menu,
                "zoom_in",
                "확대",
                QKeySequence.StandardKey.ZoomIn,
                self.zoom_in,
            ),
            (
                view_menu,
                "zoom_out",
                "축소",
                QKeySequence.StandardKey.ZoomOut,
                self.zoom_out,
            ),
            (view_menu, "fit", "화면 맞춤", "Ctrl+0", self.fit_view),
        ]
        for menu, name, title, shortcut, callback in entries:
            action = QAction(title, self)
            if isinstance(shortcut, QKeySequence.StandardKey):
                action.setShortcuts(QKeySequence.keyBindings(shortcut))
            else:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
            self.actions[name] = action
        self.actions["redo"].setShortcuts(
            [QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")]
            + QKeySequence.keyBindings(QKeySequence.StandardKey.Redo)
        )

    def update_state(self) -> None:
        controller = self.controller
        name = (
            Path(controller.project.path).name
            if controller.project.path
            else "제목 없음"
        )
        self.setWindowTitle(f"{name}{' ●' if controller.dirty else ''} — UML 도구")
        self.actions["undo"].setEnabled(
            controller.history_index > 0 or controller.timer.isActive()
        )
        self.actions["redo"].setEnabled(
            controller.history_index + 1 < len(controller.history)
            and not controller.timer.isActive()
        )
        self.actions["export"].setEnabled(controller.valid and controller.rendered)

    def confirm_discard(self) -> bool:
        if not self.controller.dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("미저장 변경")
        box.setText("변경 내용을 저장하시겠습니까?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.button(QMessageBox.StandardButton.Save).setText("저장")
        box.button(QMessageBox.StandardButton.Discard).setText("저장 안 함")
        box.button(QMessageBox.StandardButton.Cancel).setText("취소")
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        result = box.exec()
        if result == QMessageBox.StandardButton.Save:
            return self.save_file()
        return result == QMessageBox.StandardButton.Discard

    def new_file(self) -> None:
        if self.confirm_discard():
            self.controller.set_project(storage.new_project())
            self.remember_path("")

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "프로젝트 열기", "", "UML (*.umlproj)"
        )
        if path and self.confirm_discard():
            self.load_path(path)

    def load_path(self, path: str) -> bool:
        try:
            project = storage.load(path)
        except storage.StorageError as error:
            QMessageBox.warning(self, "열기 실패", str(error))
            return False
        self.controller.set_project(project)
        self.remember_path(path)
        return True

    def remember_path(self, path: str) -> None:
        try:
            storage.set_last_path(path)
        except storage.StorageError as error:
            self.statusBar().showMessage(f"최근 파일 기록 실패: {error}")

    def save_as(self) -> bool:
        return self.save_file(force_dialog=True)

    def save_file(self, checked: bool = False, *, force_dialog: bool = False) -> bool:
        self.controller.flush()
        path = self.controller.project.path
        if force_dialog or not path:
            dialog = QFileDialog(self, "프로젝트 저장", path or "제목 없음.umlproj")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setNameFilter("UML (*.umlproj)")
            dialog.setDefaultSuffix("umlproj")
            if not dialog.exec():
                return False
            path = dialog.selectedFiles()[0]
        try:
            storage.save(self.controller.project, path)
        except storage.StorageError as error:
            QMessageBox.warning(self, "저장 실패", str(error))
            return False
        self.controller.mark_saved(path)
        self.statusBar().showMessage("저장했습니다.")
        self.remember_path(path)
        return True

    def export_file(self) -> None:
        self.controller.flush()
        if not self.controller.valid or not self.controller.rendered:
            return
        options = ExportDialog(self)
        if options.exec() != QDialog.DialogCode.Accepted:
            return
        fmt, scale = options.options()
        dialog = QFileDialog(self, "내보내기", f"diagram.{fmt}")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter(f"{fmt.upper()} (*.{fmt})")
        dialog.setDefaultSuffix(fmt)
        if not dialog.exec():
            return
        selection = self.scene.selectedItems()
        self.scene.clearSelection()
        try:
            export_scene(self.scene, dialog.selectedFiles()[0], fmt, scale)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "내보내기 실패", str(error))
        else:
            self.statusBar().showMessage("내보냈습니다.")
        finally:
            for item in selection:
                item.setSelected(True)

    def copy(self) -> None:
        if self.editor.hasFocus():
            self.editor.copy()
            return
        selected = self.scene.selected_class_ids()
        if len(selected) != 1:
            self.statusBar().showMessage("복사할 클래스를 하나 선택하세요.")
            return
        block = self.controller.copy_class(selected[0])
        if block is not None:
            QApplication.clipboard().setText(block)
            position = self.controller.project.layout.nodes.get(selected[0], (0.0, 0.0))
            self.copy_origin = (block, position)

    def paste(self) -> None:
        if self.editor.hasFocus():
            self.editor.paste()
            return
        block = QApplication.clipboard().text()
        if not block:
            return
        origin = self.view.mapToScene(self.view.viewport().rect().center())
        position = (origin.x(), origin.y())
        if self.copy_origin is not None and self.copy_origin[0] == block:
            position = self.copy_origin[1]
        destination = (position[0] + 24, position[1] + 24)
        if self.controller.paste_class(block, destination):
            self.copy_origin = (block, destination)

    def zoom_in(self) -> None:
        if self.view.transform().m11() < 4:
            self.view.scale(1.2, 1.2)

    def zoom_out(self) -> None:
        if self.view.transform().m11() > 0.1:
            self.view.scale(1 / 1.2, 1 / 1.2)

    def fit_view(self) -> None:
        if not self.scene.itemsBoundingRect().isEmpty():
            self.view.fitInView(
                self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.confirm_discard():
            self.controller.timer.stop()
            event.accept()
        else:
            event.ignore()
