import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QGraphicsLineItem

from gui.items.class_item import ClassItem
from gui.main_window import MainWindow
from gui.renderers.sequence_renderer import ParticipantItem
from umlparser import parse
from umlparser.export import export_scene
from umlparser.sequence import SequenceDocument
from umlparser.storage import Layout, Project, load, save

CLASS = "classDiagram\nclass User\n"
SEQUENCE = (
    "sequenceDiagram\nactor User as 사용자\nUser->>API: 요청\nAPI-->>User: 응답\n"
)


MIXED_MESSAGE = "클래스 다이어그램과 시퀀스 다이어그램은 한 문서에 함께 쓸 수 없습니다."


def test_mixed_documents_are_rejected() -> None:
    model = parse(CLASS + SEQUENCE)
    assert model.errors[0].line == 3
    assert model.errors[0].message == MIXED_MESSAGE
    model = parse(SEQUENCE + CLASS)
    assert model.errors[0].line == 5  # classDiagram 줄
    assert model.errors[0].message == MIXED_MESSAGE
    model = parse(SEQUENCE)
    assert isinstance(model, SequenceDocument) and not model.errors
    assert model.type == "sequence"
    assert [p.label for p in model.sequence.participants.values()] == ["사용자", "API"]
    assert [m.receiver for m in model.sequence.messages] == ["API", "User"]


def headers(window: MainWindow) -> list[ParticipantItem]:
    return sorted(
        (item for item in window.scene.items() if isinstance(item, ParticipantItem)),
        key=lambda item: item.x(),
    )


def test_drag_save_undo_and_export(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(restore_last=False)
    controller = window.controller
    controller.set_project(Project(SEQUENCE, Layout(), None))
    window.show()
    app.processEvents()
    first, second = headers(window)
    start = window.view.mapFromScene(first.mapToScene(QPointF(0, 22)))
    end = window.view.mapFromScene(second.mapToScene(QPointF(0, 22)))
    QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    midpoint = (start + end) / 2
    QTest.mouseMove(window.view.viewport(), midpoint)
    lifeline = next(i for i in first.childItems() if isinstance(i, QGraphicsLineItem))
    assert first.first_x < first.x() < second.x()
    assert lifeline.mapToScene(lifeline.line().p1()).x() == first.scenePos().x()
    assert lifeline.mapToScene(lifeline.line().p2()).x() == first.scenePos().x()
    QTest.mouseMove(window.view.viewport(), end)
    QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()
    assert [h.key for h in headers(window)] == ["sequence:API", "sequence:User"]
    assert controller.project.code == SEQUENCE
    controller.undo()
    assert headers(window)[0].key == "sequence:User"
    controller.redo()
    path = str(tmp_path / "mixed.umlproj")
    save(controller.project, path)
    controller.set_project(load(path))
    assert headers(window)[0].key == "sequence:API"
    assert controller.copy_class("User") is None
    assert controller.paste_class("class User", (10, 20)) is False
    assert controller.valid and headers(window)[0].key == "sequence:API"
    svg = tmp_path / "mixed.svg"
    export_scene(window.scene, str(svg), "svg")
    assert "사용자" in svg.read_text(encoding="utf-8")
    window.hide()


def test_canvas_shows_one_kind_at_a_time() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(restore_last=False)
    controller = window.controller
    for first, second in [(CLASS, SEQUENCE), (SEQUENCE, CLASS)]:
        for code in (first, second):
            controller.set_project(Project(code, Layout(), None))
            app.processEvents()
            items = window.scene.items()
            has_class = any(isinstance(item, ClassItem) for item in items)
            has_participant = any(isinstance(item, ParticipantItem) for item in items)
            assert has_class == (code == CLASS)
            assert has_participant == (code == SEQUENCE)
    window.hide()


def test_mixed_input_keeps_previous_drawing() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(restore_last=False)
    controller = window.controller
    controller.set_project(Project(SEQUENCE, Layout(), None))
    app.processEvents()
    window.editor.setPlainText(CLASS + SEQUENCE)
    controller.flush()
    app.processEvents()
    items = window.scene.items()
    assert controller.valid is False
    assert not any(isinstance(item, ClassItem) for item in items)
    assert any(isinstance(item, ParticipantItem) for item in items)
    window.hide()
