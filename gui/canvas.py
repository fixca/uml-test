"""팩토리에 전달할 장면과 공통 상호작용 시그널."""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene


class DiagramSignals(QObject):
    moved = pyqtSignal(str, float, float)
    double_clicked = pyqtSignal(str)
    edge_toggled = pyqtSignal(str)


class DiagramScene(QGraphicsScene):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.signals = DiagramSignals(self)

    def selected_class_ids(self) -> list[str]:
        return list(
            dict.fromkeys(
                item.data(0)
                for item in self.selectedItems()
                if isinstance(item.data(0), str)
            )
        )
