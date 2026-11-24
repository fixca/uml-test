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
    """부모가 위, 자식이 아래에 오도록 클래스별 배치 층을 정한다.

    순환 상속에 얽힌 클래스는 같은 층에 둔다.
    """
    ids = list(dict.fromkeys(node.id for node in diagram.classes))
    # 부모에서 자식으로 향하는 상속·구현 관계만 모은다. (from_=자식, to=부모)
    children = {class_id: set() for class_id in ids}
    for relation in diagram.relations:
        if (
            relation.kind in ("inheritance", "realization")
            and relation.from_ in children
            and relation.to in children
        ):
            children[relation.to].add(relation.from_)

    # 같은 층에 놓아야 할 순환 관계를 찾기 위해 클래스별 하위 클래스 전체를 구한다.
    reachable = {}
    for start in ids:
        seen, pending = set(), [start]
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(children[current] - seen)
        reachable[start] = seen

    # 서로 상속하는 순환 클래스들을 하나의 배치 그룹으로 묶는다.
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

    # 그룹 사이의 부모→자식 순서를 정리한다. (그룹 안의 순환은 이미 묶여 사라진다.)
    outgoing = [set() for _ in groups]
    indegree = [0] * len(groups)
    for parent, targets in children.items():
        for child in targets:
            source, target = group_of[parent], group_of[child]
            if source != target and target not in outgoing[source]:
                outgoing[source].add(target)
                indegree[target] += 1
    # 자식 그룹을 모든 부모 그룹보다 아래 층에 놓는다.
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
    """좌표가 없는 클래스에만 다른 박스와 겹치지 않는 격자 위치를 정해 준다.

    sizes는 클래스별 실제 박스 크기이고, 이미 있는 수동 좌표는 바꾸지 않는다.
    """
    if not sizes:
        return
    levels = _layers(diagram)
    columns = max(1, ceil(sqrt(len(sizes))))
    # 가장 큰 클래스도 들어가도록 격자 칸 크기를 정한다.
    cell_width = max(width for width, _ in sizes.values()) + GAP_X
    cell_height = max(height for _, height in sizes.values()) + GAP_Y
    # 이미 좌표가 있는 클래스 영역을 새 박스가 피해야 할 자리로 예약한다.
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
            # 예약된 영역과 겹치지 않는 빈 칸을 찾는다.
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
            # 자동 배치한 좌표도 저장·Undo에 반영되도록 layout에 기록한다.
            layout.nodes[key] = (x, y)
            occupied.append((x, y, x + width, y + height))
        row += max(1, ceil(slot / columns))
