"""
AetherPDF Application Entry Point.

This module initializes the PySide6 QApplication, applies the custom
Aether Dark Theme, and starts the MainWindow event loop.
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from config.theme import apply_theme
from views.main_window import MainWindow


def main() -> None:
    """
    Bootstrap the AetherPDF application.
    
    Creates QApplication, applies the neon dark theme, and runs the MainWindow.
    """
    # [NEW] Windows 작업표시줄(테스크 바)에서 Python 기본 아이콘 병합을 차단하고
    # AetherPDF 고유 아이콘이 독립적으로 표시되도록 고유 AppUserModelID를 OS에 등록합니다.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "aetherpdf.deepmind.desktop.v1"
        )
    except (ImportError, AttributeError, OSError):
        # Windows 이외의 OS에서는 이 호출이 불필요하므로 안전하게 무시합니다.
        pass

    # Create the application instance
    app = QApplication(sys.argv)
    
    # Configure application metadata
    app.setApplicationName("AetherPDF")
    app.setApplicationDisplayName("AetherPDF Editor")
    app.setOrganizationName("Aether")

    # [NEW] 앱 전역 아이콘 설정 (작업표시줄 그룹 아이콘에도 적용됨)
    # PyInstaller 번들 실행 시 sys._MEIPASS 경로에서 assets를 탐색합니다.
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Apply the Aether Dark QSS stylesheet
    apply_theme(app)

    # Initialize and display the Main Window
    window = MainWindow()
    window.show()

    # Enter the Qt application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

