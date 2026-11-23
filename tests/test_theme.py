"""사용자 테마 전환과 설정 복원을 검증한다."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QImage, QPalette
from PyQt6.QtWidgets import QApplication, QSplitter

from gui.items.relation_item import RelationItem
from gui.main_window import MainWindow
from umlparser.export import export_scene
from umlparser.storage import Layout, Project


@pytest.mark.parametrize("initial", ["light", "dark"])
def test_theme_toggle_and_restore(tmp_path: Path, initial: str) -> None:
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    settings.setValue("theme", initial)
    window = MainWindow(restore_last=False, settings=settings)
    window.show()
    app.processEvents()
    before = window.controller.snapshot()
    history = window.controller.history_index
    dark = initial == "dark"
    assert window.actions["theme_dark"].isChecked() == dark
    assert window.menuBar().cornerWidget(Qt.Corner.TopRightCorner) is None
    window.actions["theme_light" if dark else "theme_dark"].trigger()
    app.processEvents()
    assert window.actions["theme_dark"].isChecked() != dark
    assert (
        window.editor.palette().color(QPalette.ColorRole.Base).lightness() < 128
    ) != dark
    assert window.controller.snapshot() == before
    assert window.controller.history_index == history
    assert not window.controller.dirty
    expected = "light" if dark else "dark"
    assert settings.value("theme") == expected
    window.close()
    restored = MainWindow(
        restore_last=False,
        settings=QSettings(
            str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat
        ),
    )
    assert restored.actions["theme_dark"].isChecked() == (expected == "dark")
    restored.close()
    app.processEvents()


@pytest.mark.parametrize(
    "code",
    [
        'classDiagram\nA "1" --> "*" B: link\n',
        "sequenceDiagram\nactor User\nparticipant API\n"
        "User->>+API: call\nAPI-->>-User: done\n",
    ],
)
def test_canvas_splitter_and_export_follow_theme(tmp_path: Path, code: str) -> None:
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat)
    settings.setValue("theme", "light")
    window = MainWindow(restore_last=False, settings=settings)
    window.controller.set_project(Project(code, Layout(), None))
    window.show()
    app.processEvents()
    before = window.controller.snapshot()
    handle = window.findChild(QSplitter).handle(1)

    def handle_color() -> str:
        image = handle.grab().toImage()
        return image.pixelColor(image.width() // 2, image.height() // 2).name()

    assert handle_color() == "#e5e7eb"
    light_path = tmp_path / "light.png"
    dark_path = tmp_path / "dark.png"
    export_scene(window.scene, str(light_path), "png")
    window.actions["theme_dark"].trigger()
    app.processEvents()
    assert handle_color() == "#303134"
    assert window.scene.backgroundBrush().color().lightness() < 128
    assert window.view.backgroundBrush().color().lightness() < 128
    for item in window.scene.items():
        if isinstance(item, RelationItem):
            assert item.pen().color().lightness() > 128
            item.update_geometry()
            assert item.pen().color().lightness() > 128
    export_scene(window.scene, str(dark_path), "png")
    assert QImage(str(light_path)) == QImage(str(dark_path))
    assert window.scene.property("dark_mode") is True
    window.controller.redraw()
    assert window.scene.backgroundBrush().color().lightness() < 128
    window.actions["theme_light"].trigger()
    app.processEvents()
    assert handle_color() == "#e5e7eb"
    assert window.scene.backgroundBrush().color().name() == "#ffffff"
    assert window.controller.snapshot() == before
    window.close()
