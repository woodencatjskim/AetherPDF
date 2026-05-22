"""
PDF Editor Service for AetherPDF.

This module houses the business logic for direct body text modifications [B].
It utilizes MuPDF Redaction API to cleanly erase existing text blocks and overlay
the newly entered text, preserving fonts, sizes, and colors where possible.
"""

from typing import Dict, Any, Tuple, Optional
import os
import fitz  # PyMuPDF


class PdfEditorService:
    """
    Service class handling operations that modify the PDF's internal document tree.
    """

    @staticmethod
    def replace_block_text(
        doc: fitz.Document,
        page_index: int,
        block: Dict[str, Any],
        new_text: str,
        text_style: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Replace a body text block inside a PDF page.

        Erases the text at the block's bounding box using Redactions and
        writes the new text with original typographic styles (font size, color).

        Args:
            doc (fitz.Document): Fitz Document instance to modify.
            page_index (int): 0-indexed target page.
            block (Dict[str, Any]): Original fitz block dictionary containing bbox and spans.
            new_text (str): The replacement text.

        Returns:
            bool: True if modification succeeded, False otherwise.

        Raises:
            ValueError: If inputs are invalid or page cannot be loaded.
        """
        if not doc:
            raise ValueError("Document instance is null.")

        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} is out of bounds.")

        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            raise ValueError("Invalid text block bounding box.")

        try:
            page = doc.load_page(page_index)
            rect = fitz.Rect(bbox)

            # 1. Parse font attributes from the original block spans to maintain style
            font_size, font_name, text_color = PdfEditorService._extract_typographic_styles(block)
            font_size, font_name, text_color = PdfEditorService._merge_text_style(
                font_size, font_name, text_color, text_style
            )

            # [한글 깨짐(????) 방지 패치]
            # 영문 표준 폰트는 한글 유니코드를 그리지 못해 물음표(?)로 깨집니다.
            # 입력된 텍스트에 한글이 한 글자라도 포함되어 있다면, 내장 CJK 한글 폰트인 'cjk'로 대체하고 임베딩을 예약합니다.
            if PdfEditorService._has_hangul(new_text):
                font_name = "cjk"

            # 2. Add Redaction Annotation to cleanly wipe out old graphics/text in bbox
            # fill=None prevents rendering a black block (we want transparent erase)
            page.add_redact_annot(rect, text="", fill=None)

            # Apply redactions to commit the deletion of original text/images in this bounding box
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            # CRITICAL: apply_redactions() invalidates or rebuilds the page structure in MuPDF memory.
            # We MUST reload the page from the document to obtain a fresh, valid C++ page pointer
            # before invoking insert_textbox, otherwise a Segmentation Fault will crash the process!
            page = doc.load_page(page_index)

            # [한글 폰트 임베딩 주입]
            # PyMuPDF에서 CJK 폰트 데이터를 리소스로 확실히 포함시키기 위해,
            # fitz.Font("cjk") 버퍼를 페이지 리소스에 강제 임베딩 등록합니다.
            # 이를 통해 뷰어 및 저장된 파일 모두에서 한글 렌더링이 깨지지 않습니다.
            if font_name == "cjk":
                cjk_font = fitz.Font("cjk")
                page.insert_font(fontname="cjk", fontbuffer=cjk_font.buffer)

            # 3. Insert the new text into an expanded bounding box to prevent text truncation/overflow.
            # We expand the right border (x1) and bottom border (y1) to accommodate longer texts.
            write_rect = fitz.Rect(bbox)
            page_width = page.rect.width
            
            # Allow width to stretch up to page margin or at least 400 points
            write_rect.x1 = max(write_rect.x1, min(page_width - 30, write_rect.x0 + 400))
            # Allow height to stretch to handle possible multi-line wrapping
            write_rect.y1 = max(write_rect.y1, write_rect.y0 + max(font_size * 4, 60))

            res = page.insert_textbox(
                write_rect,
                new_text,
                fontsize=font_size,
                fontname=font_name,
                color=text_color,
                align=0  # Default to Left align
            )
            
            # PyMuPDF returns negative values on overflow
            if res < 0:
                raise RuntimeError(f"Text insertion overflow. Required more space than {write_rect}.")

            return True
        except Exception as e:
            # Propagate detailed message
            raise RuntimeError(f"Redaction text replacement failed: {str(e)}")

    @staticmethod
    def add_free_text(
        doc: fitz.Document,
        page_index: int,
        point: Tuple[float, float],
        text: str,
        text_style: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add text at an empty location on a PDF page.

        Args:
            doc (fitz.Document): Fitz Document instance to modify.
            page_index (int): 0-indexed target page.
            point (Tuple[float, float]): Top-left insertion point in PDF points.
            text (str): Text to add.
            text_style (Optional[Dict[str, Any]]): color, font_size, bold, italic.

        Returns:
            bool: True if insertion succeeded.
        """
        if not doc:
            raise ValueError("Document instance is null.")

        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} is out of bounds.")

        if not text.strip():
            return False

        try:
            page = doc.load_page(page_index)
            font_size, font_name, text_color = PdfEditorService._merge_text_style(
                11.0, "helv", (0.0, 0.0, 0.0), text_style
            )

            if PdfEditorService._has_hangul(text):
                font_name = "cjk"

            if font_name == "cjk":
                cjk_font = fitz.Font("cjk")
                page.insert_font(fontname="cjk", fontbuffer=cjk_font.buffer)

            x, y = point
            write_rect = fitz.Rect(
                x,
                y,
                min(page.rect.width - 30, x + 400),
                min(page.rect.height - 30, y + max(font_size * 4, 60))
            )

            res = page.insert_textbox(
                write_rect,
                text,
                fontsize=font_size,
                fontname=font_name,
                color=text_color,
                align=0
            )

            if res < 0:
                raise RuntimeError(f"Text insertion overflow. Required more space than {write_rect}.")

            return True
        except Exception as e:
            raise RuntimeError(f"Free text insertion failed: {str(e)}")

    @staticmethod
    def reorder_pages(doc: fitz.Document, new_order: list[int]) -> bool:
        """
        Reorder PDF pages dynamically using the select API.

        Args:
            doc (fitz.Document): Fitz Document instance.
            new_order (list[int]): Ordered list of original page indices (e.g. [2, 0, 1]).

        Returns:
            bool: True if successful.
        """
        if not doc:
            raise ValueError("Document instance is null.")
        
        # Check index bounds
        max_idx = len(doc) - 1
        for idx in new_order:
            if idx < 0 or idx > max_idx:
                raise ValueError(f"Index {idx} out of range [0, {max_idx}].")

        try:
            # Reorganize pages instantly in memory
            doc.select(new_order)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to reorder pages: {str(e)}")

    @staticmethod
    def rotate_page(doc: fitz.Document, page_index: int, angle_delta: int = 90) -> bool:
        """
        Rotate a specific page by 90 degrees delta.

        Args:
            doc (fitz.Document): Fitz Document instance.
            page_index (int): Target page index.
            angle_delta (int): Degrees to rotate (positive for clockwise, usually 90).

        Returns:
            bool: True if successful.
        """
        if not doc or page_index < 0 or page_index >= len(doc):
            raise ValueError("Invalid document or page index.")

        try:
            page = doc.load_page(page_index)
            # MuPDF sets rotation in absolute degrees (0, 90, 180, 270)
            current_rotation = page.rotation
            new_rotation = (current_rotation + angle_delta) % 360
            page.set_rotation(new_rotation)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to rotate page: {str(e)}")

    @staticmethod
    def delete_page(doc: fitz.Document, page_index: int) -> bool:
        """
        Delete a page from the PDF document.

        Args:
            doc (fitz.Document): Fitz Document instance.
            page_index (int): Page index to delete.

        Returns:
            bool: True if successful.
        """
        if not doc or page_index < 0 or page_index >= len(doc):
            raise ValueError("Invalid document or page index.")

        try:
            doc.delete_page(page_index)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to delete page: {str(e)}")

    @staticmethod
    def insert_blank_page(doc: fitz.Document, page_index: int, width: float = 595.0, height: float = 842.0) -> bool:
        """
        Insert an empty blank page (A4 size default) at a specific position.

        Args:
            doc (fitz.Document): Fitz Document instance.
            page_index (int): Location to insert (e.g. 0 to prepend, len(doc) to append).
            width (float): Page width in points (default A4 = 595).
            height (float): Page height in points (default A4 = 842).

        Returns:
            bool: True if successful.
        """
        if not doc or page_index < 0 or page_index > len(doc):
            raise ValueError("Invalid document or insertion index.")

        try:
            # doc.new_page returns the created Page object
            doc.new_page(pno=page_index, width=width, height=height)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to insert blank page: {str(e)}")

    @staticmethod
    def merge_pdf(doc: fitz.Document, other_filepath: str, start_at: int) -> bool:
        """
        Merge pages from an external PDF file into the active document.

        Args:
            doc (fitz.Document): Target active Fitz Document.
            other_filepath (str): Absolute file path to the external PDF.
            start_at (int): Insert position index in the active document.

        Returns:
            bool: True if successful.
        """
        if not doc or start_at < 0 or start_at > len(doc):
            raise ValueError("Invalid document or insert position.")

        if not os.path.exists(other_filepath):
            raise FileNotFoundError(f"External PDF not found at {other_filepath}")

        other_doc = None
        try:
            other_doc = fitz.open(other_filepath)
            # Insert all pages from the other document
            doc.insert_pdf(other_doc, from_page=0, to_page=len(other_doc) - 1, start_at=start_at)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to merge PDF document: {str(e)}")
        finally:
            if other_doc:
                other_doc.close()

    @staticmethod
    def _extract_typographic_styles(block: Dict[str, Any]) -> Tuple[float, str, Tuple[float, float, float]]:
        """
        Extract font size, font family name, and RGB text color from original spans.
        
        Args:
            block (Dict[str, Any]): Fitz block structure.

        Returns:
            Tuple[float, str, Tuple[float, float, float]]: (fontsize, fontname, rgb_color)
        """
        # Sensible defaults
        default_size = 11.0
        default_font = "helv"  # Standard Helvetica
        default_color = (0.0, 0.0, 0.0)  # Black

        # Dig into lines and spans to find styling
        lines = block.get("lines", [])
        if not lines:
            return default_size, default_font, default_color

        first_line = lines[0]
        spans = first_line.get("spans", [])
        if not spans:
            return default_size, default_font, default_color

        first_span = spans[0]
        
        # 1. Extract Font Size
        size = first_span.get("size", default_size)

        # 2. Extract Font Name & Map to safe Standard MuPDF fonts
        # MuPDF includes standard: "helv" (Helvetica), "times" (Times), "cour" (Courier)
        raw_font = str(first_span.get("font", "")).lower()
        font_name = default_font
        if "times" in raw_font or "roman" in raw_font:
            font_name = "times"
        elif "courier" in raw_font or "mono" in raw_font:
            font_name = "cour"
        else:
            # Default to helv, check for bold/italic weight variations
            if "bold" in raw_font and "italic" in raw_font:
                font_name = "hebi"
            elif "bold" in raw_font:
                font_name = "hebo"
            elif "italic" in raw_font:
                font_name = "helt"

        # 3. Extract sRGB color and translate to float RGB (0.0 - 1.0)
        srgb = first_span.get("color", 0)
        # fitz sRGB is standard 24-bit int (0xRRGGBB). Map to float RGB
        try:
            rgb_color = fitz.sRGB_to_rgb(srgb)
        except Exception:
            rgb_color = default_color

        return size, font_name, rgb_color

    @staticmethod
    def _merge_text_style(
        font_size: float,
        font_name: str,
        text_color: Tuple[float, float, float],
        text_style: Optional[Dict[str, Any]]
    ) -> Tuple[float, str, Tuple[float, float, float]]:
        """Apply user-selected text styling over extracted/default values."""
        if not text_style:
            return font_size, font_name, text_color

        size = float(text_style.get("font_size", font_size))
        color = text_style.get("color", text_color)
        bold = bool(text_style.get("bold", False))
        italic = bool(text_style.get("italic", False))

        if bold and italic:
            font = "hebi"
        elif bold:
            font = "hebo"
        elif italic:
            font = "heit"
        else:
            font = font_name

        return size, font, color

    @staticmethod
    def _has_hangul(text: str) -> bool:
        """
        Check if the input string contains any Hangul (Korean) characters.

        Args:
            text (str): The target string to inspect.

        Returns:
            bool: True if Hangul is detected, False otherwise.
        """
        if not text:
            return False
        for char in text:
            code = ord(char)
            # AC00-D7A3: Hangul Syllables
            # 3130-318F: Hangul Compatibility Jamo
            # 1100-11FF: Hangul Jamo (NFD - Unicode 초성, 중성, 종성 분리형 자모)
            if (0xAC00 <= code <= 0xD7A3) or (0x3130 <= code <= 0x318F) or (0x1100 <= code <= 0x11FF):
                return True
        return False


    @staticmethod
    def add_text_annotation(
        doc: fitz.Document,
        page_index: int,
        rects: list[fitz.Rect],
        annot_type: str,
        color: tuple[float, float, float],
        opacity: float = 1.0
    ) -> bool:
        """
        PDF 페이지의 특정 영역들에 텍스트 주석(형광펜, 밑줄, 취소선)을 추가합니다.

        Args:
            doc (fitz.Document): 수정할 fitz Document 인스턴스.
            page_index (int): 0-indexed 대상 페이지 번호.
            rects (list[fitz.Rect]): 주석을 추가할 Rect 영역 리스트.
            annot_type (str): 주석 유형 ("highlight", "underline", "strikeout" 중 하나).
            color (tuple[float, float, float]): RGB 색상값 (각 요소는 0.0 ~ 1.0 사이의 float).
            opacity (float): 불투명도 (0.0 ~ 1.0, 기본값 1.0).

        Returns:
            bool: 주석 추가 성공 시 True, 실패 시 False.

        Raises:
            ValueError: 잘못된 문서 인스턴스이거나 페이지 범위를 벗어날 경우.
        """
        if not doc or page_index < 0 or page_index >= len(doc):
            raise ValueError("유효하지 않은 문서이거나 페이지 번호입니다.")

        try:
            page = doc.load_page(page_index)
            
            for rect in rects:
                annot = None
                if annot_type == "highlight":
                    annot = page.add_highlight_annot(rect)
                elif annot_type == "underline":
                    annot = page.add_underline_annot(rect)
                elif annot_type == "strikeout":
                    annot = page.add_strikeout_annot(rect)
                
                if annot:
                    # fitz 주석 색상 및 투명도 설정
                    annot.set_colors(stroke=color)
                    annot.set_opacity(opacity)
                    annot.update()
            
            return True
        except Exception as e:
            raise RuntimeError(f"텍스트 주석 추가 실패: {str(e)}")

    @staticmethod
    def add_ink_annotation(
        doc: fitz.Document,
        page_index: int,
        lines: list[list[tuple[float, float]]],
        color: tuple[float, float, float],
        width: float = 2.0,
        opacity: float = 1.0
    ) -> bool:
        """
        PDF 페이지에 마우스로 그린 자유 곡선(Ink) 주석을 추가합니다.

        Args:
            doc (fitz.Document): 수정할 fitz Document 인스턴스.
            page_index (int): 0-indexed 대상 페이지 번호.
            lines (list[list[tuple[float, float]]]): 선들의 리스트. 각 선은 (x, y) 좌표 튜플의 리스트.
            color (tuple[float, float, float]): RGB 색상값 (0.0 ~ 1.0).
            width (float): 선 두께 (기본값 2.0).
            opacity (float): 불투명도 (0.0 ~ 1.0, 기본값 1.0).

        Returns:
            bool: 주석 추가 성공 시 True, 실패 시 False.

        Raises:
            ValueError: 잘못된 문서 인스턴스이거나 페이지 범위를 벗어날 경우.
        """
        if not doc or page_index < 0 or page_index >= len(doc):
            raise ValueError("유효하지 않은 문서이거나 페이지 번호입니다.")

        if not lines:
            return False

        try:
            page = doc.load_page(page_index)
            
            # fitz.open().add_ink_annot는 list_of_points를 인자로 받음
            # list_of_points는 Point 객체들 또는 (x, y) 튜플들의 리스트의 리스트 형태여야 함
            annot = page.add_ink_annot(lines)
            if annot:
                annot.set_colors(stroke=color)
                annot.set_border(width=width)
                annot.set_opacity(opacity)
                annot.update()
                return True
            return False
        except Exception as e:
            raise RuntimeError(f"Ink 주석 추가 실패: {str(e)}")
