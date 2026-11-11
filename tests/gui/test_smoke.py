"""Opt-in GUI test: RUN_QT_TESTS=1 QT_QPA_PLATFORM=offscreen pytest tests/gui."""
import os
import pytest

if os.environ.get('RUN_QT_TESTS') != '1':
    pytest.skip('Requires an explicit Qt-enabled GUI test environment',allow_module_level=True)
pytest.importorskip('PyQt6')


def test_window_opens_and_has_two_panels():
    from PyQt6.QtWidgets import QApplication
    from diagram_editor.presentation.pyqt.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    win = MainWindow(new_document=True)
    assert win.tabs.count() == 1
    assert win.current().splitter.count() == 2
    win.current().session.saved_revision = win.current().session.edit_revision
    win.close()
