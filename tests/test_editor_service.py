"""
Unit Tests for PdfEditorService.

This module tests that PdfEditorService successfully locates text blocks,
performs redaction to erase old text, overlays the new text, and saves
the document changes accurately.
"""

import os
import tempfile
from typing import Generator
import pytest
import fitz

from models.pdf_document import PdfDocument
from services.pdf_editor_service import PdfEditorService
from services.export_service import ExportService


@pytest.fixture
def sample_pdf_with_text() -> Generator[str, None, None]:
    """
    Fixture that creates a temporary PDF with explicit text blocks for editing tests.

    Yields:
        str: Absolute filepath of the created PDF.
    """
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, "aether_edit_test.pdf")

    # Create PDF with a distinct text block
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    
    # Insert text block at a predictable rect
    page.insert_textbox(
        fitz.Rect(100, 100, 400, 150),
        "Original Aether Text",
        fontsize=12,
        fontname="helv",
        color=(0, 0, 0)
    )
    doc.save(pdf_path, garbage=3)
    doc.close()

    yield pdf_path

    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass


def test_replace_block_text_success(sample_pdf_with_text: str) -> None:
    """Ensure replacing text within a block succeeds and saves correctly."""
    # 1. Open the PDF with PdfDocument model
    pdf = PdfDocument()
    pdf.open(sample_pdf_with_text)
    
    # 2. Extract block structures
    blocks = pdf.get_text_blocks(0)
    assert len(blocks) > 0
    
    # Find our text block
    target_block = None
    for block in blocks:
        if block.get("type") == 0:  # Text block
            target_block = block
            break
            
    assert target_block is not None, "Target text block not found."

    # 3. Call the PdfEditorService to swap text
    raw_doc = pdf.get_raw_document()
    assert raw_doc is not None
    
    new_text = "Edited Premium Text!"
    success = PdfEditorService.replace_block_text(raw_doc, 0, target_block, new_text)
    assert success is True

    # 4. Save modifications to a new temp file
    temp_dir = tempfile.gettempdir()
    save_path = os.path.join(temp_dir, "aether_edit_result.pdf")
    
    # Standard save
    raw_doc.save(save_path)
    pdf.close()

    # 5. Re-open saved PDF and verify text was successfully changed
    verify_pdf = PdfDocument()
    verify_pdf.open(save_path)
    
    new_blocks = verify_pdf.get_text_blocks(0)
    text_found = False
    old_text_erased = True

    for block in new_blocks:
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if new_text in span_text:
                        text_found = True
                    if "Original Aether Text" in span_text:
                        old_text_erased = False

    verify_pdf.close()
    
    # Clean up save file
    if os.path.exists(save_path):
        os.remove(save_path)

    # Assetions
    assert text_found, "The replacement text was not found in the saved PDF."
    assert old_text_erased, "The original text was not erased properly by redaction."


def test_add_free_text_success() -> None:
    """Ensure adding text at an empty page location succeeds."""
    doc = fitz.open()
    doc.new_page(width=500, height=500)

    success = PdfEditorService.add_free_text(
        doc,
        0,
        (100.0, 100.0),
        "New Empty Space Text",
        {
            "color": (1.0, 0.0, 0.0),
            "font_size": 16.0,
            "bold": True,
            "italic": False,
        },
    )

    assert success is True
    assert "New Empty Space Text" in doc[0].get_text()
    doc.close()


def test_replace_block_text_korean_success(sample_pdf_with_text: str) -> None:
    """Ensure replacing text with Korean characters embeds the CJK font and works."""
    pdf = PdfDocument()
    pdf.open(sample_pdf_with_text)
    
    blocks = pdf.get_text_blocks(0)
    assert len(blocks) > 0
    
    target_block = None
    for block in blocks:
        if block.get("type") == 0:
            target_block = block
            break
            
    assert target_block is not None
    
    raw_doc = pdf.get_raw_document()
    assert raw_doc is not None
    
    new_text = "안녕하세요 피디에프!"
    success = PdfEditorService.replace_block_text(raw_doc, 0, target_block, new_text)
    assert success is True
    
    temp_dir = tempfile.gettempdir()
    save_path = os.path.join(temp_dir, "aether_edit_result_ko.pdf")
    raw_doc.save(save_path)
    pdf.close()
    
    # Verify the saved Korean text is extracted perfectly
    verify_pdf = PdfDocument()
    verify_pdf.open(save_path)
    
    new_blocks = verify_pdf.get_text_blocks(0)
    text_found = False
    
    for block in new_blocks:
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if new_text in span_text:
                        text_found = True
                        
    verify_pdf.close()
    if os.path.exists(save_path):
        os.remove(save_path)
        
    assert text_found, "The replacement Korean text was not found or corrupted in the saved PDF."


def test_replace_block_invalid_arguments() -> None:
    """Ensure invalid args raise correct exceptions."""
    doc = fitz.open()
    
    # Invalid document
    with pytest.raises(ValueError):
        PdfEditorService.replace_block_text(None, 0, {}, "text")
        
    # Invalid page index
    with pytest.raises(ValueError):
        PdfEditorService.replace_block_text(doc, 999, {}, "text")
        
    # Invalid block bounding box
    with pytest.raises(ValueError):
        PdfEditorService.replace_block_text(doc, 0, {"bbox": [100]}, "text")

    doc.close()


def test_reorder_pages_success() -> None:
    """Validate page reordering using PyMuPDF's select API."""
    doc = fitz.open()
    # Create 3 pages with distinct sizes to identify them
    doc.new_page(width=100, height=100)  # Page 0
    doc.new_page(width=200, height=200)  # Page 1
    doc.new_page(width=300, height=300)  # Page 2
    
    assert len(doc) == 3
    assert doc[0].rect.width == 100

    # Reorder [2, 0, 1]
    success = PdfEditorService.reorder_pages(doc, [2, 0, 1])
    assert success is True
    assert len(doc) == 3
    
    # New Page 0 should be the old Page 2 (width 300)
    assert doc[0].rect.width == 300
    # New Page 1 should be the old Page 0 (width 100)
    assert doc[1].rect.width == 100
    # New Page 2 should be the old Page 1 (width 200)
    assert doc[2].rect.width == 200
    
    doc.close()


def test_rotate_page_success() -> None:
    """Validate page rotation by 90-degree increments."""
    doc = fitz.open()
    page = doc.new_page()
    assert page.rotation == 0

    # Rotate 90 deg clockwise
    success = PdfEditorService.rotate_page(doc, 0, 90)
    assert success is True
    assert doc[0].rotation == 90

    # Rotate another 180 deg
    PdfEditorService.rotate_page(doc, 0, 180)
    assert doc[0].rotation == 270

    # Rotate past 360 deg
    PdfEditorService.rotate_page(doc, 0, 90)
    assert doc[0].rotation == 0

    doc.close()


def test_delete_page_success() -> None:
    """Ensure pages are deleted successfully, decreasing total count."""
    doc = fitz.open()
    doc.new_page(width=100, height=100)  # Page 0
    doc.new_page(width=200, height=200)  # Page 1
    assert len(doc) == 2

    # Delete first page
    success = PdfEditorService.delete_page(doc, 0)
    assert success is True
    assert len(doc) == 1
    # Remaining page should be old Page 1 (width 200)
    assert doc[0].rect.width == 200

    doc.close()


def test_insert_blank_page_success() -> None:
    """Validate insertion of a new blank page at different indices."""
    doc = fitz.open()
    doc.new_page(width=100, height=100)
    assert len(doc) == 1

    # Prepend new page (index 0)
    success = PdfEditorService.insert_blank_page(doc, 0, width=500, height=500)
    assert success is True
    assert len(doc) == 2
    assert doc[0].rect.width == 500
    assert doc[1].rect.width == 100

    # Append at end
    PdfEditorService.insert_blank_page(doc, 2, width=300, height=300)
    assert len(doc) == 3
    assert doc[2].rect.width == 300

    doc.close()


def test_merge_pdf_success() -> None:
    """Validate merging pages from an external PDF into our active document."""
    # Create external PDF
    temp_dir = tempfile.gettempdir()
    external_path = os.path.join(temp_dir, "aether_external_merge.pdf")
    
    ext_doc = fitz.open()
    ext_doc.new_page(width=444, height=444)
    ext_doc.save(external_path)
    ext_doc.close()

    # Active PDF
    active_doc = fitz.open()
    active_doc.new_page(width=111, height=111)
    
    assert len(active_doc) == 1

    try:
        # Merge external PDF at the end
        success = PdfEditorService.merge_pdf(active_doc, external_path, 1)
        assert success is True
        assert len(active_doc) == 2
        assert active_doc[0].rect.width == 111
        assert active_doc[1].rect.width == 444
    finally:
        active_doc.close()
        if os.path.exists(external_path):
            os.remove(external_path)


def test_add_text_annotation_success() -> None:
    """텍스트 주석(형광펜, 밑줄, 취소선) 추가가 성공적으로 수행되는지 검증합니다."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    
    # 텍스트 주석을 적용할 가상의 Rect 영역 지정
    target_rect = fitz.Rect(100, 100, 200, 120)
    
    # 1. 형광펜 주석 추가 (노란색, 불투명도 0.5)
    color_yellow = (1.0, 1.0, 0.0)
    success = PdfEditorService.add_text_annotation(
        doc, 0, [target_rect], "highlight", color_yellow, opacity=0.5
    )
    assert success is True

    # 2. 밑줄 주석 추가 (빨간색, 불투명도 1.0)
    color_red = (1.0, 0.0, 0.0)
    success = PdfEditorService.add_text_annotation(
        doc, 0, [target_rect], "underline", color_red, opacity=1.0
    )
    assert success is True

    # 3. 취소선 주석 추가 (파란색, 불투명도 0.8)
    color_blue = (0.0, 0.0, 1.0)
    success = PdfEditorService.add_text_annotation(
        doc, 0, [target_rect], "strikeout", color_blue, opacity=0.8
    )
    assert success is True

    # 주석들이 실제 페이지에 추가되었는지 검증
    annots = list(page.annots())
    assert len(annots) == 3

    # 각 주석의 종류와 속성 검증
    # fitz에서 주석 타입은 정수형 상수로 표현됨 (Highlight: 8, Underline: 9, StrikeOut: 11)
    types = [annot.type[0] for annot in annots]
    assert 8 in types  # Highlight
    assert 9 in types  # Underline
    assert 11 in types  # StrikeOut

    # 첫 번째 주석(Highlight) 속성 검증
    highlight_annot = next(a for a in annots if a.type[0] == 8)
    assert highlight_annot.colors["stroke"] == list(color_yellow)
    assert highlight_annot.opacity == pytest.approx(0.5)

    doc.close()


def test_add_ink_annotation_success() -> None:
    """잉크 주석(자유 그리기) 추가가 성공적으로 수행되는지 검증합니다."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)

    # 잉크 좌표선 리스트 생성 (V자 형태의 그리기)
    line1 = [(100.0, 100.0), (150.0, 200.0), (200.0, 100.0)]
    lines = [line1]

    # 초록색, 두께 3.0, 투명도 0.9의 잉크 주석 추가
    color_green = (0.0, 1.0, 0.0)
    success = PdfEditorService.add_ink_annotation(
        doc, 0, lines, color_green, width=3.0, opacity=0.9
    )
    assert success is True

    # 주석 검증
    annots = list(page.annots())
    assert len(annots) == 1
    
    ink_annot = annots[0]
    assert ink_annot.type[0] == 15  # Ink 주석 타입 상수는 15
    assert ink_annot.colors["stroke"] == list(color_green)
    assert ink_annot.opacity == pytest.approx(0.9)

    doc.close()


def test_add_annotation_invalid_arguments() -> None:
    """주석 추가 시 잘못된 인자가 전달되었을 때 예외 처리가 작동하는지 검증합니다."""
    doc = fitz.open()
    doc.new_page(width=500, height=500)

    # 1. 문서 인스턴스가 없을 때
    with pytest.raises(ValueError):
        PdfEditorService.add_text_annotation(None, 0, [fitz.Rect(0, 0, 10, 10)], "highlight", (1.0, 1.0, 0.0))

    with pytest.raises(ValueError):
        PdfEditorService.add_ink_annotation(None, 0, [[(0.0, 0.0)]], (1.0, 1.0, 0.0))

    # 2. 페이지 범위를 벗어날 때
    with pytest.raises(ValueError):
        PdfEditorService.add_text_annotation(doc, 999, [fitz.Rect(0, 0, 10, 10)], "highlight", (1.0, 1.0, 0.0))

    with pytest.raises(ValueError):
        PdfEditorService.add_ink_annotation(doc, 999, [[(0.0, 0.0)]], (1.0, 1.0, 0.0))

    doc.close()


def test_save_incremental_success(sample_pdf_with_text: str) -> None:
    """점진적 저장이 정상적으로 성공하고 파일에 반영되는지 검증합니다."""
    # 1. 파일 경로를 가진 PDF 문서 열기
    doc = fitz.open(sample_pdf_with_text)
    page = doc[0]
    
    # 2. 주석 하나 추가하여 수정사항 발생시킴
    page.add_highlight_annot(fitz.Rect(10, 10, 50, 30))
    
    # 3. 점진적 저장 수행
    success = ExportService.save_incremental(doc)
    assert success is True
    doc.close()

    # 4. 저장된 PDF 다시 열어서 주석이 정상 저장되었는지 확인
    verify_doc = fitz.open(sample_pdf_with_text)
    verify_page = verify_doc[0]
    annots = list(verify_page.annots())
    assert len(annots) == 1
    verify_doc.close()


def test_save_as_success(sample_pdf_with_text: str) -> None:
    """다른 이름으로 저장(최적화 옵션 포함)이 정상적으로 성공하는지 검증합니다."""
    doc = fitz.open(sample_pdf_with_text)
    
    # 임시 파일 경로 생성
    temp_dir = tempfile.gettempdir()
    save_path_optimized = os.path.join(temp_dir, "aether_save_as_opt.pdf")
    save_path_normal = os.path.join(temp_dir, "aether_save_as_norm.pdf")

    try:
        # 1. 최적화 저장 검증
        success_opt = ExportService.save_as(doc, save_path_optimized, optimize=True)
        assert success_opt is True
        assert os.path.exists(save_path_optimized)

        # 2. 일반 저장 검증
        success_norm = ExportService.save_as(doc, save_path_normal, optimize=False)
        assert success_norm is True
        assert os.path.exists(save_path_normal)

        # 3. 저장된 파일들이 정상적으로 열리는지 확인
        verify_opt = fitz.open(save_path_optimized)
        assert len(verify_opt) == 1
        verify_opt.close()

        verify_norm = fitz.open(save_path_normal)
        assert len(verify_norm) == 1
        verify_norm.close()

    finally:
        doc.close()
        if os.path.exists(save_path_optimized):
            os.remove(save_path_optimized)
        if os.path.exists(save_path_normal):
            os.remove(save_path_normal)


def test_export_invalid_arguments() -> None:
    """저장 서비스 호출 시 잘못된 인자가 들어왔을 때 예외 처리가 작동하는지 검증합니다."""
    doc = fitz.open()

    # 1. doc가 null일 때
    with pytest.raises(ValueError):
        ExportService.save_incremental(None)

    with pytest.raises(ValueError):
        ExportService.save_as(None, "dummy_path.pdf")

    # 2. save_incremental 호출 시 파일과 바인딩되지 않은 문서일 때
    with pytest.raises(ValueError):
        ExportService.save_incremental(doc)

    # 3. save_as 호출 시 저장 경로가 비어 있을 때
    with pytest.raises(ValueError):
        ExportService.save_as(doc, "")

    doc.close()


def test_has_hangul() -> None:
    """Ensure _has_hangul correctly identifies Korean characters and ignores others."""
    # 한글이 포함된 경우
    assert PdfEditorService._has_hangul("안녕하세요") is True
    assert PdfEditorService._has_hangul("AetherPDF 한글 편집") is True
    assert PdfEditorService._has_hangul("ㄱㄴㄷㄹ") is True  # 호환 자모 영역
    assert PdfEditorService._has_hangul("뷁") is True       # 복잡한 완성형 한글

    # 한글이 포함되지 않은 경우
    assert PdfEditorService._has_hangul("AetherPDF") is False
    assert PdfEditorService._has_hangul("12345!@#$%") is False
    assert PdfEditorService._has_hangul("") is False
    assert PdfEditorService._has_hangul(None) is False



