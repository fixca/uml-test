"""Windows/macOS PyQt6 desktop shell, document tabs and native menus."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import logging
from pathlib import Path
import sys
from PyQt6.QtCore import QObject, Qt, QSignalBlocker, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QKeySequence, QColor
from PyQt6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QSplitter, QTabWidget, QVBoxLayout, QWidget)
from diagram_editor.application.document_session import DocumentSession, DEFAULT_CLASS, DEFAULT_SEQUENCE
from diagram_editor.application.autosave_coordinator import AutosavePolicy, ValidationPolicy
from diagram_editor.core.domain.models import Snapshot, ValidationState
from diagram_editor.modules.persistence.repository import ProjectRepository, RecoveryRepository
from diagram_editor.modules.persistence.archive_codec import write_atomic, ArchiveError
from diagram_editor.modules.export.qt_exporter import ExportOptions, ExporterRegistry
from diagram_editor.modules.mermaid.source_sync import SourceSyncError
from diagram_editor.platform.save_worker import SaveWorker
from diagram_editor.presentation.pyqt.diagram_view import DiagramView


class UiSignals(QObject):
    parseReady = pyqtSignal(str, int, object)
    saveReady = pyqtSignal(str, str, int, bool, str, str)


class CodeEditor(QPlainTextEdit):
    """Disable Qt's separate undo timeline; the DocumentSession owns history."""
    undoRequested = pyqtSignal()
    redoRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUndoRedoEnabled(False)
        self.setFont(QFont("Monospace", 10))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setPlaceholderText("Mermaid 코드를 입력하세요")
        self.setStyleSheet("QPlainTextEdit {background:#141e30;color:#e6eefa;border:0;padding:12px;selection-background-color:#335a99;}")

    def keyPressEvent(self, event):
        control = Qt.KeyboardModifier.ControlModifier if sys.platform != "darwin" else Qt.KeyboardModifier.MetaModifier
        if event.modifiers() & control and event.key() == Qt.Key.Key_Z:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.redoRequested.emit()
            else:
                self.undoRequested.emit()
            event.accept()
            return
        if event.modifiers() & control and event.key() == Qt.Key.Key_Y:
            self.redoRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class EditorTab(QWidget):
    def __init__(self, session: DocumentSession, owner: "MainWindow"):
        super().__init__(owner)
        self.session = session
        self.owner = owner
        self._closed = False
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(AutosavePolicy().debounce_ms)
        self.autosave_timer.timeout.connect(self._autosave)
        self.retry_attempt = 0
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self._autosave)
        self.parse_timer = QTimer(self)
        self.parse_timer.setSingleShot(True)
        self.parse_timer.setInterval(ValidationPolicy().debounce_ms)
        self.parse_timer.timeout.connect(self._start_parse)
        self._subscriptions: list = []
        self.worker = SaveWorker(owner.project_repo, owner.recovery_repo,
            lambda kind, rev, ok, message, path: owner.signals.saveReady.emit(session.document_id, kind, rev, ok, message, path))
        self.code = CodeEditor(self)
        self.view = DiagramView(self)
        self.code.setPlainText(session.source)
        self.code.textChanged.connect(self._source_changed)
        self.code.undoRequested.connect(owner.undo)
        self.code.redoRequested.connect(owner.redo)
        self.view.nodesMoved.connect(self._nodes_moved)
        self.view.requestAdd.connect(owner.add_node)
        self.view.selectionUpdated.connect(owner.refresh_status)
        self.diagnostics = QLabel("", self)
        self.diagnostics.setStyleSheet("color:#ffb49f; background:#1b2538; padding:7px 12px;")
        self.diagnostics.setWordWrap(True)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.code)
        self.splitter.addWidget(self.view)
        self.splitter.setSizes([440, 740])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(self.splitter)
        layout.addWidget(self.diagnostics)
        for topic in ("SourceChanged", "DocumentChanged", "ValidationStarted",
                      "ValidationSucceeded", "ValidationFailed"):
            self._subscriptions.append(session.bus.subscribe(topic, self._on_event))
        self.sync_ui()
        QTimer.singleShot(100, self.view.fit_all)

    def _on_event(self, event):
        if event.document_id != self.session.document_id:
            return
        if event.name in ("SourceChanged", "DocumentChanged"):
            self.retry_timer.stop()
            self.autosave_timer.start()
        if event.name == "SourceChanged":
            if self.code.toPlainText() != self.session.source:
                with QSignalBlocker(self.code):
                    self.code.setPlainText(self.session.source)
            # GUI source patch commits are already VALID, so do not parse again.
            if self.session.status == ValidationState.VALIDATING:
                self.parse_timer.start()
        self.sync_ui()

    def _source_changed(self):
        if self.session.begin_source_edit(self.code.toPlainText()):
            self.view.set_editable(False)

    def _start_parse(self):
        rev = self.session.source_revision
        source = self.session.source
        previous = deepcopy(self.session.document)
        parser = self.session.parser
        future = self.owner.parse_executor.submit(parser.parse, source, previous)
        def complete(future):
            try: result = future.result()
            except Exception as exc: result = exc
            if not self._closed and not self.owner._closing:
                self.owner.signals.parseReady.emit(self.session.document_id, rev, result)
        future.add_done_callback(complete)

    def _autosave(self):
        self.worker.submit_recovery(self.session.snapshot())

    def _nodes_moved(self, changes: list):
        try:
            self.session.move_nodes(changes)
        except SourceSyncError as exc:
            self.view.cancel_drag()
            QMessageBox.warning(self, "이동할 수 없음", str(exc))

    def sync_ui(self):
        self.view.set_editable(self.session.status == ValidationState.VALID)
        self.view.sync_document(self.session.document)
        if self.session.status == ValidationState.VALID:
            self.diagnostics.setText("정상 · 캔버스 편집 가능")
            self.diagnostics.setStyleSheet("color:#9cd9b7;background:#1b2538;padding:7px 12px;")
        elif self.session.status == ValidationState.VALIDATING:
            self.diagnostics.setText("검증 중 · 마지막 정상 다이어그램 유지, 구조 편집 일시 중지")
            self.diagnostics.setStyleSheet("color:#eccd98;background:#1b2538;padding:7px 12px;")
        else:
            detail = self.session.diagnostics or "원문을 검증할 수 없습니다"
            self.diagnostics.setText(f"{self.session.status.value} · {detail} · 마지막 정상 다이어그램 유지")
            self.diagnostics.setStyleSheet("color:#ffb49f;background:#1b2538;padding:7px 12px;")
        self.owner.refresh_status()

    def close(self):
        self._closed = True
        self.autosave_timer.stop()
        self.retry_timer.stop()
        self.parse_timer.stop()
        for unsub in self._subscriptions: unsub()
        self.worker.close()
        return super().close()


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("이미지 내보내기")
        layout = QFormLayout(self)
        self.format = QComboBox()
        self.format.addItems(["PNG", "JPEG"])
        self.scale = QComboBox()
        self.scale.addItems(["1x", "2x", "3x", "4x"])
        self.scale.setCurrentIndex(1)
        self.margin = QSpinBox()
        self.margin.setRange(0, 500)
        self.margin.setValue(40)
        self.transparent = QCheckBox("PNG 투명 배경 사용")
        self.transparent.setChecked(False)
        self.color = "#ffffff"
        color_button = QPushButton("배경색 선택 (기본 흰색)")
        color_button.clicked.connect(self._choose_color)
        layout.addRow("형식", self.format)
        layout.addRow("해상도 배율", self.scale)
        layout.addRow("여백 (px)", self.margin)
        layout.addRow("투명 배경", self.transparent)
        layout.addRow("배경색", color_button)
        hint = QLabel("배율은 실제 이미지 픽셀 수를 변경합니다. DPI 메타데이터와는 다릅니다.")
        hint.setWordWrap(True)
        layout.addRow(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _choose_color(self):
        color = QColorDialog.getColor(QColor(self.color), self)
        if color.isValid(): self.color = color.name()

    def options(self):
        return ExportOptions(scale=self.scale.currentIndex()+1, margin=self.margin.value(),
                             transparent=self.transparent.isChecked(), background=self.color)


class MainWindow(QMainWindow):
    def __init__(self, *, new_document=True):
        super().__init__()
        self.setWindowTitle("Mermaid Diagram Studio · 오프라인")
        self.resize(1320, 810)
        self.project_repo = ProjectRepository()
        self.recovery_repo = RecoveryRepository()
        self.exporters = ExporterRegistry()
        self.signals = UiSignals()
        self.signals.parseReady.connect(self._parsed)
        self.signals.saveReady.connect(self._saved)
        self.parse_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mermaid-parse")
        self.clipboard: dict | None = None
        self._closing = False
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.refresh_status)
        self.setCentralWidget(self.tabs)
        self.save_banner = QLabel("저장 오류 발생")
        self.save_banner.setStyleSheet("color:#fff;background:#a6383c;padding:6px 12px;font-weight:bold")
        self.save_banner.hide()
        self.statusBar().addPermanentWidget(self.save_banner)
        self.state_label = QLabel("준비")
        self.statusBar().addWidget(self.state_label)
        self._make_menus()
        self._make_toolbar()
        self.setStyleSheet("QMainWindow,QWidget { background:#182236;color:#e3e9f4; } "
                           "QMenuBar,QMenu {background:#23324c;color:#e5ecf7;} "
                           "QMenu::item:selected {background:#35527b;} "
                           "QTabBar::tab {background:#23324c;padding:9px 18px;} "
                           "QTabBar::tab:selected {background:#365783;} "
                           "QToolBar {background:#23324c;spacing:5px;} "
                           "QPushButton,QComboBox,QSpinBox {background:#283b58;color:#e9eff7;padding:5px;}")
        if new_document:
            self.add_tab(DocumentSession(DEFAULT_CLASS))
            QTimer.singleShot(200, self._offer_orphan_recovery)

    def current(self) -> EditorTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, EditorTab) else None

    def _tab_for(self, doc_id: str) -> EditorTab | None:
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.session.document_id == doc_id:
                return tab
        return None

    def add_tab(self, session: DocumentSession):
        existing = self._tab_for(session.document_id)
        if existing is not None:
            self.tabs.setCurrentWidget(existing)
            return existing
        tab = EditorTab(session, self)
        index = self.tabs.addTab(tab, self._tab_label(session))
        self.tabs.setCurrentIndex(index)
        self.refresh_status()
        return tab

    def _tab_label(self, session: DocumentSession) -> str:
        base = Path(session.project_path).stem if session.project_path else "새 문서"
        dirty = " *" if session.edit_revision != session.saved_revision else ""
        return base + dirty

    def _action(self, menu: QMenu, label: str, shortcut: str | None, callback):
        act = QAction(label, self)
        if shortcut: act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(callback)
        menu.addAction(act)
        return act

    def _make_menus(self):
        file = self.menuBar().addMenu("파일(&F)")
        self._action(file, "새 클래스 다이어그램", "Ctrl+N", self.new_class)
        self._action(file, "새 시퀀스 다이어그램", None, self.new_sequence)
        self._action(file, "열기...", "Ctrl+O", self.open_project)
        file.addSeparator()
        self._action(file, "정식 저장", "Ctrl+S", self.save_project)
        self._action(file, "다른 이름으로 저장...", "Ctrl+Shift+S", self.save_as)
        file.addSeparator()
        self._action(file, "PNG/JPEG 내보내기...", "Ctrl+E", self.export_image)
        self._action(file, "복구 파일 열기...", None, self.open_recovery)
        file.addSeparator()
        self._action(file, "종료", "Ctrl+Q", self.close)
        edit = self.menuBar().addMenu("편집(&E)")
        self.undo_action = self._action(edit, "실행 취소", "Ctrl+Z", self.undo)
        self.redo_action = self._action(edit, "다시 실행", "Ctrl+Shift+Z", self.redo)
        edit.addSeparator()
        self._action(edit, "복사", "Ctrl+C", self.copy)
        self._action(edit, "붙여넣기", "Ctrl+V", self.paste)
        self.delete_action = self._action(edit, "선택 객체 삭제", "Delete", self.delete)
        self.add_action = self._action(edit, "클래스/참가자 추가...", "Ctrl+Shift+A", self.add_node)
        view = self.menuBar().addMenu("보기(&V)")
        self._action(view, "확대", "Ctrl++", lambda: self._view_call("zoom_in"))
        self._action(view, "축소", "Ctrl+-", lambda: self._view_call("zoom_out"))
        self._action(view, "화면 맞춤", "Ctrl+0", lambda: self._view_call("fit_all"))

    def _make_toolbar(self):
        bar = self.addToolBar("도구")
        bar.setMovable(False)
        for name, callback in [("새 클래스",self.new_class),("새 시퀀스",self.new_sequence),
                               ("열기",self.open_project),("저장",self.save_project),
                               ("객체 추가",self.add_node),("내보내기",self.export_image),
                               ("맞춤",lambda: self._view_call("fit_all"))]:
            action = QAction(name, self)
            action.triggered.connect(callback)
            bar.addAction(action)

    def _view_call(self, name):
        tab = self.current()
        if tab: getattr(tab.view, name)()

    def refresh_status(self, *unused):
        tab = self.current()
        if not tab:
            self.state_label.setText("문서 없음")
            self.save_banner.hide()
            return
        s = tab.session
        self.tabs.setTabText(self.tabs.indexOf(tab), self._tab_label(s))
        dirty = "정식 저장되지 않은 변경 있음" if s.saved_revision != s.edit_revision else "정식 저장 완료"
        self.state_label.setText(f"{s.status.value} | 편집 Revision {s.edit_revision} · 소스 {s.source_revision} | {dirty} | 선택 {len(tab.view.selected_ids())}개")
        self.save_banner.setVisible(s.save_error)
        can_edit = s.status == ValidationState.VALID
        self.delete_action.setEnabled(can_edit)
        self.add_action.setEnabled(can_edit)
        self.undo_action.setEnabled(s.history.can_undo)
        self.redo_action.setEnabled(s.history.can_redo)

    def new_class(self): self.add_tab(DocumentSession(DEFAULT_CLASS))
    def new_sequence(self): self.add_tab(DocumentSession(DEFAULT_SEQUENCE))

    def _do_gui(self, func, *args):
        tab = self.current()
        if not tab: return
        try:
            func(*args)
        except Exception as exc:
            QMessageBox.warning(self, "편집할 수 없음", str(exc))

    def add_node(self):
        tab = self.current()
        if not tab or tab.session.status != ValidationState.VALID: return
        is_class = tab.session.document.diagram_type == "class"
        name, ok = QInputDialog.getText(self, "객체 추가", "클래스 이름" if is_class else "참가자 이름")
        if ok and name.strip():
            self._do_gui(tab.session.add_node, name.strip())

    def _source_has_focus(self, tab):
        return tab.code.hasFocus()

    def copy(self):
        tab = self.current()
        if not tab: return
        if self._source_has_focus(tab):
            tab.code.copy()
        else:
            ids = tab.view.selected_ids()
            if ids:
                self.clipboard = tab.session.copy(ids)
                self.statusBar().showMessage(f"객체 {len(ids)}개 복사", 2000)

    def paste(self):
        tab = self.current()
        if not tab: return
        if self._source_has_focus(tab):
            tab.code.paste()
        elif self.clipboard:
            self._do_gui(tab.session.paste, self.clipboard)

    def delete(self):
        tab = self.current()
        if not tab: return
        if self._source_has_focus(tab):
            cursor = tab.code.textCursor()
            if cursor.hasSelection(): cursor.removeSelectedText()
            else: cursor.deleteChar()
        else:
            ids = tab.view.selected_ids()
            if ids:
                self._do_gui(tab.session.delete, ids)

    def undo(self):
        tab = self.current()
        if not tab: return
        if not tab.session.undo():
            self.statusBar().showMessage("현재 상태에서는 실행 취소할 수 없습니다", 2800)

    def redo(self):
        tab = self.current()
        if not tab: return
        if not tab.session.redo():
            self.statusBar().showMessage("현재 상태에서는 다시 실행할 수 없습니다", 2800)

    def _parsed(self, doc_id: str, rev: int, result: object):
        tab = self._tab_for(doc_id)
        if not tab: return
        tab.session.validate(rev, result)
        tab.sync_ui()

    def _saved(self, doc_id: str, kind: str, rev: int, ok: bool, message: str, path: str):
        tab = self._tab_for(doc_id)
        if not tab: return
        session = tab.session
        if ok:
            if kind == "project" and path == session.project_path:
                session.saved_revision = max(session.saved_revision, rev)
            else: session.recovery_revision = max(session.recovery_revision, rev)
            session.save_error = False
            tab.retry_attempt = 0
            tab.retry_timer.stop()
            self.statusBar().showMessage(f"{kind} ZIP 기록 완료 · Revision {rev}", 3000)
        else:
            session.save_error = True
            # No repeated pop-ups; the visible banner alone reports the error.
            logging.error("Save failed for document %s: %s", doc_id, message)
            if kind == "recovery":
                policy = AutosavePolicy()
                delay = min(policy.retry_initial_ms * (2 ** min(tab.retry_attempt, 12)), policy.retry_max_ms)
                tab.retry_attempt += 1
                tab.retry_timer.start(delay)
        self.refresh_status()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "프로젝트 열기", "", "Diagram Project (*.dgmzip *.zip)")
        if not path: return
        try:
            snapshot = self.project_repo.load(path)
            snapshot.project_path = path
            recovery = self.recovery_repo.candidates(snapshot.document_id)
            if recovery and recovery[0][1].edit_revision > snapshot.edit_revision:
                if QMessageBox.question(self, "복구본 발견", "더 새로운 복구본이 있습니다. 복구본으로 열까요?\n정식 ZIP은 변경하지 않습니다.") == QMessageBox.StandardButton.Yes:
                    snapshot = recovery[0][1]
                    snapshot.project_path = path
            self.add_tab(DocumentSession.from_snapshot(snapshot))
        except Exception as exc:
            QMessageBox.critical(self, "열기 실패", str(exc))

    def open_recovery(self):
        candidates = self.recovery_repo.candidates()
        if not candidates:
            QMessageBox.information(self, "복구본", "사용할 수 있는 복구 ZIP이 없습니다")
            return
        labels = [f"{Path(s.project_path).name if s.project_path else '저장 전 문서'} · {s.document_id[:8]} · Revision {s.edit_revision} · {p.name[-35:]}" for p,s in candidates]
        label, ok = QInputDialog.getItem(self, "복구본 선택", "복구할 스냅샷", labels, 0, False)
        if ok:
            p, state = candidates[labels.index(label)]
            self.add_tab(DocumentSession.from_snapshot(state))

    def _offer_orphan_recovery(self):
        candidates = self.recovery_repo.candidates()
        by_id = {}
        for p, state in candidates:
            if state.document_id not in by_id:
                by_id[state.document_id] = (p, state)
        recoverable = [(p, s) for p, s in by_id.values() if s.edit_revision > s.saved_revision]
        if not recoverable: return
        if QMessageBox.question(self, "자동 복구", f"이전 실행에서 저장되지 않은 문서 복구본이 {len(recoverable)}개 발견되었습니다.\n가장 최신 문서를 복구하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.add_tab(DocumentSession.from_snapshot(recoverable[0][1]))

    def save_project(self):
        tab = self.current()
        if not tab: return
        if not tab.session.project_path:
            self.save_as()
            return
        snapshot = tab.session.snapshot()
        snapshot.saved_revision = snapshot.edit_revision
        tab.worker.submit_project(tab.session.project_path, snapshot)
        self.statusBar().showMessage("정식 ZIP 저장 요청 완료", 2000)

    def save_as(self):
        tab = self.current()
        if not tab: return
        path, _ = QFileDialog.getSaveFileName(self, "프로젝트 저장", tab.session.project_path or "Untitled.dgmzip", "Diagram Project (*.dgmzip)")
        if not path: return
        if not path.lower().endswith(".dgmzip"):
            path += ".dgmzip"
        tab.session.project_path = path
        self.save_project()
        self.refresh_status()

    def export_image(self):
        tab = self.current()
        if not tab: return
        s = tab.session
        if s.status != ValidationState.VALID:
            answer = QMessageBox.question(self, "마지막 정상본 내보내기",
                f"현재 원문은 {s.status.value} 상태입니다.\n마지막 정상본(Revision {s.valid_revision})을 출력하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        dialog = ExportDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        fmt = dialog.format.currentText()
        ext = "png" if fmt == "PNG" else "jpg"
        default_path = str(Path(s.project_path).with_suffix("." + ext)) if s.project_path else "diagram." + ext
        path, _ = QFileDialog.getSaveFileName(self, "내보내기", default_path, f"{fmt} (*.{ext})")
        if not path: return
        if not path.lower().endswith("." + ext): path += "." + ext
        try:
            width, height = self.exporters.get(fmt).export(tab.view.canvas_scene, path, dialog.options())
            self.statusBar().showMessage(f"이미지 내보내기 완료: {width} × {height} px", 6000)
        except Exception as exc:
            QMessageBox.warning(self, "내보내기 실패", str(exc))

    def _confirm_close_tab(self, tab: EditorTab) -> bool:
        s = tab.session
        if s.edit_revision <= 0 or s.edit_revision == s.saved_revision:
            return True
        answer = QMessageBox.question(self, "저장하지 않은 변경",
            f"'{self._tab_label(s)}' 문서에 정식 저장되지 않은 변경이 있습니다.\n정식 프로젝트 ZIP을 저장한 뒤 닫으시겠습니까?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            path = s.project_path
            if not path:
                path, _ = QFileDialog.getSaveFileName(self, "저장할 경로", "Untitled.dgmzip", "Diagram Project (*.dgmzip)")
                if not path: return False
                if not path.endswith(".dgmzip"): path += ".dgmzip"
                s.project_path = path
            try:
                # User-requested save in close flow is synchronous by intent;
                # pending autosaves are canceled and NEVER waited for.
                snapshot = s.snapshot()
                snapshot.saved_revision = snapshot.edit_revision
                write_atomic(path, snapshot)
                s.saved_revision = s.edit_revision
                s.save_error = False
            except Exception as exc:
                QMessageBox.warning(self, "저장 실패", str(exc))
                return False
        return True

    def close_tab(self, index: int):
        tab = self.tabs.widget(index)
        if not isinstance(tab, EditorTab): return
        if not self._confirm_close_tab(tab): return
        tab.close()
        self.tabs.removeTab(index)
        tab.deleteLater()
        if self.tabs.count() == 0:
            self.add_tab(DocumentSession(DEFAULT_CLASS))

    def closeEvent(self, event):
        tabs = [self.tabs.widget(i) for i in range(self.tabs.count())]
        for tab in tabs:
            if not self._confirm_close_tab(tab):
                event.ignore()
                return
        for tab in tabs:
            tab.close()
        self._closing = True
        self.parse_executor.shutdown(wait=False, cancel_futures=True)
        event.accept()
