"""모델 → 그림 요소 생성. 담당: 이도훈 (F3, F4).

F3: build(scene, diagram, layout)으로 정상 모델의 장면을 다시 그린다.
위치가 없는 클래스는 auto_layout으로 배치한다.
F4의 상호작용을 scene.signals로 모아 컨트롤러에 전달한다.
F5: 오류 모델은 마지막 정상 그림과 layout을 유지한다.
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtWidgets import QGraphicsScene

from gui.auto_layout import fill_missing_positions
from gui.canvas import DiagramSignals
from gui.items.class_item import ClassItem
from gui.items.relation_item import RelationItem
from umlparser.model import ClassDiagram
from umlparser.storage import Layout


def build(scene: QGraphicsScene, diagram: ClassDiagram, layout: Layout) -> None:
    """수동 좌표와 scene.signals를 보존하고 누락된 초기 좌표만 채운다.

    부분 모델에서 끝점이 없는 관계는 건너뛴다. 마지막 정상 그림의 유지는
    기존 컨트롤러 validate()가 담당한다. 이 함수는 전달된 모델을 그린다.
    """
    # 오류 모델은 정상 그림과 저장된 배치를 덮어쓰지 않는다.
    # 컨트롤러도 같은 정책을 쓰지만 직접 호출하는 경우까지 보호한다.
    if diagram.errors:
        return

    signals = getattr(scene, "signals", None)
    if signals is None:
        signals = DiagramSignals(scene)
        scene.signals = signals

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
        relation_item = RelationItem(relation, source_item, target_item, mode)
        scene.addItem(relation_item)
        # 드래그 중에는 모델이나 layout을 바꾸지 않고 선만 따라 움직인다.
        source_item.xChanged.connect(relation_item.update_geometry)
        source_item.yChanged.connect(relation_item.update_geometry)
        if target_item is not source_item:
            target_item.xChanged.connect(relation_item.update_geometry)
            target_item.yChanged.connect(relation_item.update_geometry)
    # 이전 그림이 더 컸더라도 현재 그림에 맞춰 스크롤 영역을 다시 줄인다.
    bounds = scene.itemsBoundingRect()
    scene.setSceneRect(
        bounds.adjusted(-40, -40, 40, 40) if nodes else QRectF(0, 0, 80, 80)
    )
