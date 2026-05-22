"""
GUI Integration Tests for AetherPDF.

This module leverages pytest-qt to validate the initialization, signal-slot bindings,
and visual behavior of our major GUI components (Toolbar, Sidebar, Viewer, MainWindow).
It helps minimize manual layout verification.
"""

import os
import tempfile
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import fitz

from models.pdf_document import PdfDocument
from views.main_window import MainWindow
from views.toolbar_widget import ToolbarWidget
from views.sidebar_widget import SidebarWidget
from views.pdf_viewer_widget import PdfViewerWidget


@pytest.fixture
def sample_pdf() -> str:
    """Create a temporary 1-page sample PDF file for GUI testing."""
    fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(
        fitz.Rect(50, 50, 200, 100),
        "AetherPDF Test Page",
        fontsize=12
    )
    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass


def test_main_window_initialization(qtbot) -> None:
    """Ensure MainWindow constructs correctly and sub-widgets exist."""
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle().startswith("AetherPDF")
    assert window.toolbar is not None
    assert window.sidebar is not None
    assert window.viewer is not None
    assert window.centralWidget() is not None


def test_toolbar_mode_toggling(qtbot) -> None:
    """Validate that clicking toolbar buttons changes mode and emits signals."""
    toolbar = ToolbarWidget()
    qtbot.addWidget(toolbar)

    # Monitor the mode_changed signal
    with qtbot.waitSignal(toolbar.mode_changed, timeout=1000) as blocker:
        toolbar.btn_mode_edit_text.click()
    
    # Check if correct mode signal was sent
    assert blocker.args == ["edit_text"]
    assert toolbar.btn_mode_edit_text.isChecked()
    assert not toolbar.btn_mode_view.isChecked()

    # Toggle back to view
    with qtbot.waitSignal(toolbar.mode_changed, timeout=1000) as blocker:
        toolbar.btn_mode_view.click()
    
    assert blocker.args == ["view"]
    assert toolbar.btn_mode_view.isChecked()


def test_sidebar_document_binding(qtbot, sample_pdf: str) -> None:
    """Validate that binding a document automatically generates thumbnails in sidebar."""
    sidebar = SidebarWidget()
    qtbot.addWidget(sidebar)

    pdf = PdfDocument()
    pdf.open(sample_pdf)

    # Bind document
    sidebar.set_document(pdf)

    # Should contain 1 thumbnail item (matching our 1-page sample)
    assert sidebar.list_thumbnails.count() == 1
    
    first_item = sidebar.list_thumbnails.item(0)
    assert first_item is not None
    assert "페이지 1" in first_item.text()
    
    pdf.close()


def test_viewer_zoom_operations(qtbot, sample_pdf: str) -> None:
    """Ensure Zoom methods in PDF Viewer widget alter scales correctly."""
    viewer = PdfViewerWidget()
    qtbot.addWidget(viewer)

    pdf = PdfDocument()
    pdf.open(sample_pdf)
    viewer.set_document(pdf)

    # Initial zoom
    initial_zoom = viewer._zoom_factor
    assert initial_zoom == 1.0

    # Zoom In
    viewer.zoom_by_factor(1.2)
    assert viewer._zoom_factor == 1.2

    # Zoom Out
    viewer.zoom_by_factor(0.5)
    pdf.close()


def test_toolbar_hud_update(qtbot) -> None:
    """Validate that update_document_info updates HUD text correctly."""
    toolbar = ToolbarWidget()
    qtbot.addWidget(toolbar)

    # Empty state check
    assert "🚫 로드된 문서 없음" in toolbar.lbl_info.text()

    # Loaded state check
    toolbar.update_document_info("sample.pdf", 2, 10)
    assert "📄 sample.pdf" in toolbar.lbl_info.text()
    assert "(2 / 10 페이지)" in toolbar.lbl_info.text()


def test_main_window_menu_bar(qtbot) -> None:
    """Ensure that QMenuBar is populated correctly on MainWindow."""
    window = MainWindow()
    qtbot.addWidget(window)

    menubar = window.menuBar()
    assert menubar is not None

    actions = menubar.actions()
    # There should be 4 main menus: 파일(&F), 편집(&E), 보기(&V), 도움말(&H)
    menu_texts = [action.text() for action in actions]
    assert any("파일" in text for text in menu_texts)
    assert any("편집" in text for text in menu_texts)
    assert any("보기" in text for text in menu_texts)
    assert any("도움말" in text for text in menu_texts)


def test_main_window_drag_accept(qtbot) -> None:
    """Ensure MainWindow dragEnterEvent accepts PDF files and ignores other formats."""
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    window = MainWindow()
    qtbot.addWidget(window)

    # 1. Non-pdf mime data
    mime_other = QMimeData()
    mime_other.setUrls([QUrl.fromLocalFile("c:/test.txt")])
    event_other = QDragEnterEvent(
        window.rect().center(),
        Qt.MoveAction,
        mime_other,
        Qt.LeftButton,
        Qt.NoModifier
    )
    window.dragEnterEvent(event_other)
    assert not event_other.isAccepted()

    # 2. PDF mime data
    mime_pdf = QMimeData()
    mime_pdf.setUrls([QUrl.fromLocalFile("c:/test.pdf")])
    event_pdf = QDragEnterEvent(
        window.rect().center(),
        Qt.MoveAction,
        mime_pdf,
        Qt.LeftButton,
        Qt.NoModifier
    )
    window.dragEnterEvent(event_pdf)
    assert event_pdf.isAccepted()


def test_main_window_dirty_state_transitions(qtbot, sample_pdf: str) -> None:
    """Validate that changes trigger self._is_dirty state to True and save resets it to False."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Initial clean state
    assert not window._is_dirty

    # Open PDF
    window._pdf_doc.open(sample_pdf)
    window._is_dirty = False  # Explicit reset as simulated load

    # Simulate text modification signal
    block_meta = {
        "bbox": (50, 50, 200, 100),
        "lines": [{"spans": [{"text": "AetherPDF Test Page", "font": "Helvetica", "size": 12, "color": 0}]}]
    }
    # Call handler directly
    window._on_body_text_modified(0, block_meta, "AetherPDF Test Page", "Modified Text")
    
    # Process events to allow the deferred QTimer.singleShot to execute
    QApplication.processEvents()
    
    # State should become dirty
    assert window._is_dirty


def test_viewer_text_editor_activation(qtbot, sample_pdf: str) -> None:
    """Ensure that clicking a text block in text edit mode activates the QLineEdit overlay."""
    viewer = PdfViewerWidget()
    qtbot.addWidget(viewer)

    pdf = PdfDocument()
    pdf.open(sample_pdf)
    viewer.set_document(pdf)
    viewer.set_active_mode("edit_text")

    # The sample PDF contains "AetherPDF Test Page" at bbox fitz.Rect(50, 50, 200, 100) (at 72 DPI)
    # At DEFAULT_DPI=150, the scene coordinate would be:
    # scene_pos = pdf_pos * (DEFAULT_DPI / 72.0)
    # Let's target the center of the text box (e.g. pdf_x = 100, pdf_y = 55)
    from PySide6.QtCore import QPointF
    from config.settings import DEFAULT_DPI
    scale_ratio = DEFAULT_DPI / 72.0
    scene_click_pos = QPointF(100.0 * scale_ratio, 55.0 * scale_ratio)

    # Initially, no active proxy editor should exist
    assert viewer._active_proxy_editor is None

    # Simulate try activate text editor
    activated = viewer._try_activate_text_editor(scene_click_pos)
    assert activated
    assert viewer._active_proxy_editor is not None
    assert viewer._active_editor_block is not None

    # Verify QLineEdit geometry and content
    editor_widget = viewer._active_proxy_editor.widget()
    assert editor_widget.text() == "AetherPDF Test Page"

    # Simulate finishing edit
    editor_widget.setText("AetherPDF Test Page - Modified")
    
    # Monitor signal
    with qtbot.waitSignal(viewer.text_modified, timeout=1000) as blocker:
        viewer._on_editor_finished()
        
    assert blocker.args[2] == "AetherPDF Test Page"
    assert blocker.args[3] == "AetherPDF Test Page - Modified"

    pdf.close()


def test_viewer_new_text_editor_activation(qtbot, sample_pdf: str) -> None:
    """Ensure clicking empty space in text edit mode creates a new text editor."""
    viewer = PdfViewerWidget()
    qtbot.addWidget(viewer)

    pdf = PdfDocument()
    pdf.open(sample_pdf)
    viewer.set_document(pdf)
    viewer.set_active_mode("edit_text")

    from PySide6.QtCore import QPointF

    activated = viewer._try_activate_new_text_editor(QPointF(300.0, 300.0))
    assert activated
    assert viewer._active_proxy_editor is not None

    editor_widget = viewer._active_proxy_editor.widget()
    editor_widget.setText("Added Text")

    with qtbot.waitSignal(viewer.text_added, timeout=1000) as blocker:
        viewer._on_editor_finished()

    assert blocker.args[2] == "Added Text"
    assert blocker.args[3]["font_size"] == 12.0

    pdf.close()


def test_viewer_text_style_change_emits_without_text_change(qtbot, sample_pdf: str) -> None:
    """Ensure text style-only edits are treated as PDF modifications."""
    viewer = PdfViewerWidget()
    qtbot.addWidget(viewer)

    pdf = PdfDocument()
    pdf.open(sample_pdf)
    viewer.set_document(pdf)
    viewer.set_active_mode("edit_text")

    from PySide6.QtCore import QPointF
    from config.settings import DEFAULT_DPI

    scale_ratio = DEFAULT_DPI / 72.0
    scene_click_pos = QPointF(100.0 * scale_ratio, 55.0 * scale_ratio)

    assert viewer._try_activate_text_editor(scene_click_pos)
    viewer.set_text_style({
        "color": (1.0, 0.0, 0.0),
        "font_size": 18.0,
        "bold": True,
        "italic": False,
    })

    with qtbot.waitSignal(viewer.text_modified, timeout=1000) as blocker:
        viewer._on_editor_finished()

    assert blocker.args[2] == "AetherPDF Test Page"
    assert blocker.args[3] == "AetherPDF Test Page"
    assert blocker.args[4]["font_size"] == 18.0
    assert blocker.args[4]["bold"] is True

    pdf.close()
