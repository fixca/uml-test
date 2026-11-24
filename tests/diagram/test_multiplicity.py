"""다중성은 선 길이와 무관하게 클래스 경계 옆에 표시한다."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from gui.items.class_item import ClassItem
from gui.items.relation_item import RelationItem, RelationLabel
from umlparser.model import ClassNode, Relation


@pytest.mark.parametrize("mode", ["straight", "orthogonal"])
@pytest.mark.parametrize(
    "position", [(280, 0), (-280, 0), (0, 240), (0, -240), (360, 260), (900, 0)]
)
def test_labels_stay_at_class_boundary(mode: str, position: tuple[int, int]) -> None:
    app = QApplication.instance() or QApplication([])
    source = ClassItem(ClassNode("A", "A"))
    target = ClassItem(ClassNode("B", "B"))
    target.setPos(*position)
    edge = RelationItem(
        Relation(
            "r",
            "A",
            "B",
            "composition",
            from_multiplicity="1",
            to_multiplicity="0..*",
            label="owns",
        ),
        source,
        target,
        mode,
    )
    for offset in [QPointF(), QPointF(50, 30)]:
        target.setPos(QPointF(*position) + offset)
        edge.update_geometry()
        labels = {
            item.text(): item
            for item in edge.decorations
            if isinstance(item, RelationLabel)
        }
        for text, node in [("1", source), ("0..*", target)]:
            rect = labels[text].sceneBoundingRect()
            box = node.mapRectToScene(node.rect)
            assert not rect.intersects(box)
            gaps = [
                abs(rect.right() - box.left()),
                abs(rect.left() - box.right()),
                abs(rect.bottom() - box.top()),
                abs(rect.top() - box.bottom()),
            ]
            assert min(gaps) == pytest.approx(6)
    assert app is not None
