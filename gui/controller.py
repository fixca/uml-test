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
from gui.renderers import Diagram, PasteError, renderer_for
from umlparser import parse
from umlparser.model import ClassDiagram
from umlparser.sequence import SequenceDocument
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
        builder: Callable[[QGraphicsScene, Diagram, Layout], None] = factory.build,
    ) -> None:
        super().__init__(editor)
        self.editor = editor
        self.scene = scene
        self.builder = builder
        self.project = Project("", Layout(), None)
        self.diagram: Diagram | None = None
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
        except NotImplementedError as error:
            self.rendered = False
            self.status.emit(
                str(error) or "다이어그램 렌더러 구현을 기다리고 있습니다."
            )
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
        renderer = renderer_for(self.diagram)
        code = renderer.moved_code(self.project.code, self.diagram, class_id, x, y)
        if code is not None:
            if code == self.project.code:
                # 변경이 없으면 끌던 상자만 제자리로 돌린다.
                self.redraw()
                return
            self.project.code = code
            with QSignalBlocker(self.editor):
                self.editor.setPlainText(code)
            self.validate()
            self.record()
            return
        if class_id not in renderer_for(self.diagram).node_ids(self.diagram):
            return
        self.project.layout.nodes[class_id] = (x, y)
        self.redraw()
        self.record()

    def toggle_edge(self, layout_key: str) -> None:
        if not self.valid or self.diagram is None:
            return
        if layout_key not in renderer_for(self.diagram).edge_keys(self.diagram):
            return
        edges = self.project.layout.edges
        edges[layout_key] = (
            "straight" if edges.get(layout_key) == "orthogonal" else "orthogonal"
        )
        self.redraw()
        self.record()

    def goto_class(self, class_id: str) -> None:
        # 원문이 바뀐 뒤에는 과거 정상 모델의 줄 번호를 사용하지 않는다.
        candidate = parse(self.project.code)
        line = renderer_for(candidate).source_line(candidate, class_id)
        if line is not None:
            self.editor.goto_line(line)

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
        # 마지막 정상 모델이 아니라 현재 원문을 기준으로 한다.
        candidate = parse(self.project.code)
        return renderer_for(candidate).copy_block(self.project.code, class_id)

    def paste_class(self, block: str, position: tuple[float, float]) -> bool:
        if not self.valid or self.diagram is None:
            return False
        try:
            code, new_id = renderer_for(self.diagram).paste_block(
                self.project.code, self.diagram, block
            )
        except PasteError as error:
            self.status.emit(str(error))
            return False
        self.project.code = code
        self.project.layout.nodes[new_id] = position
        with QSignalBlocker(self.editor):
            self.editor.setPlainText(code)
        self.validate()
        self.record()
        return True

    def delete_selected(self) -> None:
        """기존 파서로 문장 단위를 확인해 선택 노드와 연결을 한 번에 지운다."""
        selected = set(self.scene.selected_class_ids())
        if not selected or not self.valid or self.diagram is None:
            return
        self.flush()
        original = parse(self.project.code)
        sequence = isinstance(original, SequenceDocument)
        names = (
            {key.removeprefix("sequence:") for key in selected}
            if sequence
            else selected
        )
        kept: list[str] = []
        chunk = ""
        active: dict[str, int] = {}
        for line in self.project.code.splitlines(keepends=True):
            chunk += line
            statement = parse("sequenceDiagram\n" + chunk) if sequence else parse(chunk)
            if sequence and isinstance(statement, SequenceDocument):
                involved = set(statement.sequence.participants)
            else:
                # 닫히지 않은 클래스 블록은 파서가 완성된 모델을 줄 때까지 모은다.
                if statement.errors:
                    continue
                involved = {node.id for node in statement.classes}
            if not involved & names:
                if sequence and isinstance(statement, SequenceDocument):
                    for message in statement.sequence.messages:
                        if message.activate:
                            active[message.receiver] = (
                                active.get(message.receiver, 0) + 1
                            )
                        elif message.deactivate:
                            depth = active.get(message.sender, 0)
                            if depth:
                                active[message.sender] = depth - 1
                            else:
                                # 시작 메시지가 삭제된 활성 구간의 종료 표식만 제거한다.
                                before, arrow, after = chunk.partition(message.arrow)
                                chunk = before + arrow + after.replace("-", "", 1)
                kept.append(chunk)
            chunk = ""
        if chunk:
            self.status.emit("삭제할 원문 범위를 확인할 수 없습니다.")
            return
        code = "".join(kept)
        candidate = parse(code)
        # 관계에서만 등장하던 반대쪽 객체도 선택하지 않았다면 유지한다.
        if sequence and isinstance(original, SequenceDocument):
            remaining = (
                set(candidate.sequence.participants)
                if isinstance(candidate, SequenceDocument)
                else set()
            )
            missing = set(original.sequence.participants) - names - remaining
            additions = [
                f"participant {name}"
                for name in original.sequence.participants
                if name in missing
            ]
        else:
            missing = (
                {node.id for node in original.classes}
                - names
                - {node.id for node in candidate.classes}
            )
            additions = [
                f"class {node.id}" for node in original.classes if node.id in missing
            ]
        if additions:
            code = code.rstrip("\r\n") + "\n" + "\n".join(additions) + "\n"
        candidate = parse(code)
        if candidate.errors:
            self.status.emit(
                "삭제 후 구문 오류가 발생하여 원문을 유지합니다: "
                + candidate.errors[0].message
            )
            return
        if code == self.project.code:
            return
        self.project.code = code
        if isinstance(candidate, ClassDiagram) and not sequence:
            nodes = {node.id for node in candidate.classes}
            edges = {edge.layout_key for edge in candidate.relations}
            self.project.layout.nodes = {
                key: value
                for key, value in self.project.layout.nodes.items()
                if key in nodes
            }
            self.project.layout.edges = {
                key: value
                for key, value in self.project.layout.edges.items()
                if key in edges
            }
        with QSignalBlocker(self.editor):
            self.editor.setPlainText(code)
        self.validate()
        self.record()
