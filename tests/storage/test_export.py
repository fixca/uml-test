"""export.py 테스트 (B9, B10). 화면 없이 offscreen 플랫폼으로 실행한다."""

import os
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QBrush, QColor, QImage  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

from umlparser.export import MARGIN, ExportError, export_scene  # noqa: E402

BOX = (100.0, 50.0, 200.0, 120.0)  # x, y, w, h


@pytest.fixture(scope="module")
def app() -> Iterator[QApplication]:
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def scene(app: QApplication) -> QGraphicsScene:
    scene = QGraphicsScene()
    box = QGraphicsRectItem(*BOX)
    box.setBrush(QBrush(QColor("#ddeeff")))
    box.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
    scene.addItem(box)
    text = QGraphicsSimpleTextItem("사용자 User")
    text.setPos(BOX[0] + 10, BOX[1] + 10)
    scene.addItem(text)
    return scene


def expected_size(scene: QGraphicsScene, scale: float = 1.0) -> tuple[int, int]:
    rect = scene.itemsBoundingRect()
    return round((rect.width() + 2 * MARGIN) * scale), round(
        (rect.height() + 2 * MARGIN) * scale
    )


# ---------------------------------------------------------------- B9 SVG


def test_svg_has_vector_text_and_tight_size(
    scene: QGraphicsScene, tmp_path: Path
) -> None:
    path = tmp_path / "그림.svg"
    export_scene(scene, str(path), "svg")

    root = ET.parse(path).getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}
    texts = [t for t in root.iter(f"{{{ns['svg']}}}text")]
    assert any(
        "사용자" in "".join(t.itertext()) for t in texts
    )  # 글자가 벡터(<text>)로 남음

    width, height = expected_size(scene)
    assert root.get("viewBox") == f"0 0 {width} {height}"


def test_svg_ignores_scale(scene: QGraphicsScene, tmp_path: Path) -> None:
    a, b = tmp_path / "a.svg", tmp_path / "b.svg"
    export_scene(scene, str(a), "svg", 1.0)
    export_scene(scene, str(b), "svg", 4.0)
    assert ET.parse(a).getroot().get("viewBox") == ET.parse(b).getroot().get("viewBox")


# ---------------------------------------------------------------- B10 PNG/JPEG


@pytest.mark.parametrize("scale", [1.0, 2.0, 4.0])
def test_png_scale_and_white_margin(
    scene: QGraphicsScene, tmp_path: Path, scale: float
) -> None:
    path = tmp_path / f"x{scale}.png"
    export_scene(scene, str(path), "png", scale)

    image = QImage(str(path))
    assert (image.width(), image.height()) == expected_size(scene, scale)
    assert image.pixelColor(0, 0) == QColor(Qt.GlobalColor.white)  # 여백은 흰 배경
    center = image.pixelColor(image.width() // 2, image.height() // 2)
    assert center != QColor(Qt.GlobalColor.white)  # 그림이 실제로 그려짐


@pytest.mark.parametrize("fmt", ["jpeg", "jpg", "JPEG"])
def test_jpeg_has_white_background(
    scene: QGraphicsScene, tmp_path: Path, fmt: str
) -> None:
    path = tmp_path / "x.jpg"
    export_scene(scene, str(path), fmt, 2.0)

    image = QImage(str(path))
    assert (image.width(), image.height()) == expected_size(scene, 2.0)
    corner = image.pixelColor(0, 0)
    assert min(corner.red(), corner.green(), corner.blue()) >= 250


# ---------------------------------------------------------------- 공통 동작


def test_scene_background_and_selection_are_not_exported(
    scene: QGraphicsScene, tmp_path: Path
) -> None:
    grid = QBrush(QColor("#ff0000"))
    scene.setBackgroundBrush(grid)
    box = next(i for i in scene.items() if isinstance(i, QGraphicsRectItem))
    box.setSelected(True)

    path = tmp_path / "x.png"
    export_scene(scene, str(path), "png")

    assert QImage(str(path)).pixelColor(0, 0) == QColor(Qt.GlobalColor.white)
    assert scene.backgroundBrush() == grid  # 내보낸 뒤 원래대로 복원
    assert box.isSelected()


def test_empty_scene_exports_margin_only(app: QApplication, tmp_path: Path) -> None:
    path = tmp_path / "empty.png"
    export_scene(QGraphicsScene(), str(path), "png")
    image = QImage(str(path))
    assert (image.width(), image.height()) == (round(2 * MARGIN), round(2 * MARGIN))


def test_invalid_format_and_scale(scene: QGraphicsScene, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_scene(scene, str(tmp_path / "x.pdf"), "pdf")
    with pytest.raises(ValueError):
        export_scene(scene, str(tmp_path / "x.png"), "png", 0)


def test_unwritable_path_raises_export_error(
    scene: QGraphicsScene, tmp_path: Path
) -> None:
    missing = tmp_path / "없는 폴더"
    with pytest.raises(ExportError):
        export_scene(scene, str(missing / "x.png"), "png")
    with pytest.raises(ExportError):
        export_scene(scene, str(missing / "x.svg"), "svg")
