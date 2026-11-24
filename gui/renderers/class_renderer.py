"""클래스 다이어그램 렌더러."""

from dataclasses import replace

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtWidgets import QGraphicsScene

from gui.auto_layout import fill_missing_positions
from gui.canvas import DiagramSignals, DiagramView
from gui.items.class_item import ClassItem
from gui.items.relation_item import RelationItem
from gui.renderers.base import Diagram, DiagramRenderer, PasteError
from umlparser import parse
from umlparser.edit import append_class, class_block
from umlparser.model import ClassDiagram, Source
from umlparser.storage import Layout


def object_states(
    scene: QGraphicsScene,
) -> dict[tuple[str, str], tuple[object, QPointF]]:
    """장면의 클래스와 관계선 상태를 모은다. 이전 그림이 있었는지 판별에 쓴다."""
    states = {}
    for item in scene.items(Qt.SortOrder.AscendingOrder):
        if isinstance(item, ClassItem):
            states["class", item.node.id] = (
                item.sections,
                item.sceneBoundingRect().center(),
            )
        elif isinstance(item, RelationItem):
            relation = replace(item.relation, id="", source=Source())
            states["edge", relation.layout_key] = (
                (relation, item.mode),
                item.mapToScene(item.path().pointAtPercent(0.5)),
            )
    return states


class ClassDiagramRenderer(DiagramRenderer):
    diagram_type = "class"

    def render(
        self,
        scene: QGraphicsScene,
        diagram: Diagram,
        layout: Layout,
        signals: DiagramSignals,
    ) -> None:
        """클래스 다이어그램을 장면에 다시 그린다.

        사용자가 놓은 위치와 scene.signals는 그대로 두고 좌표가 없는 클래스만
        새로 배치한다. 오류가 없는 빈 모델은 장면을 비우고, 끝점이 없는 관계는
        그 선만 건너뛴다. 클래스 다이어그램이 아니면 TypeError를 던진다.
        """
        if not isinstance(diagram, ClassDiagram):
            raise TypeError("ClassDiagram만 그릴 수 있습니다.")
        # 다시 그린 뒤에도 같은 클래스가 선택된 채 남도록 선택 상태를 기억한다.
        selected = {
            item.data(0)
            for item in scene.selectedItems()
            if isinstance(item.data(0), str)
        }
        # 자동 배치에 필요한 클래스별 박스 크기를 먼저 구한다.
        nodes = {node.id: ClassItem(node) for node in diagram.classes}
        sizes = {
            key: (item.rect.width(), item.rect.height()) for key, item in nodes.items()
        }
        # 좌표가 없는 클래스에만 위치를 정해 사용자가 놓은 위치를 보존한다.
        fill_missing_positions(diagram, layout, sizes)
        # 선택된 관계선과 이전 그림을 기억해 둔다. (장면 객체는 유지된다.)
        selected_edges = {
            item.relation.layout_key
            for item in scene.selectedItems()
            if isinstance(item, RelationItem)
        }
        previous = object_states(scene)
        scene.clear()
        for class_id, item in nodes.items():
            item.setPos(*layout.nodes[class_id])
            scene.addItem(item)
            item.setSelected(class_id in selected)
            # 이동·더블클릭을 장면 시그널로 전달한다. 이벤트가 끝난 뒤 처리한다.
            item.moved.connect(signals.moved, Qt.ConnectionType.QueuedConnection)
            item.double_clicked.connect(
                signals.double_clicked, Qt.ConnectionType.QueuedConnection
            )
        # 관계선은 양 끝 클래스가 모두 만들어진 뒤에 그린다.
        for relation in diagram.relations:
            # 오류로 일부만 읽힌 모델에서 끝점 클래스가 없으면 그 선은 그리지 않는다.
            if relation.from_ not in nodes or relation.to not in nodes:
                continue
            source_item = nodes[relation.from_]
            target_item = nodes[relation.to]
            mode = layout.edges.get(relation.layout_key, "straight")
            relation_item = RelationItem(
                relation,
                source_item,
                target_item,
                mode,
                layout.bends.get(relation.layout_key),
            )
            scene.addItem(relation_item)
            relation_item.setSelected(relation.layout_key in selected_edges)
            # 클래스를 끄는 동안 연결된 관계선이 따라 움직이게 한다.
            source_item.xChanged.connect(relation_item.update_geometry)
            source_item.yChanged.connect(relation_item.update_geometry)
            # 자기 자신으로 가는 관계는 한 번만 연결한다.
            if target_item is not source_item:
                target_item.xChanged.connect(relation_item.update_geometry)
                target_item.yChanged.connect(relation_item.update_geometry)
        # 장면 크기를 현재 그림에 맞춰 스크롤 영역이 필요 이상으로 남지 않게 한다.
        bounds = scene.itemsBoundingRect()
        scene.setSceneRect(
            bounds.adjusted(-40, -40, 40, 40) if nodes else QRectF(0, 0, 80, 80)
        )

        # 처음 그릴 때는 그림을 화면 가운데에 보인다. 변경 위치로 옮기기는 보류 중이다.
        # states = object_states(scene)
        for view in scene.views():
            if not isinstance(view, DiagramView):
                continue
            if not previous:
                view.center_canvas(scene.sceneRect().center())
                continue
            # for key, (appearance, center) in states.items():
            #     old = previous.get(key)
            #     if (
            #         old is None
            #         or appearance != old[0]
            #         or (key[0] == "class" and center != old[1])
            #     ):
            #         view.center_canvas(center)
            #         break

    def node_ids(self, diagram: Diagram) -> set[str]:
        """클래스 다이어그램의 모든 클래스 ID를 돌려준다."""
        if not isinstance(diagram, ClassDiagram):
            return set()
        return {node.id for node in diagram.classes}

    def edge_keys(self, diagram: Diagram) -> set[str]:
        """클래스 다이어그램의 모든 관계선 layout key를 돌려준다."""
        if not isinstance(diagram, ClassDiagram):
            return set()
        return {relation.layout_key for relation in diagram.relations}

    def source_line(self, diagram: Diagram, node_id: str) -> int | None:
        """클래스가 정의된 원문 줄 번호를 돌려준다."""
        if not isinstance(diagram, ClassDiagram):
            return None
        for node in diagram.classes:
            if node.id == node_id and node.source:
                return node.source.line
        return None

    def copy_block(self, code: str, node_id: str) -> str | None:
        """클래스 정의를 복사용 원문 블록으로 돌려준다. 찾지 못하면 None."""
        return class_block(code, node_id) or None

    def paste_block(self, code: str, diagram: Diagram, block: str) -> tuple[str, str]:
        """클래스 정의 하나를 이름이 겹치지 않게 바꿔 원문 끝에 붙인다."""
        if not isinstance(diagram, ClassDiagram):
            raise PasteError("이 다이어그램에서는 클래스를 붙여넣을 수 없습니다.")
        fragment = parse("classDiagram\n" + block)
        if (
            fragment.type != "class"
            or fragment.errors
            or len(fragment.classes) != 1
            or fragment.relations
            or fragment.classes[0].implicit
        ):
            raise PasteError("클래스 정의 하나만 붙여넣을 수 있습니다.")
        source_id = fragment.classes[0].id
        existing = {node.id for node in diagram.classes}
        number = 2
        new_id = source_id
        while new_id in existing:
            new_id = f"{source_id}{number}"
            number += 1
        new_code = append_class(code, block, new_id)
        candidate = parse(new_code)
        if candidate.errors or new_id not in {node.id for node in candidate.classes}:
            raise PasteError("이 클래스 정의는 안전하게 붙여넣을 수 없습니다.")
        return new_code, new_id
