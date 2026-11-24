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
        """그림에서 일어난 이동·꺾임·더블클릭을 컨트롤러 동작에 연결한다."""
        signals.moved.connect(self.move_node)
        signals.edge_toggled.connect(self.toggle_edge)
        signals.edge_bent.connect(self.bend_edge)
        signals.double_clicked.connect(self.goto_class)

    def snapshot(self) -> Snapshot:
        """현재 원문과 배치를 Undo·저장 비교용으로 복사해 둔다."""
        return Snapshot(self.project.code, deepcopy(self.project.layout))

    @property
    def dirty(self) -> bool:
        return self.snapshot() != self.saved

    def set_project(self, project: Project) -> None:
        """프로젝트를 불러와 편집기·그림·Undo 이력을 그 내용으로 새로 시작한다."""
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
        """원문이 바뀌면 검증을 잠시 미루고 그동안 상태를 '검증 중'으로 알린다."""
        self.project.code = self.editor.toPlainText()
        self.valid = False
        self.timer.start()
        self.status.emit("검증 중…")
        self.changed.emit()

    def flush(self) -> None:
        """대기 중인 검증이 있으면 바로 끝내고, 없으면 현재 상태를 이력에 남긴다."""
        if self.timer.isActive():
            self.apply_pending()
        else:
            self.record()

    def apply_pending(self) -> None:
        """미뤄 둔 원문 변경을 검증하고 이력에 기록한다."""
        self.timer.stop()
        self.validate()
        self.record()

    def validate(self) -> None:
        """원문을 파싱해 오류는 편집기에 표시하고, 정상이면 그림을 다시 그린다."""
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
        """마지막 정상 모델과 배치로 그림을 다시 그린다.

        announce가 True면 성공을 상태줄에 알린다.
        """
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
        """현재 상태가 이력의 현재 위치와 다르면 새 이력으로 남긴다.

        그 뒤에 있던 다시 실행 이력은 버린다.
        """
        state = self.snapshot()
        if self.history and state == self.history[self.history_index]:
            return
        del self.history[self.history_index + 1 :]
        self.history.append(state)
        # 이력이 무한히 커지지 않도록 오래된 상태부터 버린다.
        if len(self.history) > 101:
            self.history.pop(0)
        self.history_index = len(self.history) - 1
        self.changed.emit()

    def mark_saved(self, path: str) -> None:
        """저장이 끝난 상태를 기준으로 삼아 미저장 표시를 지운다."""
        self.project.path = path
        self.saved = self.snapshot()
        self.changed.emit()

    def move_node(self, class_id: str, x: float, y: float) -> None:
        """끌어서 옮긴 항목의 새 위치를 코드나 배치에 반영한다."""
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
        """선택한 관계선을 직선과 직각선 사이에서 바꾼다."""
        if not self.valid or self.diagram is None:
            return
        if layout_key not in renderer_for(self.diagram).edge_keys(self.diagram):
            return
        self.project.layout.bends.pop(layout_key, None)
        edges = self.project.layout.edges
        edges[layout_key] = (
            "straight" if edges.get(layout_key) == "orthogonal" else "orthogonal"
        )
        self.redraw()
        self.record()

    def bend_edge(self, layout_key: str, points: object) -> None:
        """관계선의 꺾임 좌표를 검사해 배치에 저장한다. 빈 목록이면 꺾임을 지운다."""
        if not self.valid or self.diagram is None:
            self.redraw(announce=False)
            return
        if layout_key not in renderer_for(self.diagram).edge_keys(self.diagram):
            return
        if not isinstance(points, list) or any(
            not isinstance(point, tuple | list)
            or len(point) != 2
            or not all(
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in point
            )
            for point in points
        ):
            self.status.emit("꺾임 좌표가 올바르지 않습니다.")
            self.redraw(announce=False)
            return
        if points:
            self.project.layout.bends[layout_key] = [
                (float(x), float(y)) for x, y in points
            ]
        else:
            self.project.layout.bends.pop(layout_key, None)
        self.redraw()
        self.record()

    def goto_class(self, class_id: str) -> None:
        """더블클릭한 항목이 정의된 줄로 편집기 커서를 옮긴다."""
        # 줄 번호가 어긋나지 않도록 마지막 정상 모델이 아니라 현재 원문을 다시 파싱한다.
        candidate = parse(self.project.code)
        line = renderer_for(candidate).source_line(candidate, class_id)
        if line is not None:
            self.editor.goto_line(line)

    def undo(self) -> None:
        """한 단계 이전 상태로 되돌린다."""
        if self.timer.isActive():
            self.flush()
        if self.history_index > 0:
            self.history_index -= 1
            self.restore()

    def redo(self) -> None:
        """되돌린 상태를 한 단계 다시 적용한다."""
        if self.timer.isActive():
            self.flush()
        if self.history_index + 1 < len(self.history):
            self.history_index += 1
            self.restore()

    def restore(self) -> None:
        """이력의 현재 위치에 있는 원문과 배치를 편집기와 그림에 복원한다."""
        state = deepcopy(self.history[self.history_index])
        self.project.code, self.project.layout = state.code, state.layout
        with QSignalBlocker(self.editor):
            self.editor.setPlainText(state.code)
        self.validate()
        self.changed.emit()

    def copy_class(self, class_id: str) -> str | None:
        """클래스 하나를 붙여넣을 수 있는 원문 블록으로 만들어 돌려준다."""
        # 현재 편집기의 원문과 맞도록 마지막 정상 모델이 아니라 원문을 다시 파싱한다.
        candidate = parse(self.project.code)
        return renderer_for(candidate).copy_block(self.project.code, class_id)

    def paste_class(self, block: str, position: tuple[float, float]) -> bool:
        """복사한 클래스 블록을 원문에 더하고 새 클래스를 position에 놓는다."""
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
        """선택한 클래스(또는 참여자)와 그에 딸린 관계·메시지를 원문에서 한 번에 지운다.

        지운 뒤 구문 오류가 생기면 원문을 그대로 둔다.
        """
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
                # 중괄호가 닫히지 않은 클래스 블록은 한 문장이 될 때까지 이어서 모은다.
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
                                # 시작 메시지가 지워진 구간의 종료 표식(-)만 지운다.
                                before, arrow, after = chunk.partition(message.arrow)
                                chunk = before + arrow + after.replace("-", "", 1)
                kept.append(chunk)
            chunk = ""
        if chunk:
            self.status.emit("삭제할 원문 범위를 확인할 수 없습니다.")
            return
        code = "".join(kept)
        candidate = parse(code)
        # 지운 관계에서만 등장하던 반대쪽 항목은 선택하지 않았다면 선언을 남겨 유지한다.
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
        # 사라진 클래스와 관계의 저장된 배치도 함께 정리한다.
        if isinstance(candidate, ClassDiagram) and not sequence:
            nodes = {node.id for node in candidate.classes}
            edges = {edge.layout_key for edge in candidate.relations}
            self.project.layout.nodes = {
                key: value
                for key, value in self.project.layout.nodes.items()
                if key in nodes
            }
            self.project.layout.bends = {
                key: value
                for key, value in self.project.layout.bends.items()
                if key in edges
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
