"""
Unit tests for PdfDocument Model.

This module validates that the PdfDocument model correctly opens a PDF,
reports metadata, retrieves structured text blocks, and renders pages to QImages.
It leverages PyMuPDF to generate a dynamic temporary PDF for testing.
"""

import os
import tempfile
from typing import Generator
import pytest
import fitz
from PySide6.QtGui import QImage

from models.pdf_document import PdfDocument


@pytest.fixture
def sample_pdf_path() -> Generator[str, None, None]:
    """
    Fixture that creates a temporary 1-page PDF for test validation.

    Yields:
        str: Absolute filepath of the created PDF.
    """
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, "aether_test_sample.pdf")

    # Create a simple PDF using PyMuPDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 Size at 72 points/inch
    page.insert_textbox(
        fitz.Rect(50, 50, 300, 100),
        "Hello AetherPDF!",
        fontsize=12,
        fontname="helv"
    )
    doc.save(pdf_path)
    doc.close()

    yield pdf_path

    # Clean up the file after the test finishes
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass


def test_pdf_document_opening_and_closing(sample_pdf_path: str) -> None:
    """Validate loading, properties, and closing operations of PdfDocument."""
    pdf = PdfDocument()
    assert not pdf.is_loaded
    assert pdf.page_count == 0
    assert pdf.filepath == ""

    # Open valid file
    success = pdf.open(sample_pdf_path)
    assert success
    assert pdf.is_loaded
    assert pdf.page_count == 1
    assert pdf.filepath == sample_pdf_path
    assert isinstance(pdf.metadata, dict)
    
    # Close file
    pdf.close()
    assert not pdf.is_loaded
    assert pdf.page_count == 0
    assert pdf.filepath == ""


def test_pdf_document_invalid_path() -> None:
    """Ensure opening a non-existent file raises FileNotFoundError."""
    pdf = PdfDocument()
    with pytest.raises(FileNotFoundError):
        pdf.open("non_existent_file_path_12345.pdf")


def test_pdf_document_invalid_format() -> None:
    """Ensure opening a corrupted or invalid file raises ValueError."""
    pdf = PdfDocument()
    # Create an invalid text file but with .pdf extension
    temp_dir = tempfile.gettempdir()
    bad_pdf_path = os.path.join(temp_dir, "corrupted_file.pdf")
    with open(bad_pdf_path, "w", encoding="utf-8") as f:
        f.write("This is not a PDF file.")

    try:
        with pytest.raises(ValueError):
            pdf.open(bad_pdf_path)
    finally:
        if os.path.exists(bad_pdf_path):
            os.remove(bad_pdf_path)


def test_pdf_document_rendering(sample_pdf_path: str) -> None:
    """Validate that PDF pages are rendered successfully to QImage."""
    pdf = PdfDocument()
    pdf.open(sample_pdf_path)

    # Render first page at default resolution
    q_img = pdf.render_page(0, dpi=72)
    assert isinstance(q_img, QImage)
    assert not q_img.isNull()
    # A4 is 595x842 at 72 DPI
    assert q_img.width() == 595
    assert q_img.height() == 842

    # Attempting to render non-existent page should raise ValueError
    with pytest.raises(ValueError):
        pdf.render_page(99, dpi=72)

    # Attempting to render negative page index should raise ValueError
    with pytest.raises(ValueError):
        pdf.render_page(-1, dpi=72)

    pdf.close()


def test_pdf_text_block_extraction(sample_pdf_path: str) -> None:
    """Ensure we can extract structural text blocks from the PDF document."""
    pdf = PdfDocument()
    pdf.open(sample_pdf_path)

    blocks = pdf.get_text_blocks(0)
    assert isinstance(blocks, list)
    assert len(blocks) > 0

    # The block should contain our text "Hello AetherPDF!"
    text_found = False
    for block in blocks:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    if "Hello AetherPDF!" in span["text"]:
                        text_found = True
                        break

    assert text_found, "The expected text 'Hello AetherPDF!' was not found in extracted blocks."
    pdf.close()
