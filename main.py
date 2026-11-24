"""앱 진입점. 담당: 강승현 (F6)."""

import sys

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> None:
    """메인 창을 열고 이벤트 루프가 끝나면 그 상태 코드로 앱을 종료한다."""
    app = QApplication(sys.argv)
    app.setApplicationName("UML 도구")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
