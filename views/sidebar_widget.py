"""
Sidebar Widget for AetherPDF.

This widget provides the thumbnail navigator sidebar on the left side of the UI.
It renders low-resolution page previews, handles page selection, and supports
drag-and-drop page reordering for layout management.
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QAbstractItemView
)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QPixmap, QIcon

from models.pdf_document import PdfDocument


class ThumbnailListWidget(QListWidget):
    """QListWidget that emits the page order after an internal drop."""

    order_changed = Signal(list)

    def dropEvent(self, event) -> None:
        before = self._current_order()
        super().dropEvent(event)
        after = self._current_order()
        if after and after != before:
            self.order_changed.emit(after)

    def _current_order(self) -> List[int]:
        """Return current item order using each item's original page index."""
        order: List[int] = []
        for i in range(self.count()):
            item = self.item(i)
            if item:
                order.append(item.data(Qt.UserRole))
        return order


class SidebarWidget(QFrame):
    """
    Sidebar widget showing page thumbnails and layout controls.
    
    Signals:
        page_selected (int): Emitted when a thumbnail is selected (0-indexed).
        pages_reordered (list): Emitted when pages are reordered via drag-drop.
                                Passes a list of original indices.
    """
    page_selected = Signal(int)
    pages_reordered = Signal(list)

    def __init__(self, parent=None) -> None:
        """Initialize the SidebarWidget layout."""
        super().__init__(parent)
        self.setObjectName("sidebarFrame")
        self.setFixedWidth(200)

        self._pdf_doc: Optional[PdfDocument] = None
        self._block_signals: bool = False

        self._init_ui()

    def _init_ui(self) -> None:
        """Create and lay out inner widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(6)

        # Title Label
        self.label_title = QLabel("페이지 탐색")
        self.label_title.setObjectName("sidebarTitle")
        self.label_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_title)

        # Thumbnail List Widget
        self.list_thumbnails = ThumbnailListWidget()
        self.list_thumbnails.setViewMode(QListWidget.ListMode)
        self.list_thumbnails.setResizeMode(QListWidget.Adjust)
        self.list_thumbnails.setMovement(QListWidget.Static)
        self.list_thumbnails.setIconSize(QSize(100, 140))
        self.list_thumbnails.setSpacing(12)
        self.list_thumbnails.setDragDropOverwriteMode(False)
        self.list_thumbnails.setDefaultDropAction(Qt.MoveAction)
        
        # Setup selection behavior
        self.list_thumbnails.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_thumbnails.currentRowChanged.connect(self._on_row_changed)

        # Connect order drops (Layout Management support)
        self.list_thumbnails.order_changed.connect(self._on_order_changed)

        layout.addWidget(self.list_thumbnails)

    def set_document(self, pdf_doc: PdfDocument) -> None:
        """
        Bind PDF document and generate thumbnails.

        Args:
            pdf_doc (PdfDocument): The active PDF document model.
        """
        self._pdf_doc = pdf_doc
        self.refresh_thumbnails()

    def refresh_thumbnails(self) -> None:
        """Regenerate and reload thumbnails from the bound PDF document."""
        # 현재 선택되어 있는 페이지의 인덱스를 기억함
        current_item = self.list_thumbnails.currentItem()
        active_idx = current_item.data(Qt.UserRole) if current_item else 0

        self._block_signals = True
        self.list_thumbnails.clear()

        if not self._pdf_doc or not self._pdf_doc.is_loaded:
            self._block_signals = False
            return

        # Render low-resolution thumbnails
        # 35 DPI provides lightning-fast rendering and saves substantial memory
        for i in range(self._pdf_doc.page_count):
            try:
                # Render page to low-res QImage
                q_img = self._pdf_doc.render_page(i, dpi=35)
                pixmap = QPixmap.fromImage(q_img)
                
                # Create List Item with page preview
                item = QListWidgetItem()
                item.setIcon(QIcon(pixmap))
                item.setText(f"페이지 {i + 1}")
                item.setTextAlignment(Qt.AlignCenter)
                
                # Store the original index inside the item's custom user data
                # to track reordering
                item.setData(Qt.UserRole, i)
                
                self.list_thumbnails.addItem(item)
            except Exception:
                # Fallback item in case of rendering errors
                item = QListWidgetItem(f"에러 (p.{i + 1})")
                item.setData(Qt.UserRole, i)
                self.list_thumbnails.addItem(item)

        self._block_signals = False
        
        # 기존에 선택되어 있던 페이지를 다시 선택해줌 (없었으면 0페이지)
        if self.list_thumbnails.count() > 0:
            target_idx = min(active_idx, self.list_thumbnails.count() - 1)
            self.select_page(target_idx)

    def select_page(self, page_index: int) -> None:
        """
        Highlight the thumbnail of the selected page index.

        Args:
            page_index (int): 0-indexed page number.
        """
        if self._block_signals or self.list_thumbnails.count() <= page_index:
            return

        self._block_signals = True
        # Find which item corresponds to page_index (checking UserRole data)
        for i in range(self.list_thumbnails.count()):
            item = self.list_thumbnails.item(i)
            if item and item.data(Qt.UserRole) == page_index:
                self.list_thumbnails.setCurrentItem(item)
                break
        self._block_signals = False

    def enable_drag_and_drop(self, enabled: bool) -> None:
        """
        Enable or disable drag & drop functionality for page reordering [C].

        Args:
            enabled (bool): True to enable page dragging, False to lock list.
        """
        if enabled:
            self.list_thumbnails.setDragEnabled(True)
            self.list_thumbnails.setAcceptDrops(True)
            self.list_thumbnails.setDropIndicatorShown(True)
            self.list_thumbnails.setDragDropMode(QAbstractItemView.InternalMove)
        else:
            self.list_thumbnails.setDragEnabled(False)
            self.list_thumbnails.setAcceptDrops(False)
            self.list_thumbnails.setDropIndicatorShown(False)
            self.list_thumbnails.setDragDropMode(QAbstractItemView.NoDragDrop)

    def _on_row_changed(self, row: int) -> None:
        """
        Handle thumbnail list row changes.

        Args:
            row (int): The selected row index.
        """
        if self._block_signals or row < 0:
            return

        item = self.list_thumbnails.item(row)
        if item:
            original_idx = item.data(Qt.UserRole)
            self.page_selected.emit(original_idx)

    def _on_order_changed(self, new_order: List[int]) -> None:
        """
        Track and report drag-drop reordering changes.
        """
        if self._block_signals:
            return

        self.pages_reordered.emit(new_order)
