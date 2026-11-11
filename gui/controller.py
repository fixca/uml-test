"""원문, 레이아웃, 통합 스냅샷 이력을 소유하는 컨트롤러."""

import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QSignalBlocker, QTimer, pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene

from gui import factory
from gui.canvas import DiagramScene, DiagramSignals
from gui.code_editor import CodeEditor
from umlparser import parse
from umlparser.edit import append_class, class_block
from umlparser.model import ClassDiagram
from umlparser.storage import Layout, Project


@dataclass(eq=True)
class Snapshot:
    code: str
    layout: Layout


class Controller(QObject):
    changed = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(
        self,
        editor: CodeEditor,
        scene: DiagramScene,
        builder: Callable[[QGraphicsScene, ClassDiagram, Layout], None] = factory.build,
    ) -> None:
        super().__init__(editor)
        self.editor = editor
        self.scene = scene
        self.builder = builder
        self.project = Project("", Layout(), None)
        self.diagram: ClassDiagram | None = None
        self.valid = False
        self.rendered = False
        self.history: list[Snapshot] = []
        self.history_index = 0
        self.saved = self.snapshot()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.apply_pending)
        editor.textChanged.connect(self.text_changed)
        editor.undo_requested.connect(self.undo)
        editor.redo_requested.connect(self.redo)
        self.bind_signals(scene.signals)

    def bind_signals(self, signals: DiagramSignals) -> None:
        signals.moved.connect(self.move_node)
        signals.edge_toggled.connect(self.toggle_edge)
        signals.double_clicked.connect(self.goto_class)

    def snapshot(self) -> Snapshot:
        return Snapshot(self.project.code, deepcopy(self.project.layout))

    @property
    def dirty(self) -> bool:
        return self.snapshot() != self.saved

    def set_project(self, project: Project) -> None:
        self.timer.stop()
        self.project = deepcopy(project)
        with QSignalBlocker(self.editor):
            self.editor.setPlainText(project.code)
        self.scene.clear()
        self.diagram = None
        self.validate()
        self.saved = self.snapshot()
        self.history = [self.snapshot()]
        self.history_index = 0
        self.changed.emit()

    def text_changed(self) -> None:
        self.project.code = self.editor.toPlainText()
        self.valid = False
        self.timer.start()
        self.status.emit("검증 중…")
        self.changed.emit()

    def flush(self) -> None:
        if self.timer.isActive():
            self.apply_pending()
        else:
            self.record()

    def apply_pending(self) -> None:
        self.timer.stop()
        self.validate()
        self.record()

    def validate(self) -> None:
        candidate = parse(self.project.code)
        self.editor.set_errors(candidate.errors)
        self.valid = not candidate.errors
        if candidate.errors:
            error = candidate.errors[0]
            self.status.emit(f"{error.line}번째 줄: {error.message}")
        else:
            self.diagram = candidate
            self.redraw()
        self.changed.emit()

    def redraw(self, announce: bool = True) -> None:
        if self.diagram is None:
            return
        try:
            self.builder(self.scene, self.diagram, self.project.layout)
        except NotImplementedError:
            self.rendered = False
            self.status.emit("다이어그램 팩토리 구현을 기다리고 있습니다.")
        else:
            self.rendered = True
            if announce:
                self.status.emit("준비")

    def record(self) -> None:
        state = self.snapshot()
        if self.history and state == self.history[self.history_index]:
            return
        del self.history[self.history_index + 1 :]
        self.history.append(state)
        # 전체 스냅샷을 사용하므로 오래된 작업부터 제한한다.
        if len(self.history) > 101:
            self.history.pop(0)
        self.history_index = len(self.history) - 1
        self.changed.emit()

    def mark_saved(self, path: str) -> None:
        self.project.path = path
        self.saved = self.snapshot()
        self.changed.emit()

    def move_node(self, class_id: str, x: float, y: float) -> None:
        if not self.valid or self.diagram is None:
            self.redraw(announce=False)
            return
        if not all(math.isfinite(value) for value in (x, y)):
            return
        if class_id not in {node.id for node in self.diagram.classes}:
            return
        self.project.layout.nodes[class_id] = (x, y)
        self.redraw()
        self.record()

    def toggle_edge(self, layout_key: str) -> None:
        if not self.valid or self.diagram is None:
            return
        if layout_key not in {edge.layout_key for edge in self.diagram.relations}:
            return
        edges = self.project.layout.edges
        edges[layout_key] = (
            "straight" if edges.get(layout_key) == "orthogonal" else "orthogonal"
        )
        self.redraw()
        self.record()

    def goto_class(self, class_id: str) -> None:
        # 원문이 바뀐 뒤에는 과거 정상 모델의 줄 번호를 사용하지 않는다.
        for node in parse(self.project.code).classes:
            if node.id == class_id and node.source:
                self.editor.goto_line(node.source)
                return

    def undo(self) -> None:
        if self.timer.isActive():
            self.flush()
        if self.history_index > 0:
            self.history_index -= 1
            self.restore()

    def redo(self) -> None:
        if self.timer.isActive():
            self.flush()
        if self.history_index + 1 < len(self.history):
            self.history_index += 1
            self.restore()

    def restore(self) -> None:
        state = deepcopy(self.history[self.history_index])
        self.project.code, self.project.layout = state.code, state.layout
        with QSignalBlocker(self.editor):
            self.editor.setPlainText(state.code)
        self.validate()
        self.changed.emit()

    def copy_class(self, class_id: str) -> str | None:
        return class_block(self.project.code, class_id) or None

    def paste_class(self, block: str, position: tuple[float, float]) -> bool:
        if not self.valid or self.diagram is None:
            return False
        fragment = parse("classDiagram\n" + block)
        if (
            fragment.errors
            or len(fragment.classes) != 1
            or fragment.relations
            or fragment.classes[0].implicit
        ):
            self.status.emit("클래스 정의 하나만 붙여넣을 수 있습니다.")
            return False
        source_id = fragment.classes[0].id
        existing = {node.id for node in self.diagram.classes}
        number = 2
        new_id = source_id
        while new_id in existing:
            new_id = f"{source_id}{number}"
            number += 1
        code = append_class(self.project.code, block, new_id)
        candidate = parse(code)
        if candidate.errors or new_id not in {node.id for node in candidate.classes}:
            self.status.emit("이 클래스 정의는 안전하게 붙여넣을 수 없습니다.")
            return False
        self.project.code = code
        self.project.layout.nodes[new_id] = position
        with QSignalBlocker(self.editor):
            self.editor.setPlainText(code)
        self.validate()
        self.record()
        return True
