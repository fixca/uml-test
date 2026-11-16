"""위치 없는 클래스 자동 배치. 담당: 이도훈 (F3).

상속·구현 관계를 기준으로 부모가 위, 자식이 아래에 오도록 격자 배치한다.
기존 수동 좌표는 유지하고, 없는 좌표만 layout.nodes에 채운다.
외부 배치 라이브러리는 사용하지 않는다.
"""

from collections import deque
from math import ceil, sqrt

from umlparser.model import ClassDiagram
from umlparser.storage import Layout

GAP_X = 80.0
GAP_Y = 90.0
MARGIN = 40.0


def _layers(diagram: ClassDiagram) -> dict[str, int]:
    """순환 상속은 같은 그룹으로 묶은 뒤 부모→자식 순으로 층을 계산한다."""
    ids = list(dict.fromkeys(node.id for node in diagram.classes))
    # 모델의 상속·구현은 from_=자식, to=부모로 정규화되어 있다.
    children = {class_id: set() for class_id in ids}
    for relation in diagram.relations:
        if (
            relation.kind in ("inheritance", "realization")
            and relation.from_ in children
            and relation.to in children
        ):
            children[relation.to].add(relation.from_)

    # 각 노드에서 도달 가능한 노드를 구해 순환 관계를 찾는다.
    reachable = {}
    for start in ids:
        seen, pending = set(), [start]
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(children[current] - seen)
        reachable[start] = seen

    # 서로 도달할 수 있는 노드들은 같은 층에서 처리할 그룹으로 묶는다.
    groups, group_of = [], {}
    for class_id in ids:
        if class_id in group_of:
            continue
        members = [
            other
            for other in ids
            if other in reachable[class_id] and class_id in reachable[other]
        ]
        for member in members:
            group_of[member] = len(groups)
        groups.append(members)

    # 그룹 사이의 관계만 남기면 순환이 사라져 부모부터 순서대로 처리할 수 있다.
    outgoing = [set() for _ in groups]
    indegree = [0] * len(groups)
    for parent, targets in children.items():
        for child in targets:
            source, target = group_of[parent], group_of[child]
            if source != target and target not in outgoing[source]:
                outgoing[source].add(target)
                indegree[target] += 1
    # 여러 부모가 있으면 가장 깊은 부모보다 한 층 아래에 배치한다.
    levels = [0] * len(groups)
    ready = deque(i for i, degree in enumerate(indegree) if degree == 0)
    while ready:
        source = ready.popleft()
        for target in sorted(outgoing[source]):
            levels[target] = max(levels[target], levels[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    return {class_id: levels[group_of[class_id]] for class_id in ids}


def fill_missing_positions(
    diagram: ClassDiagram, layout: Layout, sizes: dict[str, tuple[float, float]]
) -> None:
    """sizes는 실제 박스 크기. 수동 배치 박스와 겹치는 격자는 건너뛴다."""
    if not sizes:
        return
    levels = _layers(diagram)
    columns = max(1, ceil(sqrt(len(sizes))))
    # 가장 큰 박스를 기준으로 격자 간격을 잡는다.
    cell_width = max(width for width, _ in sizes.values()) + GAP_X
    cell_height = max(height for _, height in sizes.values()) + GAP_Y
    # 현재 모델에 있는 수동 배치 박스만 충돌 검사에 포함한다.
    occupied = [
        (x, y, x + sizes[key][0], y + sizes[key][1])
        for key, (x, y) in layout.nodes.items()
        if key in sizes
    ]
    row = 0
    for level in sorted(set(levels.values())):
        members = [key for key in sizes if levels[key] == level]
        slot = 0
        for key in members:
            if key in layout.nodes:
                continue
            width, height = sizes[key]
            # 수동 박스와 겹치는 칸은 건너뛰고 다음 빈 칸을 찾는다.
            while True:
                x = MARGIN + (slot % columns) * cell_width
                y = MARGIN + (row + slot // columns) * cell_height
                slot += 1
                if not any(
                    x < right + GAP_X / 2
                    and x + width + GAP_X / 2 > left
                    and y < bottom + GAP_Y / 2
                    and y + height + GAP_Y / 2 > top
                    for left, top, right, bottom in occupied
                ):
                    break
            # 저장·Undo·복사 위치에 반영되도록 전달받은 layout에 직접 기록한다.
            layout.nodes[key] = (x, y)
            occupied.append((x, y, x + width, y + height))
        row += max(1, ceil(slot / columns))
