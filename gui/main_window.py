"""메인 창과 파일·클립보드·내보내기 사용자 흐름."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QKeySequence,
    QPainter,
    QPalette,
)
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

from gui.canvas import DiagramScene, DiagramView
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
        """SVG는 배율이 필요 없으므로 래스터 형식일 때만 배율 선택을 켠다."""
        self.scales.setEnabled(index != 0)

    def options(self) -> tuple[str, float]:
        """선택한 내보내기 형식과 배율을 돌려준다. SVG의 배율은 항상 1이다."""
        fmt = self.formats.currentText().lower()
        scale = (1.0, 2.0, 4.0)[self.scales.currentIndex()] if fmt != "svg" else 1.0
        return fmt, scale


class MainWindow(QMainWindow):
    def __init__(self, restore_last: bool = True) -> None:
        super().__init__()
        self.resize(1200, 800)
        self.editor = CodeEditor(self)
        self.scene = DiagramScene(self)
        self.view = DiagramView(self.scene, self)
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
        self.apply_light_theme()
        self.controller.set_project(storage.new_project())
        if restore_last:
            path = storage.last_path()
            if path and not self.load_path(path):
                self.statusBar().showMessage(
                    "마지막 파일을 열지 못해 새 문서를 열었습니다."
                )

    def apply_light_theme(self) -> None:
        """운영체제 설정과 관계없이 라이트 팔레트를 사용한다."""
        background, base, foreground, button = (
            "#f3f4f6",
            "#ffffff",
            "#202124",
            "#e5e7eb",
        )
        palette = QPalette(self.palette())
        for role, color in (
            (QPalette.ColorRole.Window, background),
            (QPalette.ColorRole.Base, base),
            (QPalette.ColorRole.AlternateBase, button),
            (QPalette.ColorRole.WindowText, foreground),
            (QPalette.ColorRole.Text, foreground),
            (QPalette.ColorRole.Button, button),
            (QPalette.ColorRole.ButtonText, foreground),
            (QPalette.ColorRole.ToolTipBase, background),
            (QPalette.ColorRole.ToolTipText, foreground),
            (QPalette.ColorRole.Highlight, "#2563eb"),
            (QPalette.ColorRole.HighlightedText, "#ffffff"),
        ):
            palette.setColor(role, QColor(color))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QMainWindow, QMenuBar, QMenu, QStatusBar, QSplitter {{
                background-color: {background}; color: {foreground};
            }}
            QMenuBar::item:selected, QMenu::item:selected {{
                background-color: #2563eb; color: white;
            }}
            QPlainTextEdit {{ background-color: {base}; color: {foreground}; }}
            QSplitter::handle {{ background-color: {button}; }}
            QSplitter::handle:hover {{ background-color: #2563eb; }}
            QGraphicsView {{ background-color: {base}; }}
        """)
        self.view.setBackgroundBrush(QColor(base))
        self.scene.setBackgroundBrush(QColor(base))
        self.editor.numbers.update()

    def create_menus(self) -> None:
        """파일·편집·보기 메뉴와 단축키를 만들고 각 항목을 동작에 연결한다."""
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
            (edit_menu, "delete", "삭제", "Delete", self.delete),
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

        # 숫자패드가 없어도 Ctrl+= / Ctrl+- 로 확대·축소하고 표준 키도 유지한다.
        for name, shortcuts in (
            ("zoom_in", ["Ctrl+=", "Ctrl++", "Ctrl+Shift+=", "Ctrl+Shift++"]),
            ("zoom_out", ["Ctrl+-"]),
        ):
            bindings = [QKeySequence(key) for key in shortcuts] + self.actions[
                name
            ].shortcuts()
            unique = {binding.toString(): binding for binding in bindings}
            self.actions[name].setShortcuts(list(unique.values()))

    def update_state(self) -> None:
        """창 제목과 Undo·Redo·내보내기 메뉴의 사용 가능 여부를 현재 상태에 맞춘다."""
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
        """미저장 변경이 있으면 저장 여부를 물어, 현재 작업을 닫아도 되는지 돌려준다."""
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
        """변경 사항을 정리한 뒤 예시 원문이 든 새 문서로 바꾼다."""
        if self.confirm_discard():
            self.controller.set_project(storage.new_project())
            self.remember_path("")

    def open_file(self) -> None:
        """파일 선택 창에서 고른 프로젝트를 연다."""
        path, _ = QFileDialog.getOpenFileName(
            self, "프로젝트 열기", "", "UML (*.umlproj)"
        )
        if path and self.confirm_discard():
            self.load_path(path)

    def load_path(self, path: str) -> bool:
        """지정한 경로의 프로젝트를 연다. 실패하면 오류 창을 띄우고 False를 돌려준다."""
        try:
            project = storage.load(path)
        except storage.StorageError as error:
            QMessageBox.warning(self, "열기 실패", str(error))
            return False
        self.controller.set_project(project)
        self.remember_path(path)
        return True

    def remember_path(self, path: str) -> None:
        """다음 실행 때 다시 열 수 있도록 마지막으로 연 파일 경로를 기록한다."""
        try:
            storage.set_last_path(path)
        except storage.StorageError as error:
            self.statusBar().showMessage(f"최근 파일 기록 실패: {error}")

    def save_as(self) -> bool:
        """항상 저장 경로를 새로 물어 프로젝트를 저장한다."""
        return self.save_file(force_dialog=True)

    def save_file(self, checked: bool = False, *, force_dialog: bool = False) -> bool:
        """프로젝트를 저장하고 성공 여부를 돌려준다. 경로가 없으면 먼저 묻는다."""
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
        """현재 그림을 사용자가 고른 형식과 배율로 파일에 내보낸다."""
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
        # 선택 표시가 내보낸 그림에 나오지 않도록 잠시 해제했다가 되돌린다.
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
        """편집기에서는 글자를, 그림에서는 선택한 클래스 하나를 복사한다."""
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

    def delete(self) -> None:
        """편집기에서는 선택한 글자(선택이 없으면 커서 뒤 한 글자)를 지운다.

        그림에서는 선택한 항목을 지운다.
        """
        if self.editor.hasFocus():
            cursor = self.editor.textCursor()
            cursor.deleteChar()
            self.editor.setTextCursor(cursor)
            return
        self.controller.delete_selected()

    def paste(self) -> None:
        """편집기에서는 글자를, 그림에서는 클립보드의 클래스를 붙여넣는다.

        같은 블록을 거듭 붙이면 이전 붙인 위치에서 조금씩 비껴 놓는다.
        """
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
        self.view.zoom_by(1)

    def zoom_out(self) -> None:
        self.view.zoom_by(-1)

    def fit_view(self) -> None:
        """그려진 모든 요소가 보이도록 화면 배율과 위치를 맞춘다."""
        if not self.scene.itemsBoundingRect().isEmpty():
            self.view.fitInView(
                self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        """미저장 변경을 확인한 뒤에만 창을 닫는다."""
        if self.confirm_discard():
            self.controller.timer.stop()
            event.accept()
        else:
            event.ignore()
