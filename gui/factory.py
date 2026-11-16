"""모델 → 그림 요소 생성. 담당: 이도훈 (F3, F4).

F3: build(scene, diagram, layout)으로 장면을 비우고 다시 그린다.
위치가 없는 클래스는 auto_layout으로 배치한다.
F4의 이동·더블 클릭·관계선 클릭 시그널은 후속 구현 범위다.
"""

from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QGraphicsScene

from gui.auto_layout import fill_missing_positions
from gui.items.class_item import ClassItem
from gui.items.relation_item import RelationItem
from umlparser.model import ClassDiagram
from umlparser.storage import Layout


def build(scene: QGraphicsScene, diagram: ClassDiagram, layout: Layout) -> None:
    """수동 좌표와 scene.signals를 보존하고 누락된 초기 좌표만 채운다.

    부분 모델에서 끝점이 없는 관계는 건너뛴다. 마지막 정상 그림의 유지는
    기존 컨트롤러 validate()가 담당한다. 이 함수는 전달된 모델을 그린다.
    """
    # scene.clear() 전에 선택 ID를 보관해 같은 클래스를 다시 선택한다.
    selected = {
        item.data(0) for item in scene.selectedItems() if isinstance(item.data(0), str)
    }
    # 박스 크기가 있어야 자동 배치 간격을 계산할 수 있다.
    nodes = {node.id: ClassItem(node) for node in diagram.classes}
    sizes = {
        key: (item.rect.width(), item.rect.height()) for key, item in nodes.items()
    }
    fill_missing_positions(diagram, layout, sizes)
    # 장면 객체 자체는 유지하므로 scene.signals와 컨트롤러 연결도 유지된다.
    scene.clear()
    for class_id, item in nodes.items():
        item.setPos(*layout.nodes[class_id])
        scene.addItem(item)
        item.setSelected(class_id in selected)
    # 끝점 박스를 모두 만든 뒤 관계선을 생성한다.
    for relation in diagram.relations:
        # 부분 모델에 끝점이 없는 관계가 있으면 해당 선만 건너뛴다.
        if relation.from_ not in nodes or relation.to not in nodes:
            continue
        scene.addItem(
            RelationItem(
                relation,
                nodes[relation.from_],
                nodes[relation.to],
                layout.edges.get(relation.layout_key, "straight"),
            )
        )
    # 이전 그림이 더 컸더라도 현재 그림에 맞춰 스크롤 영역을 다시 줄인다.
    bounds = scene.itemsBoundingRect()
    scene.setSceneRect(
        bounds.adjusted(-40, -40, 40, 40) if nodes else QRectF(0, 0, 80, 80)
    )
