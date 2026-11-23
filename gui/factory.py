"""모델 → 그림 요소 생성. 담당: 이도훈 (F3, F4, F5).

다이어그램 종류에 맞는 렌더러에 그리기를 맡기는 진입점이다.
F3: build(scene, diagram, layout)으로 정상 모델의 장면을 다시 그린다.
F4의 상호작용을 scene.signals로 모아 컨트롤러에 전달한다.
F5: 오류 모델은 마지막 정상 그림과 layout을 유지한다.
"""

from PyQt6.QtWidgets import QGraphicsScene

from gui.canvas import DiagramSignals
from gui.renderers import Diagram, renderer_for
from gui.theme import apply_scene_theme
from umlparser.storage import Layout


def build(scene: QGraphicsScene, diagram: Diagram, layout: Layout) -> None:
    """오류 모델이면 그대로 두고, 아니면 종류별 렌더러가 장면을 다시 그린다.

    렌더러가 아직 지원하지 않는 종류면 NotImplementedError가 전달된다.
    오류 줄과 상태줄 메시지 표시는 기존 컨트롤러·편집기가 담당한다.
    """
    # 오류 모델은 정상 그림과 저장된 배치를 덮어쓰지 않는다.
    # 컨트롤러도 같은 정책을 쓰지만 직접 호출하는 경우까지 보호한다.
    if diagram.errors:
        return

    # 기존 장면의 시그널 객체를 재사용해 컨트롤러 연결을 유지한다.
    signals = getattr(scene, "signals", None)
    if signals is None:
        signals = DiagramSignals(scene)
        scene.signals = signals

    renderer_for(diagram).render(scene, diagram, layout, signals)
    apply_scene_theme(scene)
