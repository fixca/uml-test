"""사용자 테마 전환과 설정 복원을 검증한다."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


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
    assert window.theme_button.isChecked() == dark
    assert (
        window.menuBar().cornerWidget(Qt.Corner.TopRightCorner) is window.theme_button
    )
    assert window.theme_button.geometry().right() >= window.menuBar().width() - 5
    QTest.mouseClick(window.theme_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert window.theme_button.isChecked() != dark
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
    assert restored.theme_button.isChecked() == (expected == "dark")
    restored.close()
    app.processEvents()
