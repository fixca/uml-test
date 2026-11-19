"""다이어그램 종류별 렌더러 선택과 미지원 종류 처리를 검증한다."""

import os
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QGraphicsSimpleTextItem

from gui.canvas import DiagramScene
from gui.code_editor import CodeEditor
from gui.controller import Controller
from gui.factory import build
from gui.items.class_item import ClassItem
from gui.renderers import (
    ClassDiagramRenderer,
    DiagramRenderer,
    OtherDiagramRenderer,
    PasteError,
    renderer_for,
)
from umlparser import parse
from umlparser.model import ParseError
from umlparser.storage import Layout

EXAMPLE = Path(__file__).parent.parent / "examples" / "class-example.mmd"


@dataclass
class FakeDiagram:
    type: str = "sequence"
    errors: list[ParseError] = field(default_factory=list)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_class_diagram_uses_class_renderer() -> None:
    diagram = parse(EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(renderer_for(diagram), ClassDiagramRenderer)


def test_unknown_type_uses_other_renderer() -> None:
    assert isinstance(renderer_for(FakeDiagram()), OtherDiagramRenderer)


def test_unsupported_type_replaces_scene_with_notice(app: QApplication) -> None:
    scene = DiagramScene()
    build(scene, parse("classDiagram\nclass A"), Layout())
    assert any(isinstance(item, ClassItem) for item in scene.items())
    with pytest.raises(NotImplementedError):
        build(scene, FakeDiagram(), Layout())
    items = scene.items()
    assert not any(isinstance(item, ClassItem) for item in items)
    assert len(items) == 1
    assert isinstance(items[0], QGraphicsSimpleTextItem)
    assert "sequence" in items[0].text()


def make_controller(app: QApplication) -> Controller:
    controller = Controller(CodeEditor(), DiagramScene())
    controller.diagram = FakeDiagram()
    controller.valid = True
    return controller


def test_controller_reports_unsupported_type(app: QApplication) -> None:
    controller = make_controller(app)
    messages: list[str] = []
    controller.status.connect(messages.append)
    controller.redraw()
    assert controller.rendered is False
    assert any("sequence" in message for message in messages)


def test_controller_ignores_class_operations_on_other_type(
    app: QApplication,
) -> None:
    controller = make_controller(app)
    before = Layout(
        nodes=dict(controller.project.layout.nodes),
        edges=dict(controller.project.layout.edges),
    )
    controller.move_node("A", 1, 2)
    controller.toggle_edge("x")
    assert controller.paste_class("class A", (1, 1)) is False
    assert controller.project.layout == before


def test_abstract_renderer_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        DiagramRenderer()  # type: ignore[abstract]


CLASS_CODE = "classDiagram\nclass A\nclass B"


def test_class_renderer_copy_block() -> None:
    renderer = ClassDiagramRenderer()
    block = renderer.copy_block(CLASS_CODE, "A")
    assert block is not None
    assert "class A" in block
    assert renderer.copy_block(CLASS_CODE, "Missing") is None


def test_class_renderer_paste_block_renames_conflicting_id() -> None:
    renderer = ClassDiagramRenderer()
    diagram = parse(CLASS_CODE)
    block = renderer.copy_block(CLASS_CODE, "A")
    assert block is not None
    code, new_id = renderer.paste_block(CLASS_CODE, diagram, block)
    assert new_id == "A2"
    pasted = parse(code)
    assert not pasted.errors
    assert "A2" in {node.id for node in pasted.classes}


def test_class_renderer_rejects_multiple_classes() -> None:
    renderer = ClassDiagramRenderer()
    with pytest.raises(PasteError) as info:
        renderer.paste_block(CLASS_CODE, parse(CLASS_CODE), "class A\nclass B")
    assert str(info.value) == "클래스 정의 하나만 붙여넣을 수 있습니다."


def test_other_renderer_does_not_support_clipboard() -> None:
    renderer = OtherDiagramRenderer()
    assert renderer.copy_block(CLASS_CODE, "A") is None
    with pytest.raises(PasteError):
        renderer.paste_block(CLASS_CODE, FakeDiagram(), "class A")
