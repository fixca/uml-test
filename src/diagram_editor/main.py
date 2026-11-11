"""Desktop application entry point."""
import logging
import os
import sys


def main():
    from PyQt6.QtWidgets import QApplication
    from diagram_editor.presentation.pyqt.main_window import MainWindow
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("OfflineDiagramEditor")
    app.setOrganizationName("DiagramEditor")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
