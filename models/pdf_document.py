"""
PDF Document Model for AetherPDF.

This module encapsulates the PyMuPDF (fitz) integration, handling document
opening, page metadata extraction, high-resolution rendering, and structural
analysis of text blocks for editing.
"""

from typing import List, Dict, Any, Tuple, Optional
import os
import fitz  # PyMuPDF
from PySide6.QtGui import QImage, QPixmap

from config.settings import DEFAULT_DPI


class PdfDocument:
    """
    Model representing a loaded PDF document.
    
    Responsible for low-level PDF operations via PyMuPDF (fitz) and translating
    them into Qt-compatible structures (like QImage).
    """

    def __init__(self) -> None:
        """Initialize an empty PDF Document."""
        self._doc: Optional[fitz.Document] = None
        self._filepath: str = ""
        self._page_count: int = 0
        self._metadata: Dict[str, Any] = {}

    @property
    def is_loaded(self) -> bool:
        """
        Check if a document is currently loaded.
        
        Returns:
            bool: True if loaded, False otherwise.
        """
        return self._doc is not None

    @property
    def filepath(self) -> str:
        """
        Get the filepath of the loaded document.
        
        Returns:
            str: File path string.
        """
        return self._filepath

    @property
    def page_count(self) -> int:
        """
        Get the total page count.
        
        Returns:
            int: Number of pages.
        """
        return self._page_count

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Get the document metadata dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary containing author, title, creator, etc.
        """
        return self._metadata

    def open(self, filepath: str) -> bool:
        """
        Open a PDF document.

        Args:
            filepath (str): Absolute file path to the PDF.

        Returns:
            bool: True if loaded successfully, False otherwise.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid PDF.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF file not found at: {filepath}")

        try:
            # Open document with PyMuPDF
            self._doc = fitz.open(filepath)
            self._filepath = filepath
            self._page_count = len(self._doc)
            self._metadata = self._doc.metadata
            return True
        except Exception as e:
            # Ensure cleanup on failure
            self.close()
            raise ValueError(f"Failed to parse PDF document: {str(e)}")

    def close(self) -> None:
        """Close the active PDF document and release resources."""
        if self._doc:
            self._doc.close()
        self._doc = None
        self._filepath = ""
        self._page_count = 0
        self._metadata = {}

    def render_page(self, page_index: int, dpi: int = DEFAULT_DPI) -> QImage:
        """
        Render a PDF page to a QImage.

        Args:
            page_index (int): 0-indexed page number.
            dpi (int): Rendering resolution in Dots Per Inch.

        Returns:
            QImage: Rendered page image.

        Raises:
            ValueError: If document is not loaded or page_index is out of range.
        """
        if not self.is_loaded or not self._doc:
            raise ValueError("No PDF document is currently loaded.")

        if page_index < 0 or page_index >= self._page_count:
            raise ValueError(f"Page index {page_index} out of range [0, {self._page_count - 1}].")

        try:
            page = self._doc.load_page(page_index)
            # Calculate zoom factor from DPI (default screen resolution is 72 DPI)
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            
            # Render page to a high-resolution pixmap
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            
            # Convert fitz Pixmap to QImage
            # Format is RGB888. The pointer must be held properly, so we copy the data.
            image = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format_RGB888
            ).copy()  # copy() is critical to avoid referencing freed C-memory
            
            return image
        except Exception as e:
            raise RuntimeError(f"Failed to render page {page_index}: {str(e)}")

    def get_text_blocks(self, page_index: int) -> List[Dict[str, Any]]:
        """
        Retrieve structured text blocks of a specific page.

        Each block contains coordinates (x0, y0, x1, y1), lines, spans, etc.
        Used for body text detection and target alignment.

        Args:
            page_index (int): 0-indexed page number.

        Returns:
            List[Dict[str, Any]]: List of dictionary structures representing blocks.
        """
        if not self.is_loaded or not self._doc:
            return []

        if page_index < 0 or page_index >= self._page_count:
            return []

        try:
            page = self._doc.load_page(page_index)
            # get_text("dict") returns blocks, lines, spans with detailed coordinates and text
            text_dict = page.get_text("dict")
            return text_dict.get("blocks", [])
        except Exception:
            return []

    def get_raw_document(self) -> Optional[fitz.Document]:
        """
        Retrieve the raw PyMuPDF Document instance.
        
        This is useful for low-level modification operations.

        Returns:
            Optional[fitz.Document]: Fitz Document object or None.
        """
        return self._doc
