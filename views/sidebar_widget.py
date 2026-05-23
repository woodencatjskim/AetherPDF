"""
Sidebar Widget for AetherPDF.

This widget provides the thumbnail navigator sidebar on the left side of the UI.
It renders low-resolution page previews, handles page selection, and supports
drag-and-drop page reordering for layout management.
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QAbstractItemView, QListView, QSizePolicy, QPushButton, QMenu
)
from PySide6.QtCore import Signal, Qt, QSize, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QIcon

from models.pdf_document import PdfDocument


class ThumbnailListWidget(QListWidget):
    """QListWidget that emits the page order after an internal drop."""

    order_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        """Initialize drag guidance state."""
        super().__init__(parent)
        self._drop_row: Optional[int] = None

    def dragEnterEvent(self, event) -> None:
        """Accept internal page drags and prepare the insertion guide."""
        event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        """Track the insertion row and repaint the drop guide line."""
        self._drop_row = self._insertion_row_at(event.position().toPoint())
        self.viewport().update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        """Clear the insertion guide when dragging leaves the list."""
        self._drop_row = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        """Move the dragged page to the guided insertion row."""
        source_row = self.currentRow()
        target_row = self._insertion_row_at(event.position().toPoint())
        self._drop_row = None
        self.viewport().update()

        if source_row < 0 or target_row < 0:
            event.ignore()
            return

        if target_row == source_row or target_row == source_row + 1:
            event.acceptProposedAction()
            return

        item = self.takeItem(source_row)
        if source_row < target_row:
            target_row -= 1

        self.insertItem(target_row, item)
        self.setCurrentItem(item)
        self.order_changed.emit(self._current_order())
        event.acceptProposedAction()

    def paintEvent(self, event) -> None:
        """Draw a clear insertion guide line during page drag reordering."""
        super().paintEvent(event)
        if self._drop_row is None:
            return

        y = self._guide_y_for_row(self._drop_row)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#00F0FF"), 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(18, y, max(18, self.viewport().width() - 18), y)
        painter.end()

    def _insertion_row_at(self, pos: QPoint) -> int:
        """Return the row where a dragged page should be inserted."""
        for row in range(self.count()):
            rect = self.visualItemRect(self.item(row))
            if pos.y() < rect.center().y():
                return row
        return self.count()

    def _guide_y_for_row(self, row: int) -> int:
        """Return the viewport y-position for the insertion guide."""
        if self.count() == 0:
            return 12
        if row <= 0:
            return self.visualItemRect(self.item(0)).top()
        if row >= self.count():
            return self.visualItemRect(self.item(self.count() - 1)).bottom() + 8

        current_rect = self.visualItemRect(self.item(row))
        previous_rect = self.visualItemRect(self.item(row - 1))
        return (previous_rect.bottom() + current_rect.top()) // 2

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
    page_action_requested = Signal(int, str)

    def __init__(self, parent=None) -> None:
        """Initialize the SidebarWidget layout."""
        super().__init__(parent)
        self.setObjectName("sidebarFrame")
        self.setMinimumWidth(140)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

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

        self.layout_controls = QFrame()
        controls_layout = QHBoxLayout(self.layout_controls)
        controls_layout.setContentsMargins(8, 0, 8, 0)
        controls_layout.setSpacing(6)

        self.btn_move_up = QPushButton("위로")
        self.btn_move_up.setToolTip("선택한 페이지를 위로 이동")
        self.btn_move_up.clicked.connect(lambda: self._move_selected_page(-1))

        self.btn_move_down = QPushButton("아래로")
        self.btn_move_down.setToolTip("선택한 페이지를 아래로 이동")
        self.btn_move_down.clicked.connect(lambda: self._move_selected_page(1))

        controls_layout.addWidget(self.btn_move_up)
        controls_layout.addWidget(self.btn_move_down)
        self.layout_controls.setVisible(False)
        layout.addWidget(self.layout_controls)

        # Thumbnail List Widget
        self.list_thumbnails = ThumbnailListWidget()
        self.list_thumbnails.setViewMode(QListView.IconMode)
        self.list_thumbnails.setFlow(QListView.TopToBottom)
        self.list_thumbnails.setWrapping(False)
        self.list_thumbnails.setResizeMode(QListWidget.Adjust)
        self.list_thumbnails.setMovement(QListWidget.Static)
        self.list_thumbnails.setIconSize(QSize(108, 150))
        self.list_thumbnails.setGridSize(QSize(132, 190))
        self.list_thumbnails.setSpacing(12)
        self.list_thumbnails.setDragDropOverwriteMode(False)
        self.list_thumbnails.setDefaultDropAction(Qt.MoveAction)
        self.list_thumbnails.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_thumbnails.customContextMenuRequested.connect(self._on_context_menu_requested)
        
        # Setup selection behavior
        self.list_thumbnails.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_thumbnails.currentRowChanged.connect(self._on_row_changed)
        self._set_page_reordering_enabled(True)

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
            self.layout_controls.setVisible(True)
        else:
            self.layout_controls.setVisible(False)

        self._set_page_reordering_enabled(True)

    def _set_page_reordering_enabled(self, enabled: bool) -> None:
        """Enable drag-and-drop page reordering in the thumbnail list."""
        self.list_thumbnails.setDragEnabled(enabled)
        self.list_thumbnails.setAcceptDrops(enabled)
        self.list_thumbnails.setDropIndicatorShown(enabled)
        mode = QAbstractItemView.InternalMove if enabled else QAbstractItemView.NoDragDrop
        self.list_thumbnails.setDragDropMode(mode)

    def _move_selected_page(self, offset: int) -> None:
        """Move the selected page one slot and emit the new page order."""
        current_row = self.list_thumbnails.currentRow()
        target_row = current_row + offset
        if current_row < 0 or target_row < 0 or target_row >= self.list_thumbnails.count():
            return

        item = self.list_thumbnails.takeItem(current_row)
        self.list_thumbnails.insertItem(target_row, item)
        self.list_thumbnails.setCurrentItem(item)
        self.pages_reordered.emit(self.list_thumbnails._current_order())

    def _on_context_menu_requested(self, pos: QPoint) -> None:
        """Show thumbnail actions for the page under the pointer."""
        item = self.list_thumbnails.itemAt(pos)
        if not item:
            return

        self.list_thumbnails.setCurrentItem(item)
        menu = QMenu(self)
        rotate_action = menu.addAction("페이지 회전(90도)")
        delete_action = menu.addAction("현재 페이지 삭제")
        insert_action = menu.addAction("새 빈 페이지 삽입")
        merge_action = menu.addAction("외부 PDF 파일 병합")

        selected_action = menu.exec(self.list_thumbnails.mapToGlobal(pos))
        action_map = {
            rotate_action: "rotate",
            delete_action: "delete",
            insert_action: "insert",
            merge_action: "merge",
        }
        if selected_action in action_map:
            self.page_action_requested.emit(item.data(Qt.UserRole), action_map[selected_action])

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
