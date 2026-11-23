"""운영체제 테마와 관계없이 라이트 화면을 유지하는지 검증한다."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPalette
from PyQt6.QtWidgets import QApplication, QSplitter

from gui.items.relation_item import RelationItem
from gui.main_window import MainWindow
from umlparser.export import export_scene
from umlparser.storage import Layout, Project


@pytest.mark.parametrize("system_dark", [False, True])
@pytest.mark.parametrize(
    "code",
    [
        'classDiagram\nA "1" --> "*" B: link\n',
        "sequenceDiagram\nactor User\nparticipant API\n"
        "User->>+API: call\nAPI-->>-User: done\n",
    ],
)
def test_light_mode_is_forced(tmp_path: Path, system_dark: bool, code: str) -> None:
    app = QApplication.instance() or QApplication([])
    original = QPalette(app.palette())
    system = QPalette(original)
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base):
        system.setColor(role, QColor("#202124" if system_dark else "#ffffff"))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text):
        system.setColor(role, QColor("#ffffff" if system_dark else "#202124"))
    app.setPalette(system)
    window = MainWindow(restore_last=False)
    try:
        window.controller.set_project(Project(code, Layout(), None))
        window.show()
        app.processEvents()
        before = window.controller.snapshot()
        assert "theme_dark" not in window.actions
        assert "theme_light" not in window.actions
        assert window.menuBar().cornerWidget(Qt.Corner.TopRightCorner) is None
        assert (
            window.editor.palette().color(QPalette.ColorRole.Base).name() == "#ffffff"
        )
        assert (
            window.editor.palette().color(QPalette.ColorRole.Text).name() == "#202124"
        )
        handle = window.findChild(QSplitter).handle(1)
        image = handle.grab().toImage()
        assert (
            image.pixelColor(image.width() // 2, image.height() // 2).name()
            == "#e5e7eb"
        )
        window.controller.redraw()
        assert window.scene.backgroundBrush().color().name() == "#ffffff"
        assert window.view.backgroundBrush().color().name() == "#ffffff"
        for item in window.scene.items():
            if isinstance(item, RelationItem):
                item.update_geometry()
                assert item.pen().color().lightness() < 128
        output = tmp_path / "light.png"
        export_scene(window.scene, str(output), "png")
        exported = QImage(str(output))
        assert not exported.isNull()
        assert exported.pixelColor(0, 0).name() == "#ffffff"
        assert window.controller.snapshot() == before
        assert not window.controller.dirty
    finally:
        window.close()
        app.setPalette(original)
        app.processEvents()
