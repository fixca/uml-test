"""Qt 실행 없이 계층 계산과 배치 좌표의 불변 조건을 검증한다."""

from copy import deepcopy

import pytest

from gui.auto_layout import fill_missing_positions
from umlparser.model import ClassDiagram, ClassNode, Relation
from umlparser.storage import Layout


@pytest.mark.parametrize("count", [0, 1, 30])
def test_positions_do_not_overlap(count: int) -> None:
    diagram = ClassDiagram(classes=[ClassNode(str(i), str(i)) for i in range(count)])
    sizes = {str(i): (180.0 + i * 9, 100.0 + i * 7) for i in range(count)}
    layout = Layout()
    fill_missing_positions(diagram, layout, sizes)
    assert len(layout.nodes) == count
    for i in range(count):
        x, y = layout.nodes[str(i)]
        width, height = sizes[str(i)]
        for j in range(i):
            other_x, other_y = layout.nodes[str(j)]
            other_width, other_height = sizes[str(j)]
            assert (
                x + width <= other_x
                or other_x + other_width <= x
                or y + height <= other_y
                or other_y + other_height <= y
            )
    before = deepcopy(layout)
    fill_missing_positions(diagram, layout, sizes)
    assert layout == before


def test_multiple_parents_and_realization() -> None:
    diagram = ClassDiagram(
        classes=[ClassNode(key, key) for key in "ABCD"],
        relations=[
            Relation("ba", "B", "A", "inheritance"),
            Relation("cb", "C", "B", "realization"),
            Relation("da", "D", "A", "inheritance"),
            Relation("dc", "D", "C", "inheritance"),
        ],
    )
    layout = Layout()
    fill_missing_positions(diagram, layout, {key: (180, 100) for key in "ABCD"})
    assert all(layout.nodes[a][1] < layout.nodes[b][1] for a, b in zip("ABC", "BCD"))


def test_cycle_has_finite_positions_and_descendant_below() -> None:
    diagram = ClassDiagram(
        classes=[ClassNode(key, key) for key in "ABC"],
        relations=[
            Relation("ab", "A", "B", "inheritance"),
            Relation("ba", "B", "A", "inheritance"),
            Relation("cb", "C", "B", "inheritance"),
        ],
    )
    layout = Layout()
    fill_missing_positions(diagram, layout, {key: (180, 100) for key in "ABC"})
    assert len(layout.nodes) == 3
    assert layout.nodes["C"][1] > max(layout.nodes[key][1] for key in "AB")


def test_manual_and_stale_positions_and_edge_modes_are_preserved() -> None:
    diagram = ClassDiagram(classes=[ClassNode(key, key) for key in "AB"])
    layout = Layout(nodes={"A": (-400, 700), "old": (1, 2)}, edges={"r": "orthogonal"})
    fill_missing_positions(diagram, layout, {key: (180, 100) for key in "AB"})
    assert layout.nodes["A"] == (-400, 700)
    assert layout.nodes["old"] == (1, 2)
    assert layout.edges == {"r": "orthogonal"}
