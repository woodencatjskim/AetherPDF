"""
Toolbar Widget for AetherPDF.

This widget provides the top toolbar containing primary actions like file
open/save, zoom controls, and mode selection buttons.
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QComboBox,
    QToolButton, QSizePolicy, QSpacerItem, QLabel
)
from PySide6.QtCore import Signal, Qt


class ToolbarWidget(QFrame):
    """
    Top toolbar widget for major application controls.

    Signals:
        open_clicked: Emitted when the Open button is clicked.
        save_clicked: Emitted when the Save button is clicked.
        zoom_changed (float): Emitted when the zoom level changes.
        mode_changed (str): Emitted when active editor mode changes.
    """
    open_clicked = Signal()
    save_clicked = Signal()
    zoom_changed = Signal(float)
    mode_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        """Initialize the toolbar layout and components."""
        super().__init__(parent)
        self.setObjectName("toolbarFrame")
        self.setFixedHeight(60)

        self._init_ui()

    def _init_ui(self) -> None:
        """Configure UI layout and connect widget signals."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(12)

        self.file_group = QFrame()
        self.file_group.setObjectName("fileGroupFrame")
        file_layout = QHBoxLayout(self.file_group)
        file_layout.setContentsMargins(2, 2, 2, 2)
        file_layout.setSpacing(4)

        self.btn_open = QPushButton("열기")
        self.btn_open.setToolTip("PDF 파일 열기 (Ctrl+O)")
        self.btn_open.setObjectName("fileOpenButton")
        self.btn_open.clicked.connect(self.open_clicked.emit)

        self.btn_save = QPushButton("저장")
        self.btn_save.setToolTip("PDF 파일 저장 (Ctrl+S)")
        self.btn_save.setObjectName("primaryActionButton")
        self.btn_save.clicked.connect(self.save_clicked.emit)

        file_layout.addWidget(self.btn_open)
        file_layout.addWidget(self.btn_save)
        layout.addWidget(self.file_group)

        self.mode_group = QFrame()
        self.mode_group.setObjectName("modeGroupFrame")
        mode_layout = QHBoxLayout(self.mode_group)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(2)

        self.btn_mode_view = QToolButton()
        self.btn_mode_view.setText("보기")
        self.btn_mode_view.setToolTip("PDF 보기 모드")
        self.btn_mode_view.setCheckable(True)
        self.btn_mode_view.setChecked(True)
        self.btn_mode_view.clicked.connect(lambda: self._on_mode_toggled("view"))

        self.btn_mode_edit_text = QToolButton()
        self.btn_mode_edit_text.setText("텍스트 편집")
        self.btn_mode_edit_text.setToolTip("본문 텍스트 수정 및 추가")
        self.btn_mode_edit_text.setCheckable(True)
        self.btn_mode_edit_text.clicked.connect(lambda: self._on_mode_toggled("edit_text"))

        self.btn_mode_layout = QToolButton()
        self.btn_mode_layout.setText("페이지 관리")
        self.btn_mode_layout.setToolTip("페이지 회전, 삽입, 삭제, 순서 변경")
        self.btn_mode_layout.setCheckable(True)
        self.btn_mode_layout.clicked.connect(lambda: self._on_mode_toggled("layout"))

        self.btn_mode_annotate = QToolButton()
        self.btn_mode_annotate.setText("주석 도구")
        self.btn_mode_annotate.setToolTip("형광펜, 밑줄, 취소선, 자유 그리기")
        self.btn_mode_annotate.setCheckable(True)
        self.btn_mode_annotate.clicked.connect(lambda: self._on_mode_toggled("annotate"))

        self.mode_buttons = [
            self.btn_mode_view,
            self.btn_mode_edit_text,
            self.btn_mode_layout,
            self.btn_mode_annotate,
        ]

        for btn in self.mode_buttons:
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            mode_layout.addWidget(btn)

        layout.addWidget(self.mode_group)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.info_group = QFrame()
        self.info_group.setObjectName("infoDisplayFrame")
        info_layout = QHBoxLayout(self.info_group)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)

        self.lbl_info = QLabel("AetherPDF  |  로드된 문서 없음")
        self.lbl_info.setObjectName("infoDisplayLabel")
        self.lbl_info.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.lbl_info)

        layout.addWidget(self.info_group)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.zoom_group = QFrame()
        self.zoom_group.setObjectName("zoomGroupFrame")
        zoom_layout = QHBoxLayout(self.zoom_group)
        zoom_layout.setContentsMargins(4, 2, 4, 2)
        zoom_layout.setSpacing(2)

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setToolTip("축소")
        self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_out.setObjectName("zoomButton")
        self.btn_zoom_out.clicked.connect(self._on_zoom_out)

        self.combo_zoom = QComboBox()
        self.combo_zoom.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "300%", "맞춤"])
        self.combo_zoom.setCurrentText("100%")
        self.combo_zoom.setFixedWidth(78)
        self.combo_zoom.setObjectName("zoomCombo")
        self.combo_zoom.currentIndexChanged.connect(self._on_zoom_combo_changed)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setToolTip("확대")
        self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_in.setObjectName("zoomButton")
        self.btn_zoom_in.clicked.connect(self._on_zoom_in)

        zoom_layout.addWidget(self.btn_zoom_out)
        zoom_layout.addWidget(self.combo_zoom)
        zoom_layout.addWidget(self.btn_zoom_in)
        layout.addWidget(self.zoom_group)

    def update_document_info(self, filename: str, current_page: int, total_pages: int) -> None:
        """
        Update the HUD document info display text.

        Args:
            filename (str): Name of the active PDF file.
            current_page (int): Current active page index (1-based for UI).
            total_pages (int): Total page count of active PDF.
        """
        if filename:
            self.lbl_info.setText(f"AetherPDF  |  {filename}  |  ({current_page} / {total_pages} 페이지)")
        else:
            self.lbl_info.setText("AetherPDF  |  로드된 문서 없음")

    def _on_mode_toggled(self, active_mode: str) -> None:
        """
        Ensure mutually exclusive toggling of mode buttons and emit signal.

        Args:
            active_mode (str): Key of the selected mode.
        """
        button_map = {
            "view": self.btn_mode_view,
            "edit_text": self.btn_mode_edit_text,
            "layout": self.btn_mode_layout,
            "annotate": self.btn_mode_annotate,
        }

        for mode, btn in button_map.items():
            btn.setChecked(mode == active_mode)

        self.mode_changed.emit(active_mode)

    def _on_zoom_in(self) -> None:
        """Handle zoom-in button click."""
        self.zoom_changed.emit(1.2)

    def _on_zoom_out(self) -> None:
        """Handle zoom-out button click."""
        self.zoom_changed.emit(1.0 / 1.2)

    def _on_zoom_combo_changed(self, index: int) -> None:
        """
        Handle combobox index changes.

        Args:
            index (int): Index of selected item.
        """
        text = self.combo_zoom.itemText(index)
        if text == "맞춤":
            self.zoom_changed.emit(0.0)
            return

        try:
            cleaned = text.split("%", 1)[0].strip()
            val = float(cleaned) / 100.0
            self.zoom_changed.emit(-val)
        except ValueError:
            pass

    def set_zoom_text(self, zoom_percentage: int) -> None:
        """
        Directly update the zoom combobox text display without firing signals.

        Args:
            zoom_percentage (int): Zoom percentage integer (e.g. 120).
        """
        self.combo_zoom.blockSignals(True)
        display_text = f"{zoom_percentage}%"
        index = self.combo_zoom.findText(display_text)
        if index >= 0:
            self.combo_zoom.setCurrentIndex(index)
        else:
            custom_index = self.combo_zoom.findData("current_zoom")
            if custom_index < 0:
                self.combo_zoom.insertItem(0, display_text, "current_zoom")
                custom_index = 0
            else:
                self.combo_zoom.setItemText(custom_index, display_text)
            self.combo_zoom.setCurrentIndex(custom_index)
        self.combo_zoom.blockSignals(False)
