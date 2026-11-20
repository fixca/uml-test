"""시퀀스 참여자의 열 순서를 기존 레이아웃에 저장한다."""

from umlparser.sequence import Sequence
from umlparser.storage import Layout


def participant_key(name: str) -> str:
    return f"sequence:{name}"


def ordered_ids(sequence: Sequence, layout: Layout) -> list[str]:
    # 저장된 순서가 없는 새 참여자는 선언 순서대로 뒤에 추가한다.
    return sorted(
        sequence.participants,
        key=lambda name: layout.nodes.get(participant_key(name), (float("inf"), 0))[0],
    )


def reorder(sequence: Sequence, layout: Layout, key: str, column: int) -> bool:
    names = ordered_ids(sequence, layout)
    name = key.removeprefix("sequence:")
    if name not in names:
        return False
    target = max(0, min(column, len(names) - 1))
    if target == names.index(name):
        return False
    names.remove(name)
    names.insert(target, name)
    for index, participant in enumerate(names):
        layout.nodes[participant_key(participant)] = (float(index), 0.0)
    return True
