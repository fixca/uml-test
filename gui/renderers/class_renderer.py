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
        """수동 좌표와 scene.signals를 보존하고 누락된 초기 좌표만 채운다.

        오류가 없는 빈 모델은 장면을 비운다. 끝점이 없는 관계는 해당
        선만 건너뛴다. 클래스 다이어그램이 아니면 TypeError를 던진다.
        """
        if not isinstance(diagram, ClassDiagram):
            raise TypeError("ClassDiagram만 그릴 수 있습니다.")
        # scene.clear() 전에 선택 ID를 보관해 같은 클래스를 다시 선택한다.
        selected = {
            item.data(0)
            for item in scene.selectedItems()
            if isinstance(item.data(0), str)
        }
        # 박스 크기가 있어야 자동 배치 간격을 계산할 수 있다.
        nodes = {node.id: ClassItem(node) for node in diagram.classes}
        sizes = {
            key: (item.rect.width(), item.rect.height()) for key, item in nodes.items()
        }
        # 새 좌표만 layout에 채우고 수동 위치는 보존한다.
        fill_missing_positions(diagram, layout, sizes)
        # 장면 객체 자체는 유지하므로 scene.signals와 컨트롤러 연결도 유지된다.
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
            # 컨트롤러가 장면을 비워도 마우스 이벤트가 먼저 끝나도록 지연 전달한다.
            item.moved.connect(signals.moved, Qt.ConnectionType.QueuedConnection)
            item.double_clicked.connect(
                signals.double_clicked, Qt.ConnectionType.QueuedConnection
            )
        # 끝점 박스를 모두 만든 뒤 관계선을 생성한다.
        for relation in diagram.relations:
            # 부분 모델에 끝점이 없는 관계가 있으면 해당 선만 건너뛴다.
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
            # 드래그 중에는 모델이나 layout을 바꾸지 않고 선만 따라 움직인다.
            source_item.xChanged.connect(relation_item.update_geometry)
            source_item.yChanged.connect(relation_item.update_geometry)
            # 자기 관계는 같은 박스에 중복 연결하지 않는다.
            if target_item is not source_item:
                target_item.xChanged.connect(relation_item.update_geometry)
                target_item.yChanged.connect(relation_item.update_geometry)
        # 이전 그림이 더 컸더라도 현재 그림에 맞춰 스크롤 영역을 다시 줄인다.
        bounds = scene.itemsBoundingRect()
        scene.setSceneRect(
            bounds.adjusted(-40, -40, 40, 40) if nodes else QRectF(0, 0, 80, 80)
        )

        # 객체 변경에 따른 화면 이동은 논의 후 기능 추가 여부를 결정한다.
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
        if not isinstance(diagram, ClassDiagram):
            return set()
        return {node.id for node in diagram.classes}

    def edge_keys(self, diagram: Diagram) -> set[str]:
        if not isinstance(diagram, ClassDiagram):
            return set()
        return {relation.layout_key for relation in diagram.relations}

    def source_line(self, diagram: Diagram, node_id: str) -> int | None:
        if not isinstance(diagram, ClassDiagram):
            return None
        for node in diagram.classes:
            if node.id == node_id and node.source:
                # Source는 위치 객체이므로 정수 줄 번호만 돌려준다.
                return node.source.line
        return None

    def copy_block(self, code: str, node_id: str) -> str | None:
        return class_block(code, node_id) or None

    def paste_block(self, code: str, diagram: Diagram, block: str) -> tuple[str, str]:
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
