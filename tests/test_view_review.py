"""F1~F3 재검증: 실제 표기, 선택 보존, 내보내기와 경계 배치를 확인한다."""

import os
from copy import deepcopy
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QGraphicsPathItem

from gui.canvas import DiagramScene
from gui.factory import build
from gui.items.class_item import ClassItem
from gui.items.relation_item import RelationItem
from umlparser.export import export_scene
from umlparser.model import ClassDiagram, ClassNode, Relation
from umlparser.storage import Layout


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    "kind",
    [
        "inheritance",
        "realization",
        "association",
        "aggregation",
        "composition",
        "dependency",
    ],
)
@pytest.mark.parametrize("mode", ["straight", "orthogonal"])
def test_relation_symbol(app: QApplication, kind: str, mode: str) -> None:
    scene = DiagramScene()
    model = ClassDiagram(
        classes=[ClassNode("A", "A"), ClassNode("B", "B")],
        relations=[Relation("r", "A", "B", kind, True, layout_key="r")],
    )
    build(scene, model, Layout(nodes={"A": (0, 0), "B": (420, 280)}, edges={"r": mode}))
    edge = next(item for item in scene.items() if isinstance(item, RelationItem))
    expected = (
        Qt.PenStyle.DashLine
        if kind in ("realization", "dependency")
        else Qt.PenStyle.SolidLine
    )
    assert edge.pen().style() == expected
    head = next(
        item for item in edge.childItems() if isinstance(item, QGraphicsPathItem)
    )
    path = head.path()
    tip = path.elementAt(1 if kind in ("association", "dependency") else 0)
    end = edge.path().pointAtPercent(1)
    assert QPointF(tip.x, tip.y) == end
    assert head.pen().style() == Qt.PenStyle.SolidLine
    if kind in ("inheritance", "realization", "aggregation"):
        assert head.brush().color() == QColor("white")
    if kind == "composition":
        assert head.brush().color() != QColor("white")
    if kind in ("association", "dependency"):
        assert head.brush().style() == Qt.BrushStyle.NoBrush
    scene.clear()


@pytest.mark.parametrize("kind", ["association", "dependency"])
def test_undirected_relation_has_no_arrow(app: QApplication, kind: str) -> None:
    first, second = ClassItem(ClassNode("A", "A")), ClassItem(ClassNode("B", "B"))
    second.setPos(400, 0)
    edge = RelationItem(Relation("r", "A", "B", kind), first, second)
    assert not edge.childItems()


def test_wide_box_orthogonal_route_stays_outside(app: QApplication) -> None:
    first = ClassItem(ClassNode("A", "VeryLongName" * 12))
    second = ClassItem(ClassNode("B", "B"))
    second.setPos(first.rect.width() - 200, first.rect.height() + 100)
    for source, target in ((first, second), (second, first)):
        edge = RelationItem(
            Relation("r", "A", "B", "association"), source, target, "orthogonal"
        )
        for item in (first, second):
            interior = item.mapRectToScene(item.rect).adjusted(1, 1, -1, -1)
            for step in range(1, 100):
                assert not interior.contains(edge.path().pointAtPercent(step / 100))


def test_rebuild_preserves_selection_signals_and_model(app: QApplication) -> None:
    scene = DiagramScene()
    signals = scene.signals
    diagram = ClassDiagram(classes=[ClassNode("A", "A")])
    before = deepcopy(diagram)
    layout = Layout()
    build(scene, diagram, layout)
    item = next(item for item in scene.items() if isinstance(item, ClassItem))
    item.setSelected(True)
    build(scene, diagram, layout)
    assert scene.signals is signals
    assert scene.selected_class_ids() == ["A"]
    assert diagram == before
    scene.clear()


def test_svg_export_contains_text_and_restores_selection(
    app: QApplication, tmp_path: Path
) -> None:
    scene = DiagramScene()
    build(scene, ClassDiagram(classes=[ClassNode("A", "Account")]), Layout())
    item = next(item for item in scene.items() if isinstance(item, ClassItem))
    item.setSelected(True)
    target = tmp_path / "view.svg"
    export_scene(scene, str(target), "svg")
    text = target.read_text()
    assert "<text" in text and "Account" in text
    assert "#2563eb" not in text.lower()
    assert scene.selected_class_ids() == ["A"]
    scene.clear()
