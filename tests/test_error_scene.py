"""F5: 오류·빈 모델·누락 끝점이 장면과 배치를 손상시키지 않는지 검사한다."""

import os
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from gui.canvas import DiagramScene
from gui.factory import build
from gui.items.class_item import ClassItem
from umlparser.model import ClassDiagram, ClassNode, ParseError, Relation
from umlparser.storage import Layout


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("partial", [False, True])
def test_error_model_preserves_previous_scene(app: QApplication, partial: bool) -> None:
    scene = DiagramScene()
    layout = Layout()
    build(scene, ClassDiagram(classes=[ClassNode("A", "A")]), layout)
    item = next(item for item in scene.items() if isinstance(item, ClassItem))
    item.setSelected(True)
    previous_items = scene.items()
    previous_layout = deepcopy(layout)
    candidate = ClassDiagram(
        classes=[ClassNode("B", "B")] if partial else [],
        errors=[ParseError(2, 1, "오류")],
    )
    build(scene, candidate, layout)
    assert scene.items() == previous_items
    assert scene.selected_class_ids() == ["A"]
    assert layout == previous_layout
    # 오류를 고친 다음 정상 모델을 주면 다시 갱신한다.
    build(scene, ClassDiagram(classes=[ClassNode("B", "B")]), layout)
    assert [item.node.id for item in scene.items() if isinstance(item, ClassItem)] == [
        "B"
    ]
    scene.clear()


def test_initial_error_and_valid_empty_model(app: QApplication) -> None:
    scene = DiagramScene()
    layout = Layout()
    build(scene, ClassDiagram(errors=[ParseError(1, 1, "오류")]), layout)
    assert not scene.items()
    assert not layout.nodes
    build(scene, ClassDiagram(classes=[ClassNode("A", "A")]), layout)
    build(scene, ClassDiagram(), layout)
    assert not scene.items()  # 정상 빈 코드는 이전 그림을 지워야 한다.


def test_missing_endpoint_and_generic_scene(app: QApplication) -> None:
    scene = QGraphicsScene()
    diagram = ClassDiagram(
        classes=[ClassNode("A", "A")],
        relations=[Relation("r", "A", "missing", "association")],
    )
    build(scene, diagram, Layout())
    assert len(scene.items()) == 1
    assert scene.signals is not None
    scene.clear()
