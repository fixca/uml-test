"""실제 Qt 마우스 이벤트로 F4의 선택·이동·클릭 시그널을 검증한다."""

import os
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QGraphicsView

from gui.canvas import DiagramScene
from gui.factory import build
from gui.items.class_item import ClassItem
from gui.items.relation_item import BendHandle, RelationItem
from umlparser.model import ClassDiagram, ClassNode, Relation
from umlparser.storage import Layout


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def canvas(
    app: QApplication,
) -> Iterator[tuple[DiagramScene, QGraphicsView, ClassDiagram, Layout]]:
    scene = DiagramScene()
    view = QGraphicsView(scene)
    diagram = ClassDiagram(
        classes=[ClassNode("A", "A"), ClassNode("B", "B")],
        relations=[Relation("r", "A", "B", "association", layout_key="A->B")],
    )
    layout = Layout(nodes={"A": (0, 0), "B": (400, 0)})
    build(scene, diagram, layout)
    view.resize(800, 500)
    view.show()
    app.processEvents()
    yield scene, view, diagram, layout
    view.close()
    scene.clear()
    app.processEvents()


def test_drag_follows_edge_and_emits_once(app: QApplication, canvas: tuple) -> None:
    scene, view, _, layout = canvas
    moved = QSignalSpy(scene.signals.moved)
    item = next(
        item
        for item in scene.items()
        if isinstance(item, ClassItem) and item.node.id == "A"
    )
    edge = next(item for item in scene.items() if isinstance(item, RelationItem))
    original = edge.path()
    start = view.mapFromScene(item.mapToScene(item.rect.center()))
    end = start + QPoint(35, 25)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end, delay=20)
    assert item.pos() == QPointF(35, 25)
    assert edge.path() != original
    assert len(moved) == 0
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()
    assert list(moved) == [["A", 35.0, 25.0]]
    assert layout.nodes["A"] == (0, 0)  # 저장은 컨트롤러 역할이다.


def test_click_select_and_double_click(app: QApplication, canvas: tuple) -> None:
    scene, view, _, _ = canvas
    moved = QSignalSpy(scene.signals.moved)
    double_clicked = QSignalSpy(scene.signals.double_clicked)
    item = next(item for item in scene.items() if isinstance(item, ClassItem))
    point = view.mapFromScene(item.mapToScene(item.rect.center()))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert scene.selected_class_ids() == [item.node.id]
    app.processEvents()
    assert len(moved) == 0
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    assert list(double_clicked) == [[item.node.id]]


def test_edge_click_can_rebuild_scene(app: QApplication, canvas: tuple) -> None:
    scene, view, diagram, layout = canvas
    bent = QSignalSpy(scene.signals.edge_bent)

    def redraw(key: str, points: list[tuple[float, float]]) -> None:
        layout.bends[key] = points
        build(scene, diagram, layout)

    scene.signals.edge_bent.connect(redraw)
    edge = next(item for item in scene.items() if isinstance(item, RelationItem))
    point = view.mapFromScene(edge.path().pointAtPercent(0.5) + QPointF(0, 3))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    assert len(bent) == 0
    handle = view.mapFromScene(edge.preview_point())
    destination = handle + QPoint(0, 35)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=handle)
    QTest.mouseMove(view.viewport(), destination, delay=20)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=destination)
    app.processEvents()
    assert len(bent) == 1
    assert bent[0][0] == "A->B"
    assert len(layout.bends["A->B"]) == 1


def test_drag_can_rebuild_scene(app: QApplication, canvas: tuple) -> None:
    scene, view, diagram, layout = canvas

    def redraw(class_id: str, x: float, y: float) -> None:
        layout.nodes[class_id] = (x, y)
        build(scene, diagram, layout)

    scene.signals.moved.connect(redraw)
    item = next(
        item
        for item in scene.items()
        if isinstance(item, ClassItem) and item.node.id == "A"
    )
    start = view.mapFromScene(item.mapToScene(item.rect.center()))
    end = start + QPoint(20, 20)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end, delay=20)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()
    assert layout.nodes["A"] == (20, 20)


@pytest.mark.parametrize("destination", ["class", "selected_class", "edge", "blank"])
def test_edge_selection_moves_to_clicked_object(
    app: QApplication, canvas: tuple, destination: str
) -> None:
    scene, view, diagram, layout = canvas
    diagram.classes.extend([ClassNode("C", "C"), ClassNode("D", "D")])
    diagram.relations.append(Relation("r2", "C", "D", "association", layout_key="C->D"))
    layout.nodes.update({"C": (0, 180), "D": (400, 180)})
    build(scene, diagram, layout)
    app.processEvents()
    edges = {
        item.relation.layout_key: item
        for item in scene.items()
        if isinstance(item, RelationItem)
    }
    first = edges["A->B"]
    node = first.source
    if destination == "selected_class":
        node.setSelected(True)
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.mapFromScene(first.path().pointAtPercent(0.5)),
    )
    assert first.isSelected()
    assert first.preview_point() is not None
    assert scene.selectedItems() == [first]
    if destination in ("class", "selected_class"):
        target = node
        point = node.mapToScene(node.rect.center())
    elif destination == "edge":
        target = edges["C->D"]
        point = target.path().pointAtPercent(0.5)
    else:
        target = None
        point = QPointF(250, 130)
    QTest.mouseClick(
        view.viewport(), Qt.MouseButton.LeftButton, pos=view.mapFromScene(point)
    )
    app.processEvents()
    assert not first.isSelected()
    assert first.preview_point() is None
    assert not any(
        child.isVisible()
        for child in first.childItems()
        if isinstance(child, BendHandle)
    )
    assert scene.selectedItems() == ([] if target is None else [target])


def test_control_edge_click_preserves_multi_selection(
    app: QApplication, canvas: tuple
) -> None:
    scene, view, _, _ = canvas
    edge = next(item for item in scene.items() if isinstance(item, RelationItem))
    edge.source.setSelected(True)
    point = view.mapFromScene(edge.path().pointAtPercent(0.5))
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        pos=point,
    )
    assert set(scene.selectedItems()) == {edge.source, edge}
    preview = edge.preview_point()
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    assert scene.selectedItems() == [edge]
    assert edge.preview_point() == preview
