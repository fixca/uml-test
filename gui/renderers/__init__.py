"""다이어그램 종류별 렌더러 등록."""

from gui.renderers.base import Diagram, DiagramRenderer, PasteError
from gui.renderers.class_renderer import ClassDiagramRenderer
from gui.renderers.other_renderer import OtherDiagramRenderer
from gui.renderers.sequence_renderer import SequenceRenderer

# 새 종류는 전용 렌더러를 만들어 여기에 등록한다.
RENDERERS: dict[str, DiagramRenderer] = {
    renderer.diagram_type: renderer
    for renderer in (ClassDiagramRenderer(), SequenceRenderer())
}
FALLBACK = OtherDiagramRenderer()


def renderer_for(diagram: Diagram) -> DiagramRenderer:
    return RENDERERS.get(diagram.type, FALLBACK)


__all__ = [
    "ClassDiagramRenderer",
    "Diagram",
    "DiagramRenderer",
    "OtherDiagramRenderer",
    "PasteError",
    "renderer_for",
]
