"""캔버스 색상 전환. 모델과 저장된 레이아웃은 변경하지 않는다."""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractGraphicsShapeItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
)

COLORS = {
    "#ffffff": "#202124",
    "#000000": "#e5e7eb",
    "#334155": "#cbd5e1",
    "#808080": "#9ca3af",
}


def is_dark(scene: QGraphicsScene | None) -> bool:
    return scene is not None and scene.property("dark_mode") is True


def canvas_color(scene: QGraphicsScene | None, color: str) -> QColor:
    return QColor(COLORS.get(color, color) if is_dark(scene) else color)


def apply_item_theme(item: QGraphicsItem, dark: bool) -> None:
    colors = COLORS if dark else {value: key for key, value in COLORS.items()}
    if isinstance(item, QAbstractGraphicsShapeItem | QGraphicsLineItem):
        pen = item.pen()
        pen.setColor(QColor(colors.get(pen.color().name(), pen.color().name())))
        item.setPen(pen)
    if isinstance(item, QAbstractGraphicsShapeItem | QGraphicsSimpleTextItem):
        brush = item.brush()
        brush.setColor(QColor(colors.get(brush.color().name(), brush.color().name())))
        item.setBrush(brush)
    if isinstance(item, QGraphicsTextItem):
        color = item.defaultTextColor()
        item.setDefaultTextColor(QColor(colors.get(color.name(), color.name())))


def apply_scene_theme(scene: QGraphicsScene) -> None:
    for item in scene.items():
        apply_item_theme(item, is_dark(scene))
    scene.update()
