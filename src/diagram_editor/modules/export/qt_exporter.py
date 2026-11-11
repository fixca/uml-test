"""Qt graphics export adapter and pluggable format registry."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QBrush


@dataclass(frozen=True)
class ExportOptions:
    scale: float = 2.0
    margin: int = 40
    transparent: bool = False
    background: str = "#ffffff"


class QtImageExporter:
    def __init__(self, format_name: str):
        self.format_name = format_name

    def export(self, scene, path: str, options: ExportOptions):
        bounds = scene.itemsBoundingRect()
        if bounds.isEmpty():
            raise ValueError("내보낼 객체가 없습니다")
        pixel_width = max(1, round(bounds.width() * options.scale) + 2 * options.margin)
        pixel_height = max(1, round(bounds.height() * options.scale) + 2 * options.margin)
        if pixel_width > 32000 or pixel_height > 32000 or pixel_width * pixel_height > 100_000_000:
            raise ValueError("출력 픽셀 수가 너무 큽니다. 배율을 낮추세요")
        transparent = self.format_name == "PNG" and options.transparent
        image = QImage(pixel_width, pixel_height,
                       QImage.Format.Format_ARGB32_Premultiplied if transparent else QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.transparent if transparent else QColor(options.background))
        # QGraphicsScene has a dark interactive background. Temporarily omit it
        # so transparent PNG / white JPEG backgrounds work as configured.
        old_background = scene.backgroundBrush()
        selected_items = list(scene.selectedItems())
        for item in selected_items: item.setSelected(False)
        scene.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            scene.render(painter, QRectF(options.margin, options.margin,
                                          bounds.width() * options.scale, bounds.height() * options.scale),
                         bounds, Qt.AspectRatioMode.IgnoreAspectRatio)
        finally:
            painter.end()
            scene.setBackgroundBrush(old_background)
            for item in selected_items: item.setSelected(True)
        if not image.save(path, self.format_name, 95 if self.format_name == "JPEG" else -1):
            raise OSError("이미지 파일 저장에 실패했습니다")
        return pixel_width, pixel_height


class ExporterRegistry:
    def __init__(self):
        self._registry = {}
        self.register(QtImageExporter("PNG"))
        self.register(QtImageExporter("JPEG"))

    def register(self, exporter):
        self._registry[exporter.format_name] = exporter

    def get(self, name: str):
        return self._registry[name]
