"""
AetherPDF Theme Stylesheets.

This module defines the QSS (Qt Style Sheets) for the Aether Dark Theme,
incorporating modern glassmorphism, vibrant neon gradients (Purple & Cyan),
and sleek dark charcoal tones to provide a premium user interface.
"""

AETHER_DARK_STYLESHEET: str = """
/* Global Application Style */
QMainWindow {
    background-color: #121214;
    color: #E1E1E6;
    font-family: "Segoe UI", "Inter", "Pretendard", sans-serif;
}

/* Central Canvas Area */
QGraphicsView {
    background-color: #0F0F11;
    border: none;
}

/* Custom Window Title Bar */
QWidget#titleBar {
    background-color: #101014;
    border-bottom: 1px solid #2E2E35;
}

QLabel#titleBarTitle {
    color: #E1E1E6;
    font-size: 12px;
    font-weight: 700;
}

QLabel#titleBarIcon {
    background-color: transparent;
}

QToolButton#titleBarButton,
QToolButton#titleBarCloseButton {
    background-color: transparent;
    color: #A9A9B2;
    border: none;
    border-radius: 4px;
    min-width: 32px;
    min-height: 24px;
    padding: 0px;
    margin: 0px;
    font-size: 14px;
    font-weight: 700;
}

QToolButton#titleBarButton:hover {
    background-color: #2A2A30;
    color: #00F0FF;
}

QToolButton#titleBarCloseButton:hover {
    background-color: #D92D20;
    color: #FFFFFF;
}

/* Sidebar Styling (Glassmorphic look) */
QFrame#sidebarFrame {
    background-color: #1B1B1F;
    border-right: 1px solid #2E2E35;
}

/* Top Toolbar Styling */
QFrame#toolbarFrame {
    background-color: #151518;
    border-bottom: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8A2BE2, stop:0.5 #4B0082, stop:1 #00F0FF);
    padding: 0px 12px;
}

/* File Action Group Frame */
QFrame#fileGroupFrame {
    background-color: #1C1C21;
    border: 1px solid #2E2E35;
    border-radius: 14px;
    padding: 1px;
}

QPushButton#fileOpenButton {
    background-color: transparent;
    border: none;
    color: #E1E1E6;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#fileOpenButton:hover {
    background-color: #2E2E35;
    color: #00F0FF;
}

/* HUD Document Info Display */
QFrame#infoDisplayFrame {
    background-color: #1A1A22;
    border: 1px solid rgba(138, 43, 226, 0.4);
    border-radius: 14px;
    padding: 2px 16px;
    margin: 4px 0px;
}

QLabel#infoDisplayLabel {
    color: #E1E1E6;
    font-size: 12px;
    font-weight: 600;
}

/* Mode Segment Group Frame */
QFrame#modeGroupFrame {
    background-color: #1C1C21;
    border: 1px solid #2E2E35;
    border-radius: 14px;
    padding: 1px;
}

QFrame#modeGroupFrame QToolButton {
    background-color: transparent;
    color: #A9A9B2;
    border: none;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}

QFrame#modeGroupFrame QToolButton:hover {
    background-color: #26262B;
    color: #E1E1E6;
}

QFrame#modeGroupFrame QToolButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #8A2BE2, stop:1 #5B13B5); /* Deep Neon Purple */
    border: none;
    color: #FFFFFF;
    font-weight: bold;
}

/* Zoom Unified Group Frame (Pill Shape) */
QFrame#zoomGroupFrame {
    background-color: #1C1C21;
    border: 1px solid #2E2E35;
    border-radius: 14px;
    padding: 1px;
}

QPushButton#zoomButton {
    background-color: transparent;
    border: none;
    color: #E1E1E6;
    border-radius: 12px;
    padding: 4px 8px;
    font-size: 11px;
}

QPushButton#zoomButton:hover {
    background-color: #2E2E35;
    color: #00F0FF;
}

QComboBox#zoomCombo {
    background-color: transparent;
    border: none;
    color: #E1E1E6;
    padding: 2px 4px;
    font-size: 12px;
    font-weight: 600;
}

QComboBox#zoomCombo:hover {
    color: #00F0FF;
}

QComboBox#zoomCombo::drop-down {
    border: none;
    width: 0px; /* Hide raw down button */
}

/* Property Panel Styling */
QFrame#propertiesFrame {
    background-color: #1B1B1F;
    border-left: 1px solid #2E2E35;
}

/* Labels */
QLabel {
    color: #E1E1E6;
    font-size: 13px;
}

QLabel#sidebarTitle, QLabel#propertiesTitle {
    font-weight: bold;
    font-size: 14px;
    color: #00F0FF; /* Aurora Cyan */
    padding: 8px 4px;
}

/* Custom Push Buttons with Neon Hover Effect */
QPushButton {
    background-color: #202024;
    color: #E1E1E6;
    border: 1px solid #2E2E35;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2A2A30;
    border: 1px solid #8A2BE2; /* Deep Purple Neon Border */
    color: #00F0FF; /* Aurora Cyan Text on Hover */
}

QPushButton:pressed {
    background-color: #16161A;
    border: 1px solid #00F0FF;
}

QPushButton:disabled {
    background-color: #121214;
    color: #5A5A65;
    border: 1px solid #202024;
}

/* Primary Action Buttons (Gradient style) */
QPushButton#primaryActionButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #8A2BE2, stop:1 #00F0FF);
    color: #121214;
    border: none;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#primaryActionButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #9B30FF, stop:1 #33F4FF);
}

QPushButton#primaryActionButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #7525C0, stop:1 #00CCD9);
}

/* Tool Buttons (Icon style buttons in Toolbar) */
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px;
    margin: 2px;
}

QToolButton:hover {
    background-color: #202024;
    border: 1px solid #8A2BE2;
}

QToolButton:checked {
    background-color: #2A2A30;
    border: 1px solid #00F0FF;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #151518;
    width: 12px;
    margin: 4px 2px 4px 2px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #00F0FF, stop:1 #8A2BE2);
    min-height: 28px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #33F4FF, stop:1 #9B30FF);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    border: none;
    background: #151518;
    height: 12px;
    margin: 2px 4px 2px 4px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #00F0FF, stop:1 #8A2BE2);
    min-width: 28px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #33F4FF, stop:1 #9B30FF);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

QAbstractScrollArea::corner {
    background: #151518;
}

/* Text Inputs (QLineEdit, QTextEdit) */
QLineEdit, QTextEdit {
    background-color: #1A1A1E;
    color: #E1E1E6;
    border: 1px solid #2E2E35;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #8A2BE2;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #00F0FF; /* Neon Cyan glow on focus */
}

/* List/Tree Widget for Thumbnails */
QListWidget {
    background-color: transparent;
    border: none;
    outline: 0;
}

QListWidget::item {
    background-color: #202024;
    color: #E1E1E6;
    border: 1px solid #2E2E35;
    border-radius: 6px;
    padding: 8px;
    margin: 4px 8px;
}

QListWidget::item:hover {
    border: 1px solid #8A2BE2;
}

QListWidget::item:selected {
    background-color: #2A2A30;
    border: 2px solid #00F0FF; /* Glowing border for selected page */
    color: #00F0FF;
}

/* Menu and Menu Bar */
QMenuBar {
    background-color: #121214;
    color: #A9A9B2;
    border-bottom: 1px solid #2E2E35;
    font-size: 12px;
    font-weight: 500;
    padding: 0px 6px;
}

QMenuBar::item {
    background-color: transparent;
    padding: 3px 10px;
    margin: 0px 2px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #202024;
    color: #00F0FF;
}

QMenu {
    background-color: #1B1B1F;
    color: #E1E1E6;
    border: 1px solid #8A2BE2; /* Aurora Purple glow */
    border-radius: 6px;
    padding: 4px;
    font-size: 12px;
}

QMenu::item {
    padding: 6px 24px 6px 16px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8A2BE2, stop:1 #5B13B5);
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background-color: #2E2E35;
    margin: 4px 8px;
}

/* SpinBox & ComboBox */
QComboBox, QSpinBox {
    background-color: #202024;
    color: #E1E1E6;
    border: 1px solid #2E2E35;
    border-radius: 4px;
    padding: 4px 8px;
}

QComboBox:hover, QSpinBox:hover {
    border: 1px solid #8A2BE2;
}

QComboBox::drop-down {
    border: none;
}

/* Native message boxes use a light surface, so keep their content dark. */
QMessageBox {
    background-color: #F4F4F5;
}

QMessageBox QLabel {
    color: #111111;
    font-size: 13px;
}

QMessageBox QPushButton {
    background-color: #FFFFFF;
    color: #111111;
    border: 1px solid #B8B8C0;
    border-radius: 4px;
    padding: 6px 14px;
}

QMessageBox QPushButton:hover {
    background-color: #ECECF0;
    color: #111111;
    border: 1px solid #8A2BE2;
}
"""

def apply_theme(app) -> None:
    """
    Apply the Aether Dark QSS Theme to the given QApplication instance.
    
    Args:
        app (QApplication): The active Qt application.
    """
    app.setStyleSheet(AETHER_DARK_STYLESHEET)
