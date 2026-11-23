"""수동 꺾임의 Qt 입력, 이력 및 저장 검증."""

import os
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui.items.relation_item import BendHandle, RelationItem
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
    QTest.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QApplication.processEvents()
    assert key not in window.controller.project.layout.bends
    assert not window.controller.dirty
    handles = [
        item for item in edge(window).childItems() if isinstance(item, BendHandle)
    ]
    assert len(handles) == 1 and handles[0].isVisible()
    assert edge(window).preview_point() == edge(window).path().pointAtPercent(0.5)
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


def test_line_drag_requires_handle_and_click_is_idempotent(window: MainWindow) -> None:
    item = edge(window)
    key = item.relation.layout_key
    start = window.view.mapFromScene(item.path().pointAtPercent(0.25))
    end = start + QPoint(0, 60)
    QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(window.view.viewport(), end, delay=20)
    QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    QApplication.processEvents()
    assert key not in window.controller.project.layout.bends
    QTest.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QApplication.processEvents()
    item = edge(window)
    assert item.bends == []
    assert item.preview_point() == item.path().pointAtPercent(0.5)
    before = window.controller.snapshot()
    index = window.controller.history_index
    point = window.view.mapFromScene(item.preview_point())
    QTest.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QApplication.processEvents()
    assert window.controller.snapshot() == before
    assert window.controller.history_index == index
    window.scene.clearSelection()
    assert all(
        not child.isVisible()
        for child in edge(window).childItems()
        if isinstance(child, BendHandle)
    )


def test_split_both_sides_repeatedly(window: MainWindow, tmp_path: Path) -> None:
    key = edge(window).relation.layout_key
    # 양쪽 선분과 새 점 사이의 선분을 계속 나눈다.
    for segment in [0, 0, 2, 1, 3]:
        item = edge(window)
        path = item.path()
        start = path.elementAt(segment)
        end = path.elementAt(segment + 1)
        midpoint = QPointF((start.x + end.x) / 2, (start.y + end.y) / 2)
        before = list(window.controller.project.layout.bends.get(key, []))
        # 클릭 위치가 가운데가 아니어도 선택한 선분의 절반에 점이 생긴다.
        click = QPointF(start.x, start.y) * 0.4 + QPointF(end.x, end.y) * 0.6
        QTest.mouseClick(
            window.view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=window.view.mapFromScene(click),
        )
        QApplication.processEvents()
        assert window.controller.project.layout.bends.get(key, []) == before
        assert edge(window).preview_point() == midpoint
        start_point = window.view.mapFromScene(midpoint)
        end_point = start_point + QPoint(0, 25)
        QTest.mousePress(
            window.view.viewport(), Qt.MouseButton.LeftButton, pos=start_point
        )
        QTest.mouseMove(window.view.viewport(), end_point, delay=20)
        QTest.mouseRelease(
            window.view.viewport(), Qt.MouseButton.LeftButton, pos=end_point
        )
        QApplication.processEvents()
        destination = window.view.mapToScene(end_point)
        expected = before[:]
        expected.insert(segment, (destination.x(), destination.y()))
        assert window.controller.project.layout.bends[key] == expected
    assert len(edge(window).bends) == 5
    before = window.controller.snapshot()
    # 중간 점을 이동해도 앞뒤 점과 그 순서가 유지된다.
    start = window.view.mapFromScene(edge(window).bends[2])
    end = start + QPoint(0, 60)
    QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(window.view.viewport(), end, delay=20)
    QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    QApplication.processEvents()
    after = window.controller.snapshot()
    assert after.layout.bends[key][:2] == before.layout.bends[key][:2]
    assert after.layout.bends[key][3:] == before.layout.bends[key][3:]
    assert after.layout.bends[key][2] != before.layout.bends[key][2]
    window.controller.undo()
    assert window.controller.snapshot() == before
    window.controller.redo()
    assert window.controller.snapshot() == after
    path = tmp_path / "many-bends.umlproj"
    save(window.controller.project, str(path))
    assert load(str(path)).layout.bends == after.layout.bends


def test_preview_does_not_change_saved_path_or_history(
    window: MainWindow, tmp_path: Path
) -> None:
    item = edge(window)
    before = window.controller.snapshot()
    original_path = item.path()
    history = window.controller.history_index
    point = window.view.mapFromScene(original_path.pointAtPercent(0.5))
    QTest.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QApplication.processEvents()
    assert item.preview_point() is not None
    assert item.path() == original_path
    # 드래그했다가 원위치로 돌아오면 확정하지 않는다.
    QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseMove(window.view.viewport(), point + QPoint(0, 50), delay=20)
    QTest.mouseMove(window.view.viewport(), point, delay=20)
    QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QApplication.processEvents()
    assert window.controller.snapshot() == before
    assert window.controller.history_index == history
    assert not window.controller.dirty
    assert item.path() == original_path
    path = tmp_path / "preview.umlproj"
    save(window.controller.project, str(path))
    assert not load(str(path)).layout.bends
    window.scene.clearSelection()
    assert item.preview_point() is None
