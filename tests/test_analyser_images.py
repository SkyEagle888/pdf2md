"""Tests for pdf2md analyser and images modules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pdf2md.analyser import (
    PageMode,
    TextBlock,
    PageAnalysis,
    DocumentAnalysis,
    _count_text_chars,
    _detect_font_flags,
    _extract_text_blocks,
    analyze_pdf,
)
from pdf2md.images import (
    ExtractedImage,
    _convert_to_png,
    _get_image_y0,
    extract_images,
)


# ---------------------------------------------------------------------------
# analyser.py unit tests
# ---------------------------------------------------------------------------


class TestPageMode:
    def test_text_mode_value(self):
        assert PageMode.TEXT.value == "text"

    def test_scan_mode_value(self):
        assert PageMode.SCAN.value == "scan"


class TestTextBlock:
    def test_text_block_creation(self):
        block = TextBlock(
            text="Hello World",
            x0=10.0,
            y0=20.0,
            x1=100.0,
            y1=30.0,
            font_size=12.0,
            font_name="Helvetica",
        )
        assert block.text == "Hello World"
        assert block.font_size == 12.0
        assert block.is_bold is False
        assert block.is_italic is False

    def test_text_block_bold_italic(self):
        block = TextBlock(
            text="Bold Italic",
            x0=0,
            y0=0,
            x1=0,
            y1=0,
            font_size=14.0,
            font_name="Times-BoldItalic",
            is_bold=True,
            is_italic=True,
        )
        assert block.is_bold is True
        assert block.is_italic is True


class TestPageAnalysis:
    def test_page_analysis_defaults(self):
        analysis = PageAnalysis(page_number=1, mode=PageMode.TEXT)
        assert analysis.text_blocks == []
        assert analysis.pixmap is None
        assert analysis.has_images is False

    def test_page_analysis_with_data(self):
        block = TextBlock(
            text="Test", x0=0, y0=0, x1=0, y1=0, font_size=12, font_name=""
        )
        analysis = PageAnalysis(
            page_number=2,
            mode=PageMode.SCAN,
            text_blocks=[block],
            has_images=True,
        )
        assert analysis.page_number == 2
        assert analysis.mode == PageMode.SCAN
        assert len(analysis.text_blocks) == 1
        assert analysis.has_images is True


class TestDocumentAnalysis:
    def test_document_analysis(self):
        pages = [
            PageAnalysis(page_number=1, mode=PageMode.TEXT),
            PageAnalysis(page_number=2, mode=PageMode.SCAN),
        ]
        doc = DocumentAnalysis(
            total_pages=2,
            pages=pages,
            file_size_bytes=1024,
            file_path="/test/doc.pdf",
        )
        assert doc.total_pages == 2
        assert len(doc.pages) == 2
        assert doc.file_size_bytes == 1024


class TestDetectFontFlags:
    def test_normal_font(self):
        assert _detect_font_flags("Helvetica", 0) == (False, False)

    def test_bold_in_name(self):
        assert _detect_font_flags("Helvetica-Bold", 0) == (True, False)

    def test_italic_in_name(self):
        # "Oblique" is not matched by our simple "Italic" check
        assert _detect_font_flags("Helvetica-Oblique", 0) == (False, False)

    def test_italic_explicit_in_name(self):
        assert _detect_font_flags("Helvetica-Italic", 0) == (False, True)

    def test_bold_flag(self):
        # bit 4 = bold
        assert _detect_font_flags("Helvetica", 1 << 4) == (True, False)

    def test_italic_flag(self):
        # bit 1 = italic
        assert _detect_font_flags("Helvetica", 1 << 1) == (False, True)

    def test_bold_and_italic(self):
        flags = (1 << 4) | (1 << 1)
        assert _detect_font_flags("Helvetica", flags) == (True, True)


class TestCountTextChars:
    def test_empty_dict(self):
        assert _count_text_chars({}) == 0

    def test_no_text_blocks(self):
        page_dict = {"blocks": [{"type": 1}]}  # image block
        assert _count_text_chars(page_dict) == 0

    def test_counts_chars_correctly(self):
        page_dict = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {"text": "Hello World"}
                            ]
                        }
                    ],
                }
            ]
        }
        # "Hello World".strip() == "Hello World" = 11 chars
        assert _count_text_chars(page_dict) == 11

    def test_multiple_spans(self):
        page_dict = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {"text": "Hello "},
                                {"text": "World"},
                            ]
                        }
                    ],
                }
            ]
        }
        # "Hello ".strip() = "Hello" (5) + "World".strip() = "World" (5) = 10
        assert _count_text_chars(page_dict) == 10


class TestExtractTextBlocks:
    def test_empty_dict(self):
        assert _extract_text_blocks({}) == []

    def test_image_block_skipped(self):
        page_dict = {"blocks": [{"type": 1}]}
        assert _extract_text_blocks(page_dict) == []

    def test_extracts_single_line(self):
        page_dict = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "bbox": [10, 20, 100, 30],
                            "spans": [
                                {
                                    "text": "Hello World",
                                    "size": 12.0,
                                    "font": "Helvetica",
                                    "flags": 0,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        blocks = _extract_text_blocks(page_dict)
        assert len(blocks) == 1
        assert blocks[0].text == "Hello World"
        assert blocks[0].font_size == 12.0
        assert blocks[0].font_name == "Helvetica"
        assert blocks[0].y0 == 20.0

    def test_empty_lines_skipped(self):
        page_dict = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "bbox": [0, 0, 0, 0],
                            "spans": [{"text": "   ", "size": 12, "font": "", "flags": 0}],
                        }
                    ],
                }
            ]
        }
        assert _extract_text_blocks(page_dict) == []


class TestAnalyzePdf:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            analyze_pdf("/nonexistent/path/file.pdf")

    def test_not_a_pdf_extension(self, tmp_path: Path):
        fake_pdf = tmp_path / "test.txt"
        fake_pdf.write_bytes(b"not a pdf")
        with pytest.raises(ValueError, match="not a PDF"):
            analyze_pdf(str(fake_pdf))

    def test_invalid_pdf_content(self, tmp_path: Path):
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"this is not a valid pdf content at all 12345")
        # fitz raises an error for invalid PDF content
        with pytest.raises(ValueError, match="Cannot open PDF"):
            analyze_pdf(str(fake_pdf))

    def test_empty_pdf(self, tmp_path: Path):
        # Create a minimal valid PDF
        pdf_content = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
            b"trailer<</Root 1 0 R/Size 3>>\n%%EOF"
        )
        fake_pdf = tmp_path / "empty.pdf"
        fake_pdf.write_bytes(pdf_content)
        result = analyze_pdf(str(fake_pdf))
        assert result.total_pages == 0
        assert result.pages == []


# ---------------------------------------------------------------------------
# images.py unit tests
# ---------------------------------------------------------------------------


class TestExtractedImage:
    def test_extracted_image_creation(self):
        img = ExtractedImage(
            page_number=1,
            image_index=2,
            filename="page1_img2.png",
            width=200,
            height=150,
            y0=100.0,
            data=b"\x89PNG\r\n\x1a\n",
        )
        assert img.filename == "page1_img2.png"
        assert img.width == 200
        assert img.height == 150
        assert img.y0 == 100.0


class TestGetImageY0:
    def test_rects_available(self):
        mock_rect = MagicMock()
        mock_rect.y0 = 42.0
        mock_page = MagicMock()
        mock_page.get_image_rects.return_value = [mock_rect]
        result = _get_image_y0(mock_page, 1, 100)
        assert result == 42.0

    def test_rects_empty_uses_default(self):
        mock_page = MagicMock()
        mock_page.get_image_rects.return_value = []
        result = _get_image_y0(mock_page, 1, 999)
        assert result == 999.0

    def test_rects_exception_uses_default(self):
        mock_page = MagicMock()
        mock_page.get_image_rects.side_effect = Exception("fail")
        result = _get_image_y0(mock_page, 1, 50)
        assert result == 50.0


class TestConvertToPng:
    def test_returns_original_on_failure(self):
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.side_effect = Exception("fail")
        mock_pixmap.n = 3
        data = b"fake image data"
        result = _convert_to_png(mock_pixmap, data, "jpg")
        # Falls through to PIL, then to original bytes
        assert result == data


class TestExtractImages:
    def test_empty_document(self):
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 0
        result = extract_images(mock_doc)
        assert result == []

    def test_no_images_on_page(self):
        mock_page = MagicMock()
        mock_page.get_images.return_value = []
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        result = extract_images(mock_doc)
        assert result == []

    def test_filters_small_images(self):
        mock_page = MagicMock()
        mock_page.get_images.return_value = [(1,)]  # xref=1
        mock_page.get_image_rects.return_value = []

        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.extract_image.return_value = None  # no data

        result = extract_images(mock_doc, min_width=100, min_height=100)
        assert result == []
