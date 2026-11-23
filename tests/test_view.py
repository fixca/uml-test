"""클래스 박스·관계선·자동 배치를 Qt offscreen으로 검증한다."""

import os
import unittest
from copy import deepcopy
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from gui.factory import build
from gui.items.class_item import ClassItem
from gui.items.relation_item import RelationItem
from umlparser.model import Attribute, ClassDiagram, ClassNode, Method, Param, Relation
from umlparser.storage import Layout


class ViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.scene = QGraphicsScene()

    def test_member_formatting(self) -> None:
        node = ClassNode(
            "A",
            "Account",
            kind="abstract",
            generics=["T"],
            attributes=[Attribute("count", "int", "+", True)],
            methods=[Method("get", "T", [Param("id", "int")], "+", False, True)],
        )
        item = ClassItem(node)
        self.assertEqual(item.sections[0][-1][0], "Account<T>")
        self.assertTrue(item.sections[0][-1][1].italic())
        self.assertEqual(item.sections[1][0][0], "+count: int")
        self.assertTrue(item.sections[1][0][1].underline())
        self.assertEqual(item.sections[2][0][0], "+get(id: int): T")
        self.assertTrue(item.sections[2][0][1].italic())
        enum = ClassItem(ClassNode("E", "State", kind="enum", values=["ON", "OFF"]))
        self.assertEqual([row[0] for row in enum.sections[1]], ["ON", "OFF"])

    def test_hierarchy_and_saved_coordinates(self) -> None:
        diagram = ClassDiagram(
            classes=[ClassNode(key, key) for key in "ABC"],
            relations=[Relation("r", "B", "A", "inheritance")],
        )
        layout = Layout(nodes={"C": (40, 40)})
        build(self.scene, diagram, layout)
        self.assertEqual(layout.nodes["C"], (40, 40))
        self.assertLess(layout.nodes["A"][1], layout.nodes["B"][1])
        nodes = [item for item in self.scene.items() if isinstance(item, ClassItem)]
        for i, first in enumerate(nodes):
            for second in nodes[i + 1 :]:
                self.assertFalse(
                    first.sceneBoundingRect().intersects(second.sceneBoundingRect())
                )
        saved = deepcopy(layout.nodes)
        build(self.scene, diagram, layout)
        self.assertEqual(saved, layout.nodes)

    def test_all_relation_kinds_and_modes(self) -> None:
        kinds = [
            "inheritance",
            "realization",
            "association",
            "aggregation",
            "composition",
            "dependency",
        ]
        for mode in ("straight", "orthogonal"):
            for kind in kinds:
                with self.subTest(kind=kind, mode=mode):
                    relation = Relation(
                        "r", "A", "B", kind, True, "1", "*", "uses", "key"
                    )
                    diagram = ClassDiagram(
                        classes=[ClassNode(key, key) for key in "AB"],
                        relations=[relation],
                    )
                    build(
                        self.scene,
                        diagram,
                        Layout(
                            nodes={"A": (0, 0), "B": (340, 270)}, edges={"key": mode}
                        ),
                    )
                    edge = next(
                        item
                        for item in self.scene.items()
                        if isinstance(item, RelationItem)
                    )
                    self.assertIsNone(edge.data(0))
                    # 라벨 3개 + 머리. 방향 있는 집합·합성은 머리가 2개다.
                    heads = 2 if kind in ("aggregation", "composition") else 1
                    self.assertEqual(len(edge.decorations), 3 + heads)
                    if mode == "orthogonal":
                        path = edge.path()
                        for i in range(1, path.elementCount()):
                            a, b = path.elementAt(i - 1), path.elementAt(i)
                            self.assertTrue(a.x == b.x or a.y == b.y)
                    image = QImage(900, 700, QImage.Format.Format_ARGB32)
                    image.fill(Qt.GlobalColor.white)
                    painter = QPainter(image)
                    try:
                        self.scene.render(painter)
                    finally:
                        painter.end()
                    self.assertFalse(image.isNull())

    def test_cycle_self_relation_and_missing_endpoint(self) -> None:
        diagram = ClassDiagram(
            classes=[ClassNode(key, key) for key in "AB"],
            relations=[
                Relation("ab", "A", "B", "inheritance"),
                Relation("ba", "B", "A", "inheritance"),
                Relation("aa", "A", "A", "association"),
                Relation("missing", "A", "missing", "dependency"),
            ],
        )
        layout = Layout()
        build(self.scene, diagram, layout)
        self.assertEqual(len(layout.nodes), 2)
        edges = [item for item in self.scene.items() if isinstance(item, RelationItem)]
        self.assertEqual(len(edges), 3)
        self.assertTrue(all(not edge.path().isEmpty() for edge in edges))
        build(self.scene, ClassDiagram(), layout)
        self.assertEqual(self.scene.items(), [])

    def test_30_classes(self) -> None:
        diagram = ClassDiagram(
            classes=[ClassNode(str(i), f"Class{i}") for i in range(30)],
            relations=[
                Relation(str(i), str(i), str((i - 1) // 2), "inheritance")
                for i in range(1, 30)
            ],
        )
        layout = Layout()
        start = perf_counter()
        build(self.scene, diagram, layout)
        elapsed = perf_counter() - start
        self.assertEqual(len(layout.nodes), 30)
        print(f"30개 클래스 build: {elapsed * 1000:.1f} ms")


if __name__ == "__main__":
    unittest.main()
