"""
PDF Viewer Widget for AetherPDF.

This widget inherits QGraphicsView to host the high-resolution PDF canvas.
It supports rendering pages, smooth zooming and panning, and implements
the interactive overlay text editor for direct body text editing [B].
"""

from typing import List, Dict, Any, Tuple, Optional
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsWidget,
    QLineEdit, QGraphicsProxyWidget, QGraphicsPathItem, QGraphicsRectItem
)
from PySide6.QtCore import Signal, Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPixmap, QImage, QMouseEvent, QWheelEvent, QCursor,
    QPen, QBrush, QColor, QPainterPath
)
import fitz


from models.pdf_document import PdfDocument
from config.settings import ZOOM_STEP, MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM, DEFAULT_DPI


class PdfViewerWidget(QGraphicsView):
    """
    Interactive Graphics View canvas for PDF page viewing and editing.
    
    Signals:
        zoom_level_changed (int): Emitted when zoom level changes (as integer percentage).
        text_modified (int, dict, str, str): Emitted when a body text block is modified.
            Passes: (page_index, block_metadata, old_text, new_text)
    """
    zoom_level_changed = Signal(int)
    text_modified = Signal(int, dict, str, str, object)
    text_added = Signal(int, tuple, str, object)
    text_style_selected = Signal(dict)
    annotation_added = Signal(int, str, list, tuple, float, float)  # (page_idx, type, rects/lines, color, width, opacity)
    page_navigation_requested = Signal(int)  # 1: next, -1: prev [NEW]

    def __init__(self, parent=None) -> None:
        """Initialize the viewer scene and parameters."""
        super().__init__(parent)
        self.setObjectName("pdfViewer")
        
        # Performance optimizations for high-res graphics
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Panning state
        self.setDragMode(QGraphicsView.NoDrag)
        self._is_panning: bool = False
        self._pan_start_x: int = 0
        self._pan_start_y: int = 0
        
        # PDF details
        self._pdf_doc: Optional[PdfDocument] = None
        self._current_page_idx: int = 0
        self._zoom_factor: float = DEFAULT_ZOOM
        self._active_mode: str = "view"  # "view", "edit_text", "layout", "annotate"

        # Graphics Scene & Items
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._page_pixmap_item: Optional[QGraphicsPixmapItem] = None
        
        # Inline text editor overlay
        self._active_proxy_editor: Optional[QGraphicsProxyWidget] = None
        self._active_editor_widget: Optional[QLineEdit] = None
        self._active_editor_block: Optional[Dict[str, Any]] = None
        self._active_editor_point: Optional[Tuple[float, float]] = None
        self._active_editor_is_new: bool = False
        self._active_editor_style_dirty: bool = False
        self._text_style: Dict[str, Any] = {
            "color": (0.0, 0.0, 0.0),
            "font_size": 12.0,
            "bold": False,
            "italic": False,
        }

        # Annotation active settings
        self._annot_tool: str = "highlight"
        self._annot_color: Tuple[float, float, float] = (1.0, 1.0, 0.0)
        self._annot_width: float = 3.0
        self._annot_opacity: float = 1.0

        # Drawing / Dragging states
        self._ink_points: List[Tuple[float, float]] = []
        self._is_drawing: bool = False
        self._ink_path_item: Optional[QGraphicsPathItem] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._is_dragging_rect: bool = False
        self._drag_rect_item: Optional[QGraphicsRectItem] = None
        
        # Staged modifications to emit safely after widget detachment
        self._pending_modification: Optional[Tuple[int, Dict[str, Any], str, str, Dict[str, Any]]] = None
        self._pending_text_addition: Optional[Tuple[int, Tuple[float, float], str, Dict[str, Any]]] = None

        # Drag-and-drop & Wheel page transition settings [NEW]
        self.setAcceptDrops(True)
        self._last_page_nav_time: float = 0.0



    def set_document(self, pdf_doc: PdfDocument) -> None:
        """
        Bind the PDF document model.

        Args:
            pdf_doc (PdfDocument): The loaded PDF model.
        """
        self._pdf_doc = pdf_doc
        self._current_page_idx = 0
        self._zoom_factor = DEFAULT_ZOOM
        self.resetTransform()
        self.load_page(0)

    def set_active_mode(self, mode: str) -> None:
        """
        Set the active editor mode.

        Args:
            mode (str): One of "view", "edit_text", "layout", "annotate".
        """
        self._active_mode = mode
        self._cleanup_active_editor()
        
        if mode == "edit_text":
            self.setCursor(Qt.IBeamCursor)
        elif mode == "annotate":
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def set_annot_tool(self, tool: str) -> None:
        """
        Set the active annotation tool type.

        Args:
            tool (str): Tool type like "highlight", "underline", "strikeout", "ink".
        """
        self._annot_tool = tool

    def set_annot_color(self, color: Tuple[float, float, float]) -> None:
        """
        Set the active drawing color.

        Args:
            color (Tuple[float, float, float]): RGB float values.
        """
        self._annot_color = color

    def set_annot_width(self, width: float) -> None:
        """
        Set the active line/border thickness.

        Args:
            width (float): Thickness in pixels.
        """
        self._annot_width = width

    def set_annot_opacity(self, opacity: float) -> None:
        """
        Set the active drawing opacity.

        Args:
            opacity (float): Opacity value (0.0 - 1.0).
        """
        self._annot_opacity = opacity

    def set_text_style(self, style: Dict[str, Any]) -> None:
        """
        Set the active text insertion/replacement style.

        Args:
            style (Dict[str, Any]): color, font_size, bold, italic.
        """
        self._text_style.update(style)
        if self._active_editor_widget:
            self._active_editor_style_dirty = True
            self._apply_editor_style(self._active_editor_widget)


    def load_page(self, page_index: int) -> None:
        """
        Render and load a specific page into the scene.

        Args:
            page_index (int): 0-indexed page index.
        """
        self._cleanup_active_editor()
        
        if not self._pdf_doc or not self._pdf_doc.is_loaded:
            self._scene.clear()
            self._page_pixmap_item = None
            return

        if page_index < 0 or page_index >= self._pdf_doc.page_count:
            return

        self._current_page_idx = page_index
        self._scene.clear()
        self._page_pixmap_item = None

        try:
            # Render page at 150 DPI for crisp visual output
            q_img = self._pdf_doc.render_page(page_index)
            pixmap = QPixmap.fromImage(q_img)
            
            # Place page Pixmap in scene
            self._page_pixmap_item = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._page_pixmap_item)
            
            # Set scene size exactly to page pixmap size
            self.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            self._report_zoom_percentage()
        except Exception:
            pass

    def set_zoom(self, absolute_scale: float) -> None:
        """
        Set absolute zoom level (e.g. 1.0 = 100%).

        Args:
            absolute_scale (float): Scale multiplier.
        """
        # Clamp scale
        scale = max(MIN_ZOOM, min(MAX_ZOOM, absolute_scale))
        self._zoom_factor = scale
        
        # Apply transformation matrix
        self.resetTransform()
        self.scale(self._zoom_factor, self._zoom_factor)
        self._report_zoom_percentage()

    def zoom_by_factor(self, factor: float) -> None:
        """
        Multiply the current zoom level by a factor.

        Args:
            factor (float): Multiplier (e.g. 1.2 to zoom in, 0.8 to zoom out).
        """
        self.set_zoom(self._zoom_factor * factor)

    def fit_to_width(self) -> None:
        """Adjust zoom to fit the current page width inside the viewport."""
        if not self._page_pixmap_item:
            return
        
        # Viewport width minus some padding for scrollbars
        view_width = self.viewport().width() - 25
        page_width = self._page_pixmap_item.pixmap().width()
        
        if page_width > 0:
            scale = view_width / page_width
            self.set_zoom(scale)

    def _report_zoom_percentage(self) -> None:
        """Emit current zoom level percentage."""
        pct = int(round(self._zoom_factor * 100))
        self.zoom_level_changed.emit(pct)

    # --- Mouse Event Handlers & Panning & Annotations ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse clicks for Panning, Inline Text Editing [B], and Annotations [A]."""
        # Panning activation: Right click or middle click
        if event.button() in (Qt.RightButton, Qt.MiddleButton):
            self._is_panning = True
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # Left click interaction
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            
            # [A] Annotation Mode interaction
            if self._active_mode == "annotate":
                if self._annot_tool == "ink":
                    self._is_drawing = True
                    self._ink_points = [(scene_pos.x(), scene_pos.y())]
                    
                    # Create pen style based on color settings (float RGB to QColor)
                    q_col = QColor.fromRgbF(
                        self._annot_color[0],
                        self._annot_color[1],
                        self._annot_color[2],
                        self._annot_opacity
                    )
                    pen = QPen(q_col, self._annot_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                    
                    path = QPainterPath()
                    path.moveTo(scene_pos)
                    
                    self._ink_path_item = QGraphicsPathItem()
                    self._ink_path_item.setPen(pen)
                    self._ink_path_item.setPath(path)
                    self._scene.addItem(self._ink_path_item)
                    event.accept()
                    return
                elif self._annot_tool in ("highlight", "underline", "strikeout"):
                    self._is_dragging_rect = True
                    self._drag_start_pos = scene_pos
                    
                    # Glowing Cyan dotted bounding box for premium dragging guide
                    pen = QPen(QColor("#00F0FF"), 1, Qt.DashLine)
                    brush = QBrush(QColor(0, 240, 255, 30))  # 12% opacity
                    
                    self._drag_rect_item = QGraphicsRectItem(QRectF(scene_pos, scene_pos))
                    self._drag_rect_item.setPen(pen)
                    self._drag_rect_item.setBrush(brush)
                    self._scene.addItem(self._drag_rect_item)
                    event.accept()
                    return

            # [B] Inline Text Edit Mode interaction
            elif self._active_mode == "edit_text":
                if self._active_proxy_editor:
                    # Check if clicked inside the bounds of the active editor widget
                    editor_rect = self._active_proxy_editor.sceneBoundingRect()
                    if editor_rect.contains(scene_pos):
                        # Pass click straight to the widget (allows moving cursor, selecting text, etc.)
                        super().mousePressEvent(event)
                        return
                    else:
                        # Clicked outside: commit and close active editor
                        self._on_editor_finished()
                        event.accept()
                        return

                if self._try_activate_text_editor(scene_pos):
                    event.accept()
                    return

                if self._try_activate_new_text_editor(scene_pos):
                    event.accept()
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle panning and real-time annotation visual feed."""
        if self._is_panning:
            # Scroll view dynamically by movement delta
            dx = event.position().x() - self._pan_start_x
            dy = event.position().y() - self._pan_start_y
            
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - dx)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - dy)
            
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            event.accept()
            return

        # Ink Drawing Real-time feedback
        if self._active_mode == "annotate" and self._is_drawing and self._ink_path_item:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._ink_points.append((scene_pos.x(), scene_pos.y()))
            
            path = self._ink_path_item.path()
            path.lineTo(scene_pos)
            self._ink_path_item.setPath(path)
            event.accept()
            return

        # Selection Guide Rect Real-time feedback
        if self._active_mode == "annotate" and self._is_dragging_rect and self._drag_rect_item:
            scene_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._drag_start_pos, scene_pos).normalized()
            self._drag_rect_item.setRect(rect)
            event.accept()
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Deactivate panning/drawing and commit created Annotations to model."""
        if event.button() in (Qt.RightButton, Qt.MiddleButton) and self._is_panning:
            self._is_panning = False
            if self._active_mode == "edit_text":
                self.setCursor(Qt.IBeamCursor)
            elif self._active_mode == "annotate":
                self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            event.accept()
            return

        # Commit drawing annotation
        if event.button() == Qt.LeftButton and self._active_mode == "annotate":
            scale_ratio = 72.0 / DEFAULT_DPI
            
            if self._is_drawing and self._ink_path_item:
                self._is_drawing = False
                self._scene.removeItem(self._ink_path_item)
                self._ink_path_item = None
                
                if len(self._ink_points) > 1:
                    # Translate scene pixels back to fitz points (72 DPI)
                    fitz_lines = [
                        [(p[0] * scale_ratio, p[1] * scale_ratio) for p in self._ink_points]
                    ]
                    
                    self.annotation_added.emit(
                        self._current_page_idx,
                        "ink",
                        fitz_lines,
                        self._annot_color,
                        self._annot_width,
                        self._annot_opacity
                    )
                self._ink_points.clear()
                event.accept()
                return
                
            elif self._is_dragging_rect and self._drag_rect_item:
                self._is_dragging_rect = False
                scene_rect = self._drag_rect_item.rect()
                self._scene.removeItem(self._drag_rect_item)
                self._drag_rect_item = None
                
                # Check for non-empty selection box
                if scene_rect.width() > 3 and scene_rect.height() > 3:
                    # Translate to fitz bounding box
                    fitz_rect = fitz.Rect(
                        scene_rect.left() * scale_ratio,
                        scene_rect.top() * scale_ratio,
                        scene_rect.right() * scale_ratio,
                        scene_rect.bottom() * scale_ratio
                    )
                    
                    target_rects = []
                    
                    # Fine-grained Text Span Intersection Detection
                    if self._pdf_doc and self._pdf_doc.is_loaded:
                        blocks = self._pdf_doc.get_text_blocks(self._current_page_idx)
                        for block in blocks:
                            if block.get("type") == 0:  # Text block
                                for line in block.get("lines", []):
                                    for span in line.get("spans", []):
                                        s_bbox = span.get("bbox")
                                        if s_bbox:
                                            span_rect = fitz.Rect(s_bbox)
                                            # Intersect check: if overlap area is substantial
                                            intersect = span_rect.intersect(fitz_rect)
                                            if not intersect.is_empty and intersect.get_area() > 5:
                                                target_rects.append(span_rect)
                    
                    # Fallback to the raw drag area itself if no characters intersect
                    # (allows highlighting empty sections or non-extracted text images)
                    if not target_rects:
                        target_rects = [fitz_rect]
                        
                    self.annotation_added.emit(
                        self._current_page_idx,
                        self._annot_tool,
                        target_rects,
                        self._annot_color,
                        self._annot_width,
                        self._annot_opacity
                    )
                self._drag_start_pos = None
                event.accept()
                return
            
        super().mouseReleaseEvent(event)


    def wheelEvent(self, event: QWheelEvent) -> None:
        """Support standard Ctrl + MouseWheel zoom control and page boundary auto-scroll."""
        if event.modifiers() == Qt.ControlModifier:
            # Zoom in/out based on wheel angle delta
            if event.angleDelta().y() > 0:
                self.zoom_by_factor(ZOOM_STEP)
            else:
                self.zoom_by_factor(1.0 / ZOOM_STEP)
            event.accept()
            return
        
        # 일반 스크롤 시 스크롤바 한계 도달 검사 및 다음/이전 페이지 이동 [NEW]
        v_bar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        
        import time
        now = time.time()
        
        if delta < 0:  # 아래로 스크롤
            if v_bar.value() >= v_bar.maximum():
                if now - self._last_page_nav_time >= 0.5:
                    self._last_page_nav_time = now
                    self.page_navigation_requested.emit(1)
                event.accept()
                return
        elif delta > 0:  # 위로 스크롤
            if v_bar.value() <= v_bar.minimum():
                if now - self._last_page_nav_time >= 0.5:
                    self._last_page_nav_time = now
                    self.page_navigation_requested.emit(-1)
                event.accept()
                return
                
        super().wheelEvent(event)

    # --- [NEW] Viewer Drag and Drop file loading support ---
    def dragEnterEvent(self, event) -> None:
        """Accept dragged PDF files over the viewer area [NEW]."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        """Allow drag movement over the viewer [NEW]."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        """Handle PDF dropped over the viewer and forward it to MainWindow [NEW]."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                if filepath.lower().endswith(".pdf"):
                    main_win = self.window()
                    if main_win and hasattr(main_win, "open_dropped_file"):
                        main_win.open_dropped_file(filepath)
                        event.acceptProposedAction()
                        return
        super().dropEvent(event)

    # --- [B] Body Text Direct Editing: Inline Overlay Logic ---

    def _try_activate_text_editor(self, scene_pos: QPointF) -> bool:
        """
        Check if the clicked scene coordinate lands inside a text block.
        If yes, overlay an interactive QLineEdit over the exact block location.
        """
        if not self._pdf_doc or not self._pdf_doc.is_loaded:
            return False

        # Scale coordinates back to fitz points (MuPDF is always 72 DPI internally)
        # Note: self._pdf_doc.render_page rendered the page at DEFAULT_DPI (150 DPI)
        scale_ratio = 72.0 / DEFAULT_DPI
        pdf_x = scene_pos.x() * scale_ratio
        pdf_y = scene_pos.y() * scale_ratio

        # Retrieve structural text blocks for current page
        blocks = self._pdf_doc.get_text_blocks(self._current_page_idx)
        
        # Find block containing target coordinate
        for block in blocks:
            # block["type"] == 0 means it contains text
            if block.get("type") == 0:
                bbox = block.get("bbox")  # (x0, y0, x1, y1)
                if bbox and bbox[0] <= pdf_x <= bbox[2] and bbox[1] <= pdf_y <= bbox[3]:
                    # Found target text block! Clean up any active editor first
                    self._cleanup_active_editor()
                    
                    # Accumulate block text lines into a single editable string
                    lines_text = []
                    for line in block.get("lines", []):
                        line_str = "".join([span.get("text", "") for span in line.get("spans", [])])
                        lines_text.append(line_str)
                    
                    block_full_text = "\n".join(lines_text).strip()
                    
                    # Map fitz bbox to Scene Coordinates
                    scene_x = bbox[0] / scale_ratio
                    scene_y = bbox[1] / scale_ratio
                    scene_w = (bbox[2] - bbox[0]) / scale_ratio
                    scene_h = (bbox[3] - bbox[1]) / scale_ratio

                    # Create QLineEdit as Inline Editor Overlay
                    selected_style = self._text_style_from_block(block, pdf_x, pdf_y)
                    self._text_style.update(selected_style)
                    self.text_style_selected.emit(dict(self._text_style))

                    editor = QLineEdit()
                    editor.setText(block_full_text)
                    self._apply_editor_style(editor)
                    
                    # Size editor exactly matching the block dimensions (with small padding)
                    editor.setGeometry(0, 0, max(scene_w, 150), max(scene_h, 24))
                    
                    # Wrap widget as Graphics Proxy to embed inside 3D Zoomable Scene
                    self._active_proxy_editor = self._scene.addWidget(editor)
                    self._active_proxy_editor.setPos(scene_x, scene_y)
                    
                    self._active_editor_widget = editor
                    self._active_editor_block = block
                    self._active_editor_point = None
                    self._active_editor_is_new = False
                    self._active_editor_style_dirty = False
                    
                    # Set focus to editor and select all text
                    editor.setFocus()
                    editor.selectAll()
                    
                    # Connect finish triggers
                    editor.returnPressed.connect(self._on_editor_finished)
                    
                    return True
        return False

    def _text_style_from_block(self, block: Dict[str, Any], pdf_x: float, pdf_y: float) -> Dict[str, Any]:
        """Extract text color and size from the span under the clicked point."""
        fallback_span = None
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                fallback_span = fallback_span or span
                bbox = span.get("bbox")
                if bbox and bbox[0] <= pdf_x <= bbox[2] and bbox[1] <= pdf_y <= bbox[3]:
                    return self._style_from_span(span)

        return self._style_from_span(fallback_span) if fallback_span else {}

    def _style_from_span(self, span: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a PyMuPDF text span style into the editor style dictionary."""
        style: Dict[str, Any] = {}
        size = span.get("size")
        if isinstance(size, (int, float)):
            style["font_size"] = max(6.0, min(72.0, float(size)))

        color = span.get("color")
        if isinstance(color, int):
            style["color"] = (
                ((color >> 16) & 0xFF) / 255.0,
                ((color >> 8) & 0xFF) / 255.0,
                (color & 0xFF) / 255.0,
            )

        return style

    def _try_activate_new_text_editor(self, scene_pos: QPointF) -> bool:
        """Create an inline editor at an empty page location for new text."""
        if not self._pdf_doc or not self._pdf_doc.is_loaded:
            return False

        self._cleanup_active_editor()

        scale_ratio = 72.0 / DEFAULT_DPI
        pdf_x = scene_pos.x() * scale_ratio
        pdf_y = scene_pos.y() * scale_ratio

        editor = QLineEdit()
        editor.setPlaceholderText("텍스트 입력")
        self._apply_editor_style(editor)
        editor.setGeometry(0, 0, 240, max(int(self._text_style["font_size"] * 2.2), 28))

        self._active_proxy_editor = self._scene.addWidget(editor)
        self._active_proxy_editor.setPos(scene_pos.x(), scene_pos.y())

        self._active_editor_widget = editor
        self._active_editor_block = {"bbox": (pdf_x, pdf_y, pdf_x, pdf_y), "lines": []}
        self._active_editor_point = (pdf_x, pdf_y)
        self._active_editor_is_new = True
        self._active_editor_style_dirty = False

        editor.setFocus()
        editor.returnPressed.connect(self._on_editor_finished)
        return True

    def _apply_editor_style(self, editor: QLineEdit) -> None:
        """Apply active text style to the inline editor preview."""
        color = self._text_style.get("color", (0.0, 0.0, 0.0))
        q_color = QColor.fromRgbF(color[0], color[1], color[2])
        editor.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1A1A1E;
                color: {q_color.name()};
                border: 1px solid #00F0FF;
                border-radius: 2px;
                padding: 2px;
                font-size: {int(self._text_style.get("font_size", 12))}px;
            }}
        """)
        font = editor.font()
        font.setPointSizeF(float(self._text_style.get("font_size", 12.0)))
        font.setBold(bool(self._text_style.get("bold", False)))
        font.setItalic(bool(self._text_style.get("italic", False)))
        editor.setFont(font)

    def _on_editor_finished(self) -> None:
        """Handle inline editor submission when Enter is pressed."""
        if not self._active_proxy_editor or not self._active_editor_block:
            return

        editor_widget = self._active_proxy_editor.widget()
        if isinstance(editor_widget, QLineEdit):
            # Disable editor to prevent further user input or double triggers
            editor_widget.setEnabled(False)
            editor_widget.clearFocus()
            
            new_text = editor_widget.text()
            
            if self._active_editor_is_new:
                if new_text.strip() and self._active_editor_point:
                    self._pending_text_addition = (
                        self._current_page_idx,
                        self._active_editor_point,
                        new_text,
                        dict(self._text_style)
                    )
                else:
                    self._pending_text_addition = None
                self._pending_modification = None
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._cleanup_active_editor)
                return

            # Reconstruct old text
            lines_text = []
            for line in self._active_editor_block.get("lines", []):
                line_str = "".join([span.get("text", "") for span in line.get("spans", [])])
                lines_text.append(line_str)
            old_text = "\n".join(lines_text).strip()

            if old_text != new_text or self._active_editor_style_dirty:
                # Stage the modification to emit safely after the editor widget is detached
                self._pending_modification = (
                    self._current_page_idx,
                    self._active_editor_block,
                    old_text,
                    new_text,
                    dict(self._text_style)
                )
            else:
                self._pending_modification = None

        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._cleanup_active_editor)

    def _cleanup_active_editor(self) -> None:
        """Safely remove the active inline editor overlay from the scene."""
        if self._active_proxy_editor:
            widget = self._active_proxy_editor.widget()
            if widget:
                widget.deleteLater()
            self._scene.removeItem(self._active_proxy_editor)
            self._active_proxy_editor = None
        self._active_editor_widget = None
        self._active_editor_block = None
        self._active_editor_point = None
        self._active_editor_is_new = False
        self._active_editor_style_dirty = False

        # Emit staged modifications safely now that the editor widget is fully detached from the scene
        if hasattr(self, "_pending_modification") and self._pending_modification:
            page_idx, block, old_txt, new_txt, text_style = self._pending_modification
            self._pending_modification = None
            self.text_modified.emit(page_idx, block, old_txt, new_txt, text_style)
        if hasattr(self, "_pending_text_addition") and self._pending_text_addition:
            page_idx, point, text, text_style = self._pending_text_addition
            self._pending_text_addition = None
            self.text_added.emit(page_idx, point, text, text_style)
