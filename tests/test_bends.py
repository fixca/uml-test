"""수동 꺾임의 Qt 입력, 이력 및 저장 검증."""

import os
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui.items.relation_item import RelationItem
from gui.main_window import MainWindow
from umlparser.storage import Layout, Project, StorageError, load, save


@pytest.fixture
def window() -> Iterator[MainWindow]:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(restore_last=False)
    window.controller.set_project(
        Project(
            "classDiagram\nA --> B\n", Layout(nodes={"A": (0, 0), "B": (500, 0)}), None
        )
    )
    window.show()
    app.processEvents()
    yield window
    window.controller.timer.stop()
    window.controller.mark_saved("test.umlproj")
    window.close()
    app.processEvents()


def edge(window: MainWindow) -> RelationItem:
    return next(item for item in window.scene.items() if isinstance(item, RelationItem))


def test_drag_add_move_undo_save(window: MainWindow, tmp_path: Path) -> None:
    item = edge(window)
    key = item.relation.layout_key
    start = window.view.mapFromScene(item.path().pointAtPercent(0.5))
    end = start + QPoint(0, 70)
    QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(window.view.viewport(), end, delay=20)
    QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    QApplication.processEvents()
    points = window.controller.project.layout.bends[key]
    assert len(points) == 1
    assert QPointF(*points[0]) == window.view.mapToScene(end)
    assert edge(window).path().elementCount() == 3
    start = window.view.mapFromScene(QPointF(*points[0]))
    end = start + QPoint(30, 20)
    QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(window.view.viewport(), end, delay=20)
    QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    QApplication.processEvents()
    assert len(window.controller.project.layout.bends[key]) == 1
    assert window.controller.project.layout.bends[key] != points
    window.controller.undo()
    assert window.controller.project.layout.bends[key] == points
    window.controller.undo()
    assert key not in window.controller.project.layout.bends
    window.controller.redo()
    path = tmp_path / "bends.umlproj"
    save(window.controller.project, str(path))
    restored = load(str(path))
    assert restored.layout.bends[key] == points
    window.controller.set_project(restored)
    assert edge(window).path().elementCount() == 3
    window.controller.move_node("B", 600, 100)
    assert window.controller.project.layout.bends[key] == points
    assert edge(window).path().pointAtPercent(1) != QPointF(500, 45)


def test_reset_delete_and_invalid_input(window: MainWindow) -> None:
    key = edge(window).relation.layout_key
    window.scene.signals.edge_bent.emit(key, [(300.0, 200.0), (400.0, 220.0)])
    before = window.controller.snapshot()
    window.scene.signals.edge_bent.emit(key, [(float("nan"), 10)])
    assert window.controller.snapshot() == before
    window.scene.signals.edge_bent.emit(key, [])
    assert key not in window.controller.project.layout.bends
    window.controller.undo()
    assert window.controller.snapshot() == before
    window.scene.signals.edge_toggled.emit(key)
    assert key not in window.controller.project.layout.bends
    window.controller.undo()
    for item in window.scene.items():
        if item.data(0) == "A":
            item.setSelected(True)
    window.controller.delete_selected()
    assert not window.controller.project.layout.bends


@pytest.mark.parametrize(
    "points", [None, {}, [[1]], [[True, 1]], [[1, "x"]], [[float("inf"), 0]]]
)
def test_invalid_saved_bends(tmp_path: Path, points: object) -> None:
    import json

    path = tmp_path / "invalid.umlproj"
    path.write_text(json.dumps({"layout": {"bends": {"r": points}}}), encoding="utf-8")
    with pytest.raises(StorageError):
        load(str(path))
