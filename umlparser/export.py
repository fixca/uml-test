"""SVG/PNG/JPEG 내보내기. 담당: 이찬혁 (B9, B10).

umlparser 패키지에서 PyQt 를 import 하는 유일한 모듈이다 (docs/00-common.md 3장).

- 내보내는 범위: 장면의 그림 영역(itemsBoundingRect) + 사방 여백 20px
- 배경: 흰색. 장면의 배경 브러시(격자 등)와 선택 테두리는 내보낸 그림에 넣지 않는다.
- SVG: QSvgGenerator 로 렌더링해 글자가 <text> 벡터로 남는다 (논문용).
  scale 은 무시한다.
- PNG/JPEG: QImage 에 scale 배(1x/2x/4x)로 렌더링한다. JPEG 품질 95.
"""

from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import QGraphicsScene

MARGIN = 20.0
JPEG_QUALITY = 95
FORMATS = ("svg", "png", "jpeg")
_FORMAT_ALIASES = {"jpg": "jpeg"}
_BACKGROUND = QColor(Qt.GlobalColor.white)


class ExportError(Exception):
    pass


def export_scene(
    scene: QGraphicsScene, path: str, fmt: str, scale: float = 1.0
) -> None:
    """scene 을 path 에 fmt("svg" | "png" | "jpeg") 형식으로 저장한다.

    잘못된 fmt/scale 은 ValueError, 파일을 쓸 수 없으면 ExportError.
    """
    fmt = _FORMAT_ALIASES.get(fmt.lower(), fmt.lower())
    if fmt not in FORMATS:
        raise ValueError(
            f"지원하지 않는 형식입니다: {fmt!r} (지원: {', '.join(FORMATS)})"
        )
    if scale <= 0:
        raise ValueError(f"배율은 0보다 커야 합니다: {scale}")

    source = _export_rect(scene)
    selected = scene.selectedItems()
    background = scene.backgroundBrush()
    scene.clearSelection()
    scene.setBackgroundBrush(QBrush(_BACKGROUND))
    try:
        if fmt == "svg":
            _export_svg(scene, source, Path(path))
        else:
            _export_image(scene, source, Path(path), fmt, scale)
    finally:
        scene.setBackgroundBrush(background)
        for item in selected:
            item.setSelected(True)


def _export_rect(scene: QGraphicsScene) -> QRectF:
    """그림이 차지하는 영역 + 여백. 빈 장면이면 여백만큼의 빈 그림."""
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 0, 0)
    return rect.adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN)


def _export_svg(scene: QGraphicsScene, source: QRectF, path: Path) -> None:
    width, height = round(source.width()), round(source.height())
    target = QRectF(0, 0, width, height)

    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(QSize(width, height))
    generator.setViewBox(target)
    generator.setTitle(path.stem)

    painter = QPainter()
    if not painter.begin(generator):
        raise ExportError(f"SVG 파일을 쓸 수 없습니다: {path}")
    try:
        painter.fillRect(target, _BACKGROUND)
        scene.render(painter, target, source)
    finally:
        painter.end()


def _export_image(
    scene: QGraphicsScene, source: QRectF, path: Path, fmt: str, scale: float
) -> None:
    width = max(1, round(source.width() * scale))
    height = max(1, round(source.height() * scale))

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(_BACKGROUND)

    painter = QPainter()
    if not painter.begin(image):
        raise ExportError(f"이미지를 만들 수 없습니다: {width}x{height}")
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scene.render(painter, QRectF(0, 0, width, height), source)
    finally:
        painter.end()

    if fmt == "jpeg":
        image = image.convertToFormat(QImage.Format.Format_RGB32)  # JPEG 는 알파 없음
        ok = image.save(str(path), "JPEG", JPEG_QUALITY)
    else:
        ok = image.save(str(path), "PNG")
    if not ok:
        raise ExportError(f"{fmt.upper()} 파일을 쓸 수 없습니다: {path}")
