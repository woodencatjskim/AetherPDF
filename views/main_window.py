"""
Main Window Controller for AetherPDF.

This module combines all views (Toolbar, Sidebar, Viewer) into a unified
split-pane desktop application. It manages overall application state,
handles file open/save dialogs, and maps signals between widgets.
"""

from typing import Optional, List
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFileDialog, QMessageBox, QLabel, QMenuBar, QToolButton, QProgressDialog
)
from PySide6.QtCore import QObject, QThread, Qt, QSize, QPoint, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon

from config.settings import APP_NAME, APP_VERSION, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
from config.theme import apply_theme
from models.pdf_document import PdfDocument
from services.pdf_editor_service import PdfEditorService
from services.export_service import ExportService
from services.update_service import UpdateInfo, UpdateService

from views.toolbar_widget import ToolbarWidget
from views.sidebar_widget import SidebarWidget
from views.pdf_viewer_widget import PdfViewerWidget
from views.properties_widget import PropertiesWidget


class TitleBar(QWidget):
    """Custom frameless window title bar."""

    def __init__(self, parent: QMainWindow) -> None:
        """Create title text and window control buttons."""
        super().__init__(parent)
        self._window = parent
        self._drag_pos: Optional[QPoint] = None
        self.setObjectName("titleBar")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(6)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("titleBarIcon")
        self.icon_label.setFixedSize(18, 18)
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("titleBarTitle")
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.btn_minimize = QToolButton()
        self.btn_minimize.setObjectName("titleBarButton")
        self.btn_minimize.setText("-")
        self.btn_minimize.setToolTip("최소화")
        self.btn_minimize.clicked.connect(self._window.showMinimized)

        self.btn_maximize = QToolButton()
        self.btn_maximize.setObjectName("titleBarButton")
        self.btn_maximize.setText("□")
        self.btn_maximize.setToolTip("최대화")
        self.btn_maximize.clicked.connect(self._toggle_maximized)

        self.btn_close = QToolButton()
        self.btn_close.setObjectName("titleBarCloseButton")
        self.btn_close.setText("×")
        self.btn_close.setToolTip("닫기")
        self.btn_close.clicked.connect(self._window.close)

        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_maximize)
        layout.addWidget(self.btn_close)

    def set_icon(self, icon: QIcon) -> None:
        """Display the application icon in the title bar."""
        if not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(18, 18))

    def set_title(self, title: str) -> None:
        """Update the visible title text."""
        self.title_label.setText(title)

    def mousePressEvent(self, event) -> None:
        """Start window drag on left mouse press."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Move the frameless window while dragging the title bar."""
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            if self._window.isMaximized():
                self._window.showNormal()
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """Stop title-bar dragging."""
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Toggle maximize state on title-bar double click."""
        if event.button() == Qt.LeftButton:
            self._toggle_maximized()
            event.accept()

    def _toggle_maximized(self) -> None:
        """Toggle between maximized and normal window states."""
        if self._window.isMaximized():
            self._window.showNormal()
            self.btn_maximize.setText("□")
        else:
            self._window.showMaximized()
            self.btn_maximize.setText("❐")



class UpdateCheckWorker(QObject):
    """Background worker for GitHub update checks."""

    finished = Signal(object)

    def run(self) -> None:
        """Check GitHub Releases for an available update."""
        self.finished.emit(UpdateService.check_for_update())


class UpdateDownloadWorker(QObject):
    """Background worker for downloading an update executable."""

    progress = Signal(int, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, update_info: UpdateInfo) -> None:
        """Store update metadata for the download task."""
        super().__init__()
        self._update_info = update_info

    def run(self) -> None:
        """Download the release asset."""
        try:
            path = UpdateService.download_update(self._update_info, self.progress.emit)
            self.finished.emit(path)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """
    Main application window orchestrating Toolbar, Sidebar, and PDF Viewer.
    """

    def __init__(self) -> None:
        """Initialize and layout the main window structure."""
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle(APP_NAME)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Core Application State
        self._pdf_doc = PdfDocument()
        self._current_mode: str = "view"
        self._is_dirty: bool = False  # Track unsaved changes [NEW]
        self._update_info: Optional[UpdateInfo] = None
        self._update_check_thread: Optional[QThread] = None
        self._update_check_worker: Optional[UpdateCheckWorker] = None
        self._update_download_thread: Optional[QThread] = None
        self._update_download_worker: Optional[UpdateDownloadWorker] = None
        self._update_progress_dialog: Optional[QProgressDialog] = None

        self.setAcceptDrops(True)  # Enable Drag-and-Drop [NEW]
        UpdateService.cleanup_old_backups()

        # [NEW] 윈도우 타이틀바 및 작업표시줄 아이콘 적용
        # PyInstaller 번들 실행 시 sys._MEIPASS 경로에서 assets를 탐색합니다.
        import sys as _sys
        base_dir = getattr(_sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        icon_path = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
        else:
            app_icon = QIcon()

        self._init_ui()
        self.title_bar.set_icon(app_icon)
        self.windowTitleChanged.connect(self.title_bar.set_title)
        self.title_bar.set_title(self.windowTitle())
        self._setup_menu_bar()  # Combined QMenuBar setup and shortcut actions
        self._connect_signals()
        self._sync_hud()        # Initial HUD state sync (empty state)
        QTimer.singleShot(1200, self._check_for_updates)

    def _init_ui(self) -> None:
        """Configure widget layout hierarchy."""
        # Create central container widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # Vertical layout holding Toolbar on top and Split-pane below
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Add Custom Title Bar and Menu Bar
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        self.custom_menu_bar = QMenuBar(self)
        self.custom_menu_bar.setObjectName("customMenuBar")
        self.custom_menu_bar.setFixedHeight(28)
        main_layout.addWidget(self.custom_menu_bar)

        # 2. Add Top Toolbar Widget
        self.toolbar = ToolbarWidget(self)
        main_layout.addWidget(self.toolbar)

        # 3. Add Split-pane (Sidebar | Viewer)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #2E2E35; }")

        # Sidebar Thumbnail Navigator
        self.sidebar = SidebarWidget(self)
        self.splitter.addWidget(self.sidebar)

        # Canvas Graphics View Viewer
        self.viewer = PdfViewerWidget(self)
        self.splitter.addWidget(self.viewer)

        # Properties panel (Annotations settings)
        self.properties_panel = PropertiesWidget(self)
        self.splitter.addWidget(self.properties_panel)
        self.properties_panel.setVisible(False)  # Hide by default (Only visible in annotate mode)

        # Configure splitter ratio (approx Sidebar, Viewer, Properties)
        self.splitter.setSizes([180, 860, 240])
        main_layout.addWidget(self.splitter)

        # 4. Simple Status Bar
        self.statusBar().showMessage("준비 완료")
        self.statusBar().setStyleSheet("QStatusBar { background-color: #121214; color: #8D8D99; border-top: 1px solid #2E2E35; }")

    def _setup_menu_bar(self) -> None:
        """Configure elegant QMenuBar for direct menu tree access and unified shortcuts."""
        menubar = self.custom_menu_bar
        menubar.clear()  # Clear native menus if any

        # --- 1. 파일 메뉴 (File Menu) ---
        menu_file = menubar.addMenu("파일(&F)")

        act_open = QAction("📁 PDF 파일 열기(&O)...", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.action_open_file)
        menu_file.addAction(act_open)

        act_save = QAction("💾 PDF 저장(&S)", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self.action_save_file)
        menu_file.addAction(act_save)

        act_save_as = QAction("💾 다른 이름으로 최적화 저장(&A)...", self)
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_as.triggered.connect(self.action_save_file_as)
        menu_file.addAction(act_save_as)

        menu_file.addSeparator()

        act_exit = QAction("❌ AetherPDF 종료(&X)", self)
        act_exit.setShortcut(QKeySequence("Alt+F4"))
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # --- 2. 편집 메뉴 (Edit Menu) ---
        menu_edit = menubar.addMenu("편집(&E)")

        act_rotate = QAction("🔄 페이지 회전(90도)(&R)", self)
        act_rotate.setShortcut(QKeySequence("Ctrl+R"))
        act_rotate.triggered.connect(self.action_rotate_page)
        menu_edit.addAction(act_rotate)

        act_delete = QAction("🗑️ 현재 페이지 삭제(&D)", self)
        act_delete.setShortcut(QKeySequence("Ctrl+D"))
        act_delete.triggered.connect(self.action_delete_page)
        menu_edit.addAction(act_delete)

        act_insert = QAction("📄 새 빈 페이지 삽입(&N)", self)
        act_insert.setShortcut(QKeySequence("Ctrl+N"))
        act_insert.triggered.connect(self.action_insert_blank)
        menu_edit.addAction(act_insert)

        act_merge = QAction("🔀 외부 PDF 파일 병합(&M)...", self)
        act_merge.setShortcut(QKeySequence("Ctrl+M"))
        act_merge.triggered.connect(self.action_merge_pdf)
        menu_edit.addAction(act_merge)

        # --- 3. 보기 메뉴 (View Menu) ---
        menu_view = menubar.addMenu("보기(&V)")

        act_zoom_in = QAction("➕ 화면 확대(&I)", self)
        act_zoom_in.setShortcut(QKeySequence("Ctrl+="))
        act_zoom_in.triggered.connect(self.toolbar._on_zoom_in)
        menu_view.addAction(act_zoom_in)

        act_zoom_out = QAction("➖ 화면 축소(&O)", self)
        act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        act_zoom_out.triggered.connect(self.toolbar._on_zoom_out)
        menu_view.addAction(act_zoom_out)

        act_zoom_fit = QAction("📏 가로폭 맞춤(&W)", self)
        act_zoom_fit.triggered.connect(lambda: self._on_toolbar_zoom_changed(0.0))
        menu_view.addAction(act_zoom_fit)

        # --- 4. 도움말 메뉴 (Help Menu) ---
        menu_help = menubar.addMenu("도움말(&H)")

        act_about = QAction("💡 AetherPDF 정보(&A)", self)
        act_about.triggered.connect(self.action_show_about)
        menu_help.addAction(act_about)

        self.act_update = QAction("업데이트", self)
        self.act_update.setVisible(False)
        self.act_update.triggered.connect(self.action_apply_update)
        menubar.addAction(self.act_update)

        # Keep actions active in window context for keyboard shortcuts to fire
        self.addActions([
            act_open, act_save, act_save_as,
            act_rotate, act_delete, act_insert, act_merge,
            act_zoom_in, act_zoom_out
        ])

    def _connect_signals(self) -> None:
        """Link widget signals together dynamically."""
        # Toolbar Actions
        self.toolbar.open_clicked.connect(self.action_open_file)
        self.toolbar.save_clicked.connect(self.action_save_file)
        self.toolbar.zoom_changed.connect(self._on_toolbar_zoom_changed)
        self.toolbar.mode_changed.connect(self._on_mode_changed)

        # Sidebar Thumbnail Navigation
        self.sidebar.page_selected.connect(self._on_sidebar_page_selected)
        self.sidebar.pages_reordered.connect(self._on_pages_reordered)
        self.sidebar.page_action_requested.connect(self._on_sidebar_page_action_requested)

        # Viewer Updates
        self.viewer.zoom_level_changed.connect(self._on_viewer_zoom_changed)
        self.viewer.text_modified.connect(self._on_body_text_modified)
        self.viewer.text_added.connect(self._on_free_text_added)
        self.viewer.text_style_selected.connect(self.properties_panel.set_text_style)
        self.viewer.page_navigation_requested.connect(self._on_page_navigation_requested)  # [NEW] 휠 바운더리 페이지 전환
        self.viewer.annotation_added.connect(self._on_annotation_added)

        # Properties Panel to Viewer Connections
        self.properties_panel.tool_changed.connect(self.viewer.set_annot_tool)
        self.properties_panel.color_changed.connect(self.viewer.set_annot_color)
        self.properties_panel.width_changed.connect(self.viewer.set_annot_width)
        self.properties_panel.opacity_changed.connect(self.viewer.set_annot_opacity)
        self.properties_panel.text_style_changed.connect(self.viewer.set_text_style)

        # Initialize viewer drawing settings to match properties panel defaults
        init_tool, init_col, init_w, init_op = self.properties_panel.get_settings()
        self.viewer.set_annot_tool(init_tool)
        self.viewer.set_annot_color(init_col)
        self.viewer.set_annot_width(init_w)
        self.viewer.set_annot_opacity(init_op)
        self.viewer.set_text_style(self.properties_panel.get_text_style())

    def _sync_hud(self) -> None:
        """Synchronize the top toolbar HUD with the active PDF document state."""
        if self._pdf_doc and self._pdf_doc.is_loaded:
            filename = os.path.basename(self._pdf_doc._filepath) if self._pdf_doc._filepath else "이름 없는 문서.pdf"
            curr_page = self.viewer._current_page_idx + 1
            total_pages = self._pdf_doc.page_count
            self.toolbar.update_document_info(filename, curr_page, total_pages)
        else:
            self.toolbar.update_document_info("", 0, 0)

    def _check_for_updates(self) -> None:
        """Check GitHub Releases for a newer packaged executable."""
        if self._update_check_thread is not None:
            return

        self._update_check_thread = QThread(self)
        self._update_check_worker = UpdateCheckWorker()
        self._update_check_worker.moveToThread(self._update_check_thread)
        self._update_check_thread.started.connect(self._update_check_worker.run)
        self._update_check_worker.finished.connect(self._on_update_check_finished)
        self._update_check_worker.finished.connect(self._update_check_thread.quit)
        self._update_check_worker.finished.connect(self._update_check_worker.deleteLater)
        self._update_check_thread.finished.connect(self._on_update_check_thread_finished)
        self._update_check_thread.start()

    def _on_update_check_finished(self, update_info: Optional[UpdateInfo]) -> None:
        """Show the update action when a newer release is available."""
        if not update_info:
            return

        self._update_info = update_info
        self.act_update.setText(f"업데이트 v{update_info.latest_version}")
        self.act_update.setVisible(True)
        self.statusBar().showMessage(f"AetherPDF v{update_info.latest_version} 업데이트 가능")

    def _on_update_check_thread_finished(self) -> None:
        """Clear update check thread references."""
        if self._update_check_thread:
            self._update_check_thread.deleteLater()
        self._update_check_thread = None
        self._update_check_worker = None

    def action_apply_update(self) -> None:
        """Download and apply the available update after user confirmation."""
        if not self._update_info:
            return

        if not UpdateService.can_apply_update():
            QMessageBox.information(
                self,
                "업데이트",
                "업데이트 적용은 패키징된 AetherPDF.exe로 실행 중일 때만 가능합니다.\n"
                "개발 실행 환경에서는 업데이트 가능 여부만 확인합니다."
            )
            return

        reply = QMessageBox.question(
            self,
            "업데이트 확인",
            f"AetherPDF v{self._update_info.latest_version}을 다운로드하고 재시작하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        self._start_update_download()

    def _start_update_download(self) -> None:
        """Download the selected update release asset in the background."""
        if not self._update_info or self._update_download_thread is not None:
            return

        self._update_progress_dialog = QProgressDialog("업데이트 다운로드 중...", "취소", 0, 100, self)
        self._update_progress_dialog.setWindowTitle("AetherPDF 업데이트")
        self._update_progress_dialog.setWindowModality(Qt.WindowModal)
        self._update_progress_dialog.setMinimumDuration(0)
        self._update_progress_dialog.setCancelButton(None)

        self._update_download_thread = QThread(self)
        self._update_download_worker = UpdateDownloadWorker(self._update_info)
        self._update_download_worker.moveToThread(self._update_download_thread)
        self._update_download_thread.started.connect(self._update_download_worker.run)
        self._update_download_worker.progress.connect(self._on_update_download_progress)
        self._update_download_worker.finished.connect(self._on_update_download_finished)
        self._update_download_worker.failed.connect(self._on_update_download_failed)
        self._update_download_worker.finished.connect(self._update_download_thread.quit)
        self._update_download_worker.failed.connect(self._update_download_thread.quit)
        self._update_download_worker.finished.connect(self._update_download_worker.deleteLater)
        self._update_download_worker.failed.connect(self._update_download_worker.deleteLater)
        self._update_download_thread.finished.connect(self._on_update_download_thread_finished)
        self._update_download_thread.start()

    def _on_update_download_progress(self, downloaded: int, total: int) -> None:
        """Update download progress UI."""
        if not self._update_progress_dialog:
            return
        if total > 0:
            self._update_progress_dialog.setMaximum(100)
            self._update_progress_dialog.setValue(int(downloaded * 100 / total))
        else:
            self._update_progress_dialog.setMaximum(0)

    def _on_update_download_finished(self, downloaded_exe: str) -> None:
        """Launch the replacement script after download completion."""
        if self._update_progress_dialog:
            self._update_progress_dialog.close()
            self._update_progress_dialog = None

        QMessageBox.information(
            self,
            "업데이트",
            "확인을 누르면 업데이트를 적용하기 위해 AetherPDF를 재시작합니다."
        )
        try:
            UpdateService.launch_update_replacer(downloaded_exe)
        except Exception as exc:
            QMessageBox.critical(self, "업데이트 오류", f"업데이트 적용을 시작하지 못했습니다:\n{exc}")
            return

        QTimer.singleShot(100, self.close)

    def _on_update_download_failed(self, message: str) -> None:
        """Report update download failures."""
        if self._update_progress_dialog:
            self._update_progress_dialog.close()
            self._update_progress_dialog = None
        QMessageBox.critical(self, "업데이트 다운로드 실패", message)

    def _on_update_download_thread_finished(self) -> None:
        """Clear update download thread references."""
        if self._update_download_thread:
            self._update_download_thread.deleteLater()
        self._update_download_thread = None
        self._update_download_worker = None

    # --- Drag & Drop and Save State Interceptors ---

    def dragEnterEvent(self, event) -> None:
        """Accept dragged PDF files for seamless drop loading [NEW]."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                if filepath.lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:
        """Handle dropped PDF files safely [NEW]."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                if filepath.lower().endswith(".pdf"):
                    self.open_dropped_file(filepath)
                    break

    def open_dropped_file(self, filepath: str) -> None:
        """Load the dropped PDF file after performing safety unsaved changes check [NEW]."""
        if not self.maybe_save():
            return

        self.statusBar().showMessage("PDF 파일 로드 중...")
        try:
            self._pdf_doc.close()
            success = self._pdf_doc.open(filepath)
            
            if success:
                filename = os.path.basename(filepath)
                self.setWindowTitle(f"{APP_NAME} - {filename}")
                self.viewer.set_document(self._pdf_doc)
                self.sidebar.set_document(self._pdf_doc)
                self._sync_hud()
                self._is_dirty = False
                self.statusBar().showMessage(f"로딩 완료: {filename} ({self._pdf_doc.page_count}페이지)")
            else:
                raise ValueError("PDF 파싱 에러 발생.")
        except Exception as e:
            QMessageBox.critical(
                self,
                "파일 로드 오류",
                f"PDF 파일을 열지 못했습니다:\n{str(e)}"
            )
            self.statusBar().showMessage("로드 실패")

    def maybe_save(self) -> bool:
        """
        Check if there are unsaved changes and ask to save.
        
        Returns:
            bool: True if safe to proceed (discarded, saved, or clean), False if user cancelled.
        """
        if not self._is_dirty:
            return True

        reply = QMessageBox.question(
            self,
            "변경 사항 저장 확인",
            "현재 문서에 저장하지 않은 변경 사항이 있습니다.\n변경 사항을 저장하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            self.action_save_file()
            return not self._is_dirty  # Safe if no longer dirty (successfully saved)
        elif reply == QMessageBox.No:
            return True  # User explicitly chose to discard changes, safe to proceed
        else:
            return False  # User cancelled

    def closeEvent(self, event) -> None:
        """Intercept application close event to check for unsaved edits [NEW]."""
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()

    # --- Controller Actions ---

    def action_show_about(self) -> None:
        """Display an elegant dark-themed information box about AetherPDF."""
        QMessageBox.about(
            self,
            "AetherPDF 정보",
            f"<h3>🌌 AetherPDF v{APP_VERSION}</h3>"
            "<p><b>초경량 오프라인 PDF 편집기</b></p>"
            "<p>AetherPDF는 초고속 렌더링 및 본문 직접 수정과 주석 필기가 가능한 오프라인 전용 독립 실행 소프트웨어입니다.</p>"
            "<hr style='border: 1px solid #2E2E35;'/>"
            "<p>• 엔진: PyMuPDF (fitz)<br/>"
            "• GUI: PySide6 (Qt6)<br/>"
            "• 테마: Aether Neon Dark Theme</p>"
            "<p>• GitHub: https://github.com/woodencatjskim/AetherPDF<br/>"
            "• Contact: woodencat.jskim@gmail.com</p>"
        )

    def action_open_file(self) -> None:
        """Trigger native Open File Dialog and load PDF after validation."""
        if not self.maybe_save():
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "PDF 파일 열기",
            "",
            "PDF Documents (*.pdf)"
        )
        
        if not filepath:
            return

        self.statusBar().showMessage("PDF 파일 로드 중...")
        try:
            self._pdf_doc.close()
            success = self._pdf_doc.open(filepath)
            
            if success:
                # Update window title
                filename = os.path.basename(filepath)
                self.setWindowTitle(f"{APP_NAME} - {filename}")
                
                # Bind document to sub-views
                self.viewer.set_document(self._pdf_doc)
                self.sidebar.set_document(self._pdf_doc)
                
                self._sync_hud()  # Sync HUD after loading
                self._is_dirty = False
                self.statusBar().showMessage(f"로딩 완료: {filename} ({self._pdf_doc.page_count}페이지)")
            else:
                raise ValueError("PDF 파싱 에러 발생.")
        except Exception as e:
            QMessageBox.critical(
                self,
                "파일 로드 오류",
                f"PDF 파일을 열지 못했습니다:\n{str(e)}"
            )
            self.statusBar().showMessage("로드 실패")

    def action_save_file(self) -> None:
        """Save the document in-place using incremental save to preserve resources."""
        if not self._pdf_doc.is_loaded:
            QMessageBox.warning(self, "저장 오류", "저장할 PDF 문서가 없습니다.")
            return

        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        self.statusBar().showMessage("문서 점진적 저장 중...")
        try:
            success = ExportService.save_incremental(raw_doc)
            if success:
                self._sync_hud()  # Sync HUD
                self._is_dirty = False  # Mark as clean [NEW]
                self.statusBar().showMessage("점진적 저장 완료!")
                QMessageBox.information(self, "저장 성공", "변경 사항이 성공적으로 덮어쓰기 저장되었습니다.")
            else:
                raise RuntimeError("점진적 저장 실패")
        except Exception as e:
            QMessageBox.critical(
                self,
                "저장 오류",
                f"문서를 덮어쓰기 저장하지 못했습니다:\n{str(e)}\n\n'다른 이름으로 저장'을 시도해 주십시오."
            )
            self.statusBar().showMessage("저장 실패")

    def action_save_file_as(self) -> None:
        """Trigger native Save File Dialog and write fully optimized and compressed PDF."""
        if not self._pdf_doc.is_loaded:
            QMessageBox.warning(self, "저장 오류", "저장할 PDF 문서가 없습니다.")
            return

        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        # Open file dialog to choose target location
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "다른 이름으로 저장 (압축 및 최적화)",
            "",
            "PDF Documents (*.pdf)"
        )
        if not filepath:
            return

        self.statusBar().showMessage("최적화 압축 저장 중...")
        try:
            # Full optimized save (garbage collect & deflate streams)
            success = ExportService.save_as(raw_doc, filepath, optimize=True)
            if success:
                # Update document and window title state
                self._pdf_doc._filepath = filepath
                filename = os.path.basename(filepath)
                self.setWindowTitle(f"{APP_NAME} - {filename}")
                self._sync_hud()  # Sync HUD
                self._is_dirty = False  # Mark as clean [NEW]
                self.statusBar().showMessage(f"다른 이름으로 저장 완료: {filename}")
                QMessageBox.information(
                    self,
                    "저장 완료",
                    f"문서가 최적화 및 압축되어 성공적으로 저장되었습니다:\n{filename}"
                )
            else:
                raise RuntimeError("압축 저장 실패")
        except Exception as e:
            QMessageBox.critical(
                self,
                "저장 오류",
                f"최적화 저장을 실패했습니다:\n{str(e)}"
            )
            self.statusBar().showMessage("저장 실패")


    # --- Signal Response Handlers ---

    def _on_sidebar_page_selected(self, page_index: int) -> None:
        """Navigate viewer to selected page."""
        self.viewer.load_page(page_index)
        self._sync_hud()  # Sync HUD on page navigation
        self.statusBar().showMessage(f"{page_index + 1} 페이지 표시 중")

    def _on_sidebar_page_action_requested(self, page_index: int, action: str) -> None:
        """Run an edit-menu action for the page selected from the sidebar."""
        self.viewer.load_page(page_index)
        self.sidebar.select_page(page_index)
        self._sync_hud()

        if action == "rotate":
            self.action_rotate_page()
        elif action == "delete":
            self.action_delete_page()
        elif action == "insert":
            self.action_insert_blank()
        elif action == "merge":
            self.action_merge_pdf()

    def _on_page_navigation_requested(self, direction: int) -> None:
        """
        Handle page boundary scroll navigation from viewer wheel events [NEW].

        Args:
            direction (int): 1 for next page, -1 for previous page.
        """
        if not self._pdf_doc or not self._pdf_doc.is_loaded:
            return

        current_page = self.viewer._current_page_idx
        new_page = current_page + direction

        # 유효 범위 검사: 첫 페이지 이전이나 마지막 페이지 이후로는 이동 불가
        if new_page < 0 or new_page >= self._pdf_doc.page_count:
            return

        self.viewer.load_page(new_page)
        self.sidebar.select_page(new_page)
        self._sync_hud()
        self.statusBar().showMessage(f"{new_page + 1} 페이지 표시 중")

    def _on_toolbar_zoom_changed(self, zoom_val: float) -> None:
        """Handle zoom alterations from the toolbar."""
        if zoom_val == 0.0:
            self.viewer.fit_to_width()
        elif zoom_val < 0.0:
            self.viewer.set_zoom(-zoom_val)  # Absolute
        else:
            self.viewer.zoom_by_factor(zoom_val)  # Multiplicative

    def _on_viewer_zoom_changed(self, percentage: int) -> None:
        """Synchronize toolbar zoom text display with actual viewer zoom."""
        self.toolbar.set_zoom_text(percentage)

    def _on_mode_changed(self, new_mode: str) -> None:
        """Handle application-wide mode switches."""
        self._current_mode = new_mode
        self.viewer.set_active_mode(new_mode)
        
        # [C] Page Layout Mode: Enable drag-and-drop on sidebar
        is_layout_mode = (new_mode == "layout")
        self.sidebar.enable_drag_and_drop(is_layout_mode)

        # [A/B] Annotation and text edit modes use the properties panel
        is_annotate = (new_mode == "annotate")
        is_edit_text = (new_mode == "edit_text")
        self.properties_panel.setVisible(is_annotate or is_edit_text)
        self.properties_panel.set_mode(new_mode)
        
        self.statusBar().showMessage(f"모드 전환: {new_mode.upper()}")


    def _on_pages_reordered(self, original_indices: List[int]) -> None:
        """
        Handle page order change notifications [C].
        
        Applies reordering in-memory to the active document and refreshes views.
        """
        if not self._pdf_doc.is_loaded:
            return

        self.statusBar().showMessage("페이지 순서 재정렬 중...")
        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        try:
            # Reorder in PDF document
            success = PdfEditorService.reorder_pages(raw_doc, original_indices)
            if success:
                # Reload sidebar thumbnails and update current page view
                # The drag-drop already changed the QListWidget items, so we just rebuild
                self.sidebar.refresh_thumbnails()
                self.viewer.load_page(0)  # Reset to first page safely
                self.sidebar.select_page(0)
                self._sync_hud()  # Sync HUD
                self._is_dirty = True  # Mark as modified [NEW]
                self.statusBar().showMessage("페이지 재정렬 완료!")
        except Exception as e:
            QMessageBox.critical(
                self,
                "페이지 재정렬 오류",
                f"페이지 순서를 변경하는 데 실패했습니다:\n{str(e)}"
            )
            self.statusBar().showMessage("재정렬 실패")

    def action_rotate_page(self) -> None:
        """Rotate the active page 90 degrees clockwise [C]."""
        if not self._pdf_doc.is_loaded:
            return

        active_page = self.viewer._current_page_idx
        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        self.statusBar().showMessage("페이지 회전 중...")
        try:
            success = PdfEditorService.rotate_page(raw_doc, active_page, 90)
            if success:
                # Refresh views
                self.viewer.load_page(active_page)
                self.sidebar.refresh_thumbnails()
                self.sidebar.select_page(active_page)
                self._sync_hud()  # Sync HUD
                self._is_dirty = True  # Mark as modified [NEW]
                self.statusBar().showMessage(f"p.{active_page + 1} 90도 회전 완료!")
        except Exception as e:
            QMessageBox.critical(self, "페이지 회전 오류", f"페이지 회전에 실패했습니다:\n{str(e)}")
            self.statusBar().showMessage("회전 실패")

    def action_delete_page(self) -> None:
        """Delete the currently active page [C]."""
        if not self._pdf_doc.is_loaded:
            return

        if self._pdf_doc.page_count <= 1:
            QMessageBox.warning(self, "페이지 삭제 오류", "문서에 최소 1페이지는 존재해야 합니다.")
            return

        active_page = self.viewer._current_page_idx
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "페이지 삭제 확인",
            f"정말로 현재 페이지 ({active_page + 1} 페이지)를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        self.statusBar().showMessage("페이지 삭제 중...")
        try:
            success = PdfEditorService.delete_page(raw_doc, active_page)
            if success:
                # Update document page count state
                self._pdf_doc._page_count = len(raw_doc)
                
                # Determine next active page index
                next_page = min(active_page, self._pdf_doc.page_count - 1)
                
                # Refresh views
                self.sidebar.refresh_thumbnails()
                self.viewer.load_page(next_page)
                self.sidebar.select_page(next_page)
                self._sync_hud()  # Sync HUD
                self._is_dirty = True  # Mark as modified [NEW]
                self.statusBar().showMessage("페이지 삭제 완료!")
        except Exception as e:
            QMessageBox.critical(self, "페이지 삭제 오류", f"페이지 삭제에 실패했습니다:\n{str(e)}")
            self.statusBar().showMessage("삭제 실패")

    def action_insert_blank(self) -> None:
        """Insert a blank A4 page directly after the active page [C]."""
        if not self._pdf_doc.is_loaded:
            return

        active_page = self.viewer._current_page_idx
        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        insert_at = active_page + 1
        self.statusBar().showMessage("빈 페이지 삽입 중...")
        try:
            success = PdfEditorService.insert_blank_page(raw_doc, insert_at)
            if success:
                # Update page count
                self._pdf_doc._page_count = len(raw_doc)
                
                # Refresh views and navigate to the newly inserted blank page
                self.sidebar.refresh_thumbnails()
                self.viewer.load_page(insert_at)
                self.sidebar.select_page(insert_at)
                self._sync_hud()  # Sync HUD
                self._is_dirty = True  # Mark as modified [NEW]
                self.statusBar().showMessage("새 빈 페이지 삽입 완료!")
        except Exception as e:
            QMessageBox.critical(self, "페이지 삽입 오류", f"빈 페이지 삽입에 실패했습니다:\n{str(e)}")
            self.statusBar().showMessage("삽입 실패")

    def action_merge_pdf(self) -> None:
        """Merge an external PDF file after the current active page [C]."""
        if not self._pdf_doc.is_loaded:
            return

        active_page = self.viewer._current_page_idx
        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        # Open file dialog to choose external PDF
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "병합할 PDF 파일 선택",
            "",
            "PDF Documents (*.pdf)"
        )
        if not filepath:
            return

        insert_at = active_page + 1
        self.statusBar().showMessage("외부 PDF 병합 중...")
        try:
            success = PdfEditorService.merge_pdf(raw_doc, filepath, insert_at)
            if success:
                # Update page count
                self._pdf_doc._page_count = len(raw_doc)
                
                # Refresh views
                self.sidebar.refresh_thumbnails()
                self.viewer.load_page(insert_at)
                self.sidebar.select_page(insert_at)
                self._sync_hud()  # Sync HUD
                self._is_dirty = True  # Mark as modified [NEW]
                self.statusBar().showMessage("외부 PDF 병합 완료!")
        except Exception as e:
            QMessageBox.critical(self, "PDF 병합 오류", f"외부 PDF 파일 병합에 실패했습니다:\n{str(e)}")
            self.statusBar().showMessage("병합 실패")

    def _on_body_text_modified(
        self, page_index: int, block_meta: dict, old_txt: str, new_txt: str, text_style: Optional[dict] = None
    ) -> None:
        """
        Handle text modifications [B].
        
        Executes PDF body text replacement, and refreshes both the main viewer
        and the sidebar thumbnails to keep all views synchronized.
        """
        self.statusBar().showMessage("본문 텍스트 수정 적용 중...")
        
        # [CRITICAL 메모리 크래시 예방]
        # QLineEdit의 returnPressed 이벤트 처리 도중에 동기적으로 뷰의 scene.clear()가 수행되면,
        # 이벤트를 실행 중인 위젯이 메모리에서 강제 소멸되어 C++ 세그멘테이션 폴트가 발생합니다.
        # QTimer.singleShot(0, ...)을 사용해 이 작업을 다음 이벤트 루프 틱으로 미뤄 안전을 보장합니다.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._execute_body_text_modification(page_index, block_meta, old_txt, new_txt, text_style))

    def _execute_body_text_modification(
        self, page_index: int, block_meta: dict, old_txt: str, new_txt: str, text_style: Optional[dict] = None
    ) -> None:
        """Actually perform the document modification and reload views safely."""
        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        try:
            # Modify PDF document directly
            success = PdfEditorService.replace_block_text(
                raw_doc, page_index, block_meta, new_txt, text_style
            )
            
            if success:
                # Refresh main view canvas
                self.viewer.load_page(page_index)
                
                # Refresh sidebar thumbnails to match the edit
                self.sidebar.refresh_thumbnails()
                self.sidebar.select_page(page_index)
                self._sync_hud()  # Sync HUD
                self._is_dirty = True  # Mark as modified [NEW]
                self.statusBar().showMessage(f"p.{page_index + 1} 본문 수정 성공!")
            else:
                raise RuntimeError("텍스트 수정에 실패했습니다.")
        except Exception as e:
            QMessageBox.critical(
                self,
                "텍스트 편집 오류",
                f"본문 직접 편집 중 오류가 발생했습니다:\n{str(e)}"
            )
            self.statusBar().showMessage("편집 실패")

    def _on_free_text_added(
        self, page_index: int, point: tuple, text: str, text_style: Optional[dict] = None
    ) -> None:
        """Handle adding text to an empty PDF location."""
        if not self._pdf_doc.is_loaded:
            return

        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        self.statusBar().showMessage("텍스트 추가 적용 중...")
        try:
            success = PdfEditorService.add_free_text(
                raw_doc, page_index, point, text, text_style
            )

            if success:
                self.viewer.load_page(page_index)
                self.sidebar.refresh_thumbnails()
                self.sidebar.select_page(page_index)
                self._sync_hud()
                self._is_dirty = True
                self.statusBar().showMessage(f"p.{page_index + 1} 텍스트 추가 성공!")
            else:
                raise RuntimeError("텍스트 추가에 실패했습니다.")
        except Exception as e:
            QMessageBox.critical(
                self,
                "텍스트 추가 오류",
                f"빈 공간에 텍스트를 추가하는 중 오류가 발생했습니다:\n{str(e)}"
            )
            self.statusBar().showMessage("텍스트 추가 실패")

    def _on_annotation_added(
        self, page_index: int, annot_type: str, data: list,
        color: tuple, width: float, opacity: float
    ) -> None:
        """
        Handle annotation additions [A].
        
        Applies annotations to the fitz Document model and updates viewer & sidebar.
        """
        if not self._pdf_doc.is_loaded:
            return

        raw_doc = self._pdf_doc.get_raw_document()
        if not raw_doc:
            return

        self.statusBar().showMessage("주석 추가 적용 중...")
        try:
            success = False
            if annot_type == "ink":
                success = PdfEditorService.add_ink_annotation(
                    raw_doc, page_index, data, color, width, opacity
                )
            else:  # highlight, underline, strikeout
                success = PdfEditorService.add_text_annotation(
                    raw_doc, page_index, data, annot_type, color, opacity
                )

            if success:
                # Refresh views to display the new annotation
                self.viewer.load_page(page_index)
                self.sidebar.refresh_thumbnails()
                self.sidebar.select_page(page_index)
                self._sync_hud()  # Sync HUD
                self._is_dirty = True  # Mark as modified [NEW]
                self.statusBar().showMessage("주석 추가 완료!")
            else:
                raise RuntimeError("주석 추가에 실패했습니다.")
        except Exception as e:
            QMessageBox.critical(
                self,
                "주석 추가 오류",
                f"주석을 생성하는 데 실패했습니다:\n{str(e)}"
            )
            self.statusBar().showMessage("주석 추가 실패")
