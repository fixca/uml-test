"""다이어그램 종류별 렌더러의 공통 인터페이스."""

from abc import ABC, abstractmethod
from typing import ClassVar, Protocol

from PyQt6.QtWidgets import QGraphicsScene

from gui.canvas import DiagramSignals
from umlparser.model import ParseError
from umlparser.storage import Layout


class PasteError(ValueError):
    """붙여넣기를 거부할 때 쓴다. 메시지는 상태줄에 그대로 표시된다."""


class Diagram(Protocol):
    """모든 파서 결과가 공통으로 갖는 필드."""

    type: str
    errors: list[ParseError]


class DiagramRenderer(ABC):
    diagram_type: ClassVar[str] = ""  # 이 렌더러가 그리는 Diagram.type

    @abstractmethod
    def render(
        self,
        scene: QGraphicsScene,
        diagram: Diagram,
        layout: Layout,
        signals: DiagramSignals,
    ) -> None:
        """오류가 없는 모델을 장면에 그린다.

        아직 지원하지 않는 종류는 안내를 그린 뒤 NotImplementedError를
        던져 컨트롤러가 내보내기를 막게 한다.
        """

    # 아래 메서드는 지원하지 않는 기본 동작을 두어, 필요한 종류만 덮어쓴다.
    def node_ids(self, diagram: Diagram) -> set[str]:
        """끌어서 옮긴 위치를 layout 좌표로 저장할 노드 ID 집합."""
        return set()

    def edge_keys(self, diagram: Diagram) -> set[str]:
        """직선·직각 전환과 꺾임을 저장할 수 있는 관계선의 layout key 집합."""
        return set()

    def source_line(self, diagram: Diagram, node_id: str) -> int | None:
        """더블클릭한 노드가 정의된 원문 줄 번호. 알 수 없으면 None."""
        return None

    def moved_code(
        self, code: str, diagram: Diagram, node_id: str, x: float, y: float
    ) -> str | None:
        """노드를 옮긴 결과를 원문 수정으로 반영하는 종류면 새 코드를 돌려준다.

        위치를 layout 좌표로 저장하는 종류면 None을 돌려준다.
        """
        return None

    def copy_block(self, code: str, node_id: str) -> str | None:
        """node_id를 복사할 수 있는 원문 블록으로 돌려준다. 복사할 수 없으면 None."""
        return None

    def paste_block(self, code: str, diagram: Diagram, block: str) -> tuple[str, str]:
        """복사한 block을 code 끝에 붙인 (새 원문, 새 노드 ID)를 돌려준다.

        기본 구현은 붙여넣기를 지원하지 않으므로 항상 PasteError를 낸다.
        """
        raise PasteError("이 다이어그램에서는 붙여넣기를 지원하지 않습니다.")
