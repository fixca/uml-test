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
    diagram_type: ClassVar[str] = ""  # 담당하는 Diagram.type

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

    # 아래 셋은 기본 구현(빈 값)을 둔다. stub는 고치지 않아도 된다.
    def node_ids(self, diagram: Diagram) -> set[str]:
        """moved 시그널을 허용할 노드 ID."""
        return set()

    def edge_keys(self, diagram: Diagram) -> set[str]:
        """edge_toggled 시그널을 허용할 layout key."""
        return set()

    def source_line(self, diagram: Diagram, node_id: str) -> int | None:
        """더블 클릭 시 이동할 원문 줄 번호."""
        return None

    def copy_block(self, code: str, node_id: str) -> str | None:
        """node_id의 원문 블록. 복사할 수 없으면 None."""
        return None

    def paste_block(self, code: str, diagram: Diagram, block: str) -> tuple[str, str]:
        """block을 code 끝에 붙인 (새 원문, 새 노드 ID). 거부하면 PasteError."""
        raise PasteError("이 다이어그램에서는 붙여넣기를 지원하지 않습니다.")
