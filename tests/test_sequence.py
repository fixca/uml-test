import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QGraphicsLineItem

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


def test_section_boundaries() -> None:
    for code, line in [(CLASS + SEQUENCE, 2), (SEQUENCE + CLASS, 6)]:
        model = parse(code)
        assert isinstance(model, SequenceDocument) and not model.errors
        assert model.classes[0].source.line == line
        assert [p.label for p in model.sequence.participants.values()] == [
            "사용자",
            "API",
        ]
        assert [m.receiver for m in model.sequence.messages] == ["API", "User"]
    assert parse(CLASS + SEQUENCE + "class Broken").errors[0].line == 7


def headers(window: MainWindow) -> list[ParticipantItem]:
    return sorted(
        (item for item in window.scene.items() if isinstance(item, ParticipantItem)),
        key=lambda item: item.x(),
    )


def test_drag_save_undo_and_export(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(restore_last=False)
    controller = window.controller
    controller.set_project(Project(CLASS + SEQUENCE, Layout(), None))
    window.show()
    app.processEvents()
    first, second = headers(window)
    start = window.view.mapFromScene(first.mapToScene(QPointF(0, 22)))
    end = window.view.mapFromScene(second.mapToScene(QPointF(0, 22)))
    position = controller.project.layout.nodes["User"]
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
    assert controller.project.layout.nodes["User"] == position
    assert controller.project.code == CLASS + SEQUENCE
    controller.undo()
    assert headers(window)[0].key == "sequence:User"
    controller.redo()
    path = str(tmp_path / "mixed.umlproj")
    save(controller.project, path)
    controller.set_project(load(path))
    assert headers(window)[0].key == "sequence:API"
    assert controller.copy_class("User") == "class User"
    assert controller.paste_class("class User", (10, 20))
    assert controller.valid and headers(window)[0].key == "sequence:API"
    svg = tmp_path / "mixed.svg"
    export_scene(window.scene, str(svg), "svg")
    assert "사용자" in svg.read_text(encoding="utf-8")
    window.hide()
