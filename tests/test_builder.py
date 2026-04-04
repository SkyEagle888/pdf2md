"""Tests for pdf2md builder module."""

from __future__ import annotations

from pdf2md.analyser import (
    DocumentAnalysis,
    PageAnalysis,
    PageMode,
    TextBlock,
)
from pdf2md.builder import BuildStats, MarkdownBuilder
from pdf2md.images import ExtractedImage
from pdf2md.ocr import OCRResult, PageOCRResult


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_text_block(
    text: str,
    x0: float = 10.0,
    y0: float = 10.0,
    x1: float = 100.0,
    y1: float = 22.0,
    font_size: float = 12.0,
    font_name: str = "Helvetica",
    is_bold: bool = False,
    is_italic: bool = False,
) -> TextBlock:
    """Create a TextBlock with sensible defaults."""
    return TextBlock(
        text=text,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        font_size=font_size,
        font_name=font_name,
        is_bold=is_bold,
        is_italic=is_italic,
    )


def _make_page_analysis(
    page_number: int,
    mode: PageMode,
    blocks: list[TextBlock] | None = None,
) -> PageAnalysis:
    """Create a PageAnalysis with given blocks."""
    return PageAnalysis(
        page_number=page_number,
        mode=mode,
        text_blocks=blocks or [],
    )


def _make_document_analysis(pages: list[PageAnalysis]) -> DocumentAnalysis:
    """Create a DocumentAnalysis from pages."""
    return DocumentAnalysis(
        total_pages=len(pages),
        pages=pages,
        file_size_bytes=1024,
        file_path="/test/doc.pdf",
    )


def _make_extracted_image(
    page_number: int,
    image_index: int,
    y0: float = 100.0,
) -> ExtractedImage:
    """Create an ExtractedImage with defaults."""
    return ExtractedImage(
        page_number=page_number,
        image_index=image_index,
        filename=f"page{page_number}_img{image_index}.png",
        width=200,
        height=150,
        y0=y0,
        data=b"fake-png-data",
    )


def _make_ocr_result(
    page_number: int,
    results: list[OCRResult],
) -> PageOCRResult:
    """Create a PageOCRResult."""
    full_text = "\n".join(r.text for r in results)
    return PageOCRResult(
        page_number=page_number,
        results=results,
        full_text=full_text,
    )


# ---------------------------------------------------------------------------
# BuildStats tests
# ---------------------------------------------------------------------------


class TestBuildStats:
    def test_defaults(self):
        stats = BuildStats()
        assert stats.pages_processed == 0
        assert stats.headings_found == 0
        assert stats.lists_found == 0
        assert stats.code_blocks_found == 0
        assert stats.tables_found == 0
        assert stats.images_inserted == 0
        assert stats.ocr_pages == 0


# ---------------------------------------------------------------------------
# MarkdownBuilder initialisation tests
# ---------------------------------------------------------------------------


class TestMarkdownBuilderInit:
    def test_defaults(self):
        builder = MarkdownBuilder()
        assert builder.add_page_breaks is False
        assert builder.max_heading_level == 4
        assert builder._font_size_map == {}

    def test_custom_settings(self):
        builder = MarkdownBuilder(add_page_breaks=True, max_heading_level=6)
        assert builder.add_page_breaks is True
        assert builder.max_heading_level == 6


# ---------------------------------------------------------------------------
# Font size map tests
# ---------------------------------------------------------------------------


class TestFontSizeMap:
    def test_empty_document(self):
        builder = MarkdownBuilder()
        analysis = _make_document_analysis([])
        result = builder._build_font_size_map(analysis)
        assert result == {}

    def test_single_font_size(self):
        blocks = [
            _make_text_block("Hello", font_size=12.0),
            _make_text_block("World", font_size=12.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder._build_font_size_map(analysis)
        assert 12.0 in result
        assert result[12.0] == 1  # Only one size → H1

    def test_multiple_font_sizes(self):
        blocks = [
            _make_text_block("Title", font_size=24.0),
            _make_text_block("Subtitle", font_size=18.0),
            _make_text_block("Body", font_size=12.0),
            _make_text_block("Small", font_size=10.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder._build_font_size_map(analysis)

        assert result[24.0] == 1  # Largest → H1
        assert result[18.0] == 2  # Second → H2
        assert result[12.0] == 3  # Third → H3
        assert result[10.0] == 4  # Fourth → H4

    def test_max_heading_level_respected(self):
        blocks = [
            _make_text_block("S1", font_size=30.0),
            _make_text_block("S2", font_size=25.0),
            _make_text_block("S3", font_size=20.0),
            _make_text_block("S4", font_size=15.0),
            _make_text_block("S5", font_size=12.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder(max_heading_level=2)
        result = builder._build_font_size_map(analysis)

        assert result[30.0] == 1
        assert result[25.0] == 2
        assert 20.0 not in result  # Beyond max_heading_level
        assert 15.0 not in result
        assert 12.0 not in result

    def test_scan_pages_excluded_from_font_map(self):
        text_blocks = [_make_text_block("Text", font_size=14.0)]
        pages = [
            _make_page_analysis(1, PageMode.TEXT, text_blocks),
            _make_page_analysis(2, PageMode.SCAN, []),
        ]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder._build_font_size_map(analysis)
        assert 14.0 in result
        assert len(result) == 1

    def test_negative_font_size_excluded(self):
        blocks = [_make_text_block("Bad", font_size=-1.0)]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder._build_font_size_map(analysis)
        assert result == {}


# ---------------------------------------------------------------------------
# Heading level detection tests
# ---------------------------------------------------------------------------


class TestHeadingLevel:
    def test_exact_size_match(self):
        builder = MarkdownBuilder()
        builder._font_size_map = {24.0: 1, 18.0: 2, 12.0: 3}

        block = _make_text_block("Title", font_size=24.0)
        assert builder._get_heading_level(block) == 1

        block = _make_text_block("Subtitle", font_size=18.0)
        assert builder._get_heading_level(block) == 2

    def test_no_match_returns_none(self):
        builder = MarkdownBuilder()
        builder._font_size_map = {24.0: 1}

        block = _make_text_block("Body", font_size=12.0)
        assert builder._get_heading_level(block) is None

    def test_bold_non_italic_defaults_to_h3(self):
        builder = MarkdownBuilder()
        builder._font_size_map = {24.0: 1}  # Bold text not in map

        block = _make_text_block("Bold Text", font_size=12.0, is_bold=True)
        assert builder._get_heading_level(block) == 3

    def test_bold_italic_does_not_default(self):
        builder = MarkdownBuilder()
        builder._font_size_map = {24.0: 1}

        block = _make_text_block(
            "Bold Italic", font_size=12.0, is_bold=True, is_italic=True
        )
        assert builder._get_heading_level(block) is None

    def test_h3_respects_max_heading_level(self):
        builder = MarkdownBuilder(max_heading_level=2)
        builder._font_size_map = {24.0: 1}

        block = _make_text_block("Bold", font_size=12.0, is_bold=True)
        assert builder._get_heading_level(block) == 2  # capped at max_heading_level


# ---------------------------------------------------------------------------
# Paragraph grouping tests
# ---------------------------------------------------------------------------


class TestGroupIntoParagraphs:
    def test_empty_list(self):
        builder = MarkdownBuilder()
        result = builder._group_into_paragraphs([])
        assert result == []

    def test_single_block(self):
        blocks = [_make_text_block("Hello")]
        builder = MarkdownBuilder()
        result = builder._group_into_paragraphs(blocks)
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_close_blocks_same_paragraph(self):
        # Gap < line_height * 1.5 → same paragraph
        blocks = [
            _make_text_block("Line 1", y0=10.0, y1=20.0),
            _make_text_block("Line 2", y0=22.0, y1=32.0),  # gap=2
        ]
        builder = MarkdownBuilder()
        result = builder._group_into_paragraphs(blocks)
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_far_blocks_different_paragraphs(self):
        # Gap > line_height * 1.5 → different paragraphs
        blocks = [
            _make_text_block("Para 1", y0=10.0, y1=20.0),
            _make_text_block("Para 2", y0=50.0, y1=60.0),  # gap=30
        ]
        builder = MarkdownBuilder()
        result = builder._group_into_paragraphs(blocks)
        assert len(result) == 2
        assert result[0][0].text == "Para 1"
        assert result[1][0].text == "Para 2"


# ---------------------------------------------------------------------------
# List detection tests
# ---------------------------------------------------------------------------


class TestListDetection:
    def test_bullet_list_detection(self):
        blocks = [
            _make_text_block("• Item 1", x0=10.0),
            _make_text_block("• Item 2", x0=10.0),
            _make_text_block("• Item 3", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Item 3" in result

    def test_dash_bullet_list(self):
        blocks = [
            _make_text_block("- Item 1", x0=10.0),
            _make_text_block("- Item 2", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None
        assert "- Item 1" in result

    def test_asterisk_bullet_list(self):
        blocks = [
            _make_text_block("* Item 1", x0=10.0),
            _make_text_block("* Item 2", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None
        assert "- Item 1" in result  # Normalized to dash

    def test_numbered_list_detection(self):
        blocks = [
            _make_text_block("1. First item", x0=10.0),
            _make_text_block("2. Second item", x0=10.0),
            _make_text_block("3. Third item", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None
        assert "1. First item" in result
        assert "1. Second item" in result  # Normalized to "1."

    def test_numbered_list_with_paren(self):
        blocks = [
            _make_text_block("1) First", x0=10.0),
            _make_text_block("2) Second", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None

    def test_nested_list_indentation(self):
        blocks = [
            _make_text_block("• Item 1", x0=10.0, y0=10.0),
            _make_text_block("• Sub item", x0=30.0, y0=30.0),  # indented
            _make_text_block("• Item 2", x0=10.0, y0=50.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None
        # Sub item should be indented
        lines = result.split("\n")
        assert any(line.startswith("  - Sub item") for line in lines)

    def test_not_enough_list_items(self):
        blocks = [
            _make_text_block("• Item 1", x0=10.0),
            _make_text_block("Regular text", x0=10.0),
            _make_text_block("More text", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is None  # Only 1/3 = 33% < 50%

    def test_empty_blocks(self):
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list([])
        assert result is None

    def test_cjk_bullet(self):
        blocks = [
            _make_text_block("① First", x0=10.0),
            _make_text_block("② Second", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None

    def test_cjk_paren_number(self):
        blocks = [
            _make_text_block("（1）First", x0=10.0),
            _make_text_block("（2）Second", x0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_list(blocks)
        assert result is not None


# ---------------------------------------------------------------------------
# Code block detection tests
# ---------------------------------------------------------------------------


class TestCodeBlockDetection:
    def test_monospace_font_detected(self):
        builder = MarkdownBuilder()

        block = _make_text_block("code", font_name="Courier")
        assert builder._is_code_block(block) is True

        block = _make_text_block("code", font_name="Consolas")
        assert builder._is_code_block(block) is True

        block = _make_text_block("code", font_name="Menlo-Regular")
        assert builder._is_code_block(block) is True

        block = _make_text_block("code", font_name="SourceCodePro")
        assert builder._is_code_block(block) is True

    def test_non_monospace_font(self):
        builder = MarkdownBuilder()

        block = _make_text_block("text", font_name="Helvetica")
        assert builder._is_code_block(block) is False

        block = _make_text_block("text", font_name="Times New Roman")
        assert builder._is_code_block(block) is False

    def test_code_paragraph_all_monospace(self):
        blocks = [
            _make_text_block("def foo():", font_name="Courier"),
            _make_text_block("    pass", font_name="Courier"),
        ]
        builder = MarkdownBuilder()
        assert builder._is_code_paragraph(blocks) is True

    def test_code_paragraph_mixed_fonts(self):
        blocks = [
            _make_text_block("def foo():", font_name="Courier"),
            _make_text_block("Normal text", font_name="Helvetica"),
        ]
        builder = MarkdownBuilder()
        assert builder._is_code_paragraph(blocks) is False

    def test_language_detection_from_heading(self):
        builder = MarkdownBuilder()
        preceding = ["## Python Code Example"]
        lang = builder._detect_code_language(preceding)
        assert lang == "python"

    def test_language_detection_no_heading(self):
        builder = MarkdownBuilder()
        preceding = ["Just some paragraph text"]
        lang = builder._detect_code_language(preceding)
        assert lang is None

    def test_language_detection_empty_preceding(self):
        builder = MarkdownBuilder()
        lang = builder._detect_code_language([])
        assert lang is None

    def test_language_detection_various_languages(self):
        builder = MarkdownBuilder()

        assert builder._detect_code_language(["## JavaScript"]) == "javascript"
        assert builder._detect_code_language(["## Bash Script"]) == "bash"
        assert builder._detect_code_language(["## C++ Code"]) == "cpp"
        assert builder._detect_code_language(["## Go Example"]) == "go"
        assert builder._detect_code_language(["## Rust"]) == "rust"
        assert builder._detect_code_language(["## SQL Query"]) == "sql"

    def test_language_detection_word_boundary(self):
        """Ensure substring false positives don't occur (e.g. 'paragraph' matching 'latex')."""
        builder = MarkdownBuilder()
        # "paragraph" contains no whole-word match for any language hint
        lang = builder._detect_code_language(["## Paragraph text"])
        assert lang is None

        # "csharp" should not match "sharp" alone
        lang = builder._detect_code_language(["## Sharp tools"])
        assert lang is None

    def test_language_detection_special_chars(self):
        """Keys with special chars (c++, c#) use substring matching."""
        builder = MarkdownBuilder()
        assert builder._detect_code_language(["## C++ Tutorial"]) == "cpp"
        assert builder._detect_code_language(["## C# Programming"]) == "csharp"

    def test_language_detection_case_insensitive(self):
        builder = MarkdownBuilder()
        assert builder._detect_code_language(["## PYTHON CODE"]) == "python"


# ---------------------------------------------------------------------------
# Table detection tests
# ---------------------------------------------------------------------------


class TestTableDetection:
    def test_insufficient_blocks(self):
        blocks = [
            _make_text_block("Cell 1", y0=10.0),
            _make_text_block("Cell 2", y0=10.0),
            _make_text_block("Cell 3", y0=30.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_table(blocks)
        assert result is None  # 3 blocks < 2x2 = 4 minimum

    def test_simple_table(self):
        blocks = [
            _make_text_block("Name", y0=10.0),
            _make_text_block("Age", y0=10.0),
            _make_text_block("Alice", y0=30.0),
            _make_text_block("30", y0=30.0),
            _make_text_block("Bob", y0=50.0),
            _make_text_block("25", y0=50.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_table(blocks)
        assert result is not None
        assert "| Name | Age |" in result
        assert "| ------ | ------ |" in result  # GFM format with spaces
        assert "| Alice | 30 |" in result
        assert "| Bob | 25 |" in result

    def test_single_row_not_table(self):
        blocks = [
            _make_text_block("A", y0=10.0),
            _make_text_block("B", y0=10.0),
        ]
        builder = MarkdownBuilder()
        result = builder._detect_and_build_table(blocks)
        assert result is None


# ---------------------------------------------------------------------------
# Image insertion tests
# ---------------------------------------------------------------------------


class TestImageInsertion:
    def test_group_images_by_page(self):
        images = [
            _make_extracted_image(1, 1, y0=100.0),
            _make_extracted_image(1, 2, y0=200.0),
            _make_extracted_image(2, 1, y0=50.0),
        ]
        builder = MarkdownBuilder()
        result = builder._group_images_by_page(images)

        assert len(result) == 2
        assert len(result[1]) == 2
        assert len(result[2]) == 1
        # Check sorting by y0
        assert result[1][0].y0 == 100.0
        assert result[1][1].y0 == 200.0

    def test_insert_images_into_page(self):
        page_md = "# Title\n\nSome content here."
        images = [
            _make_extracted_image(1, 1, y0=100.0),
            _make_extracted_image(1, 2, y0=200.0),
        ]
        builder = MarkdownBuilder()
        result = builder._insert_images_into_page(page_md, images)

        assert "![page1_img1.png](images/page1_img1.png)" in result
        assert "![page1_img2.png](images/page1_img2.png)" in result
        assert "# Title" in result  # Original content preserved

    def test_insert_no_images(self):
        page_md = "Just text"
        builder = MarkdownBuilder()
        result = builder._insert_images_into_page(page_md, [])
        assert result == "Just text"

    def test_stats_image_count(self):
        page_md = "# Page"
        images = [
            _make_extracted_image(1, 1),
            _make_extracted_image(1, 2),
        ]
        builder = MarkdownBuilder()
        builder._insert_images_into_page(page_md, images)
        assert builder.stats.images_inserted == 2


# ---------------------------------------------------------------------------
# Markdown cleanup tests
# ---------------------------------------------------------------------------


class TestCleanMarkdown:
    def test_collapses_excessive_blank_lines(self):
        builder = MarkdownBuilder()
        md = "Para 1\n\n\n\n\nPara 2"  # 5 newlines = 4 blank lines
        result = builder._clean_markdown(md)
        assert "\n\n\n\n" not in result  # Should be collapsed to 2 blank lines
        assert "Para 1" in result
        assert "Para 2" in result

    def test_strips_trailing_whitespace(self):
        builder = MarkdownBuilder()
        md = "Line with spaces   \nAnother line   "
        result = builder._clean_markdown(md)
        assert "   \n" not in result
        assert result.endswith("\n")

    def test_ensures_trailing_newline(self):
        builder = MarkdownBuilder()
        md = "No newline at end"
        result = builder._clean_markdown(md)
        assert result.endswith("\n")

    def test_empty_string(self):
        builder = MarkdownBuilder()
        result = builder._clean_markdown("")
        assert result == ""

    def test_strips_leading_blank_lines(self):
        builder = MarkdownBuilder()
        md = "\n\n\nContent here\n"
        result = builder._clean_markdown(md)
        assert result.startswith("Content here")

    def test_preserves_normal_blank_lines(self):
        builder = MarkdownBuilder()
        md = "Para 1\n\nPara 2\n\nPara 3"
        result = builder._clean_markdown(md)
        # Should keep the 2-blank-line separations
        assert "\n\n\n\n" not in result


# ---------------------------------------------------------------------------
# Full build tests (build method)
# ---------------------------------------------------------------------------


class TestBuild:
    def test_empty_document(self):
        builder = MarkdownBuilder()
        analysis = _make_document_analysis([])
        result = builder.build(analysis, [])
        assert result == ""

    def test_single_text_page(self):
        blocks = [
            _make_text_block("Title", font_size=24.0, y0=10.0, y1=34.0),
            _make_text_block("Body", font_size=12.0, y0=50.0, y1=62.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert "# Title" in result
        assert "Body" in result

    def test_heading_inference_in_build(self):
        blocks = [
            _make_text_block("Main Title", font_size=28.0, y0=10.0, y1=38.0),
            _make_text_block("Section", font_size=20.0, y0=50.0, y1=70.0),
            _make_text_block("Subsection", font_size=16.0, y0=80.0, y1=96.0),
            _make_text_block("Subsub", font_size=14.0, y0=100.0, y1=114.0),
            _make_text_block("Body", font_size=12.0, y0=120.0, y1=132.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert "# Main Title" in result  # H1
        assert "## Section" in result  # H2
        assert "Body" in result  # paragraph (5th size, outside H1-H4)

    def test_page_breaks_enabled(self):
        pages = [
            _make_page_analysis(
                1, PageMode.TEXT, [_make_text_block("Page 1", y0=10.0, y1=22.0)]
            ),
            _make_page_analysis(
                2, PageMode.TEXT, [_make_text_block("Page 2", y0=10.0, y1=22.0)]
            ),
        ]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder(add_page_breaks=True)
        result = builder.build(analysis, [])

        assert "---" in result

    def test_page_breaks_disabled(self):
        pages = [
            _make_page_analysis(
                1, PageMode.TEXT, [_make_text_block("Page 1", y0=10.0, y1=22.0)]
            ),
            _make_page_analysis(
                2, PageMode.TEXT, [_make_text_block("Page 2", y0=10.0, y1=22.0)]
            ),
        ]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder(add_page_breaks=False)
        result = builder.build(analysis, [])

        assert "---" not in result

    def test_images_included_in_build(self):
        blocks = [
            _make_text_block("Title", font_size=24.0, y0=10.0, y1=34.0),
            _make_text_block("Body", font_size=12.0, y0=50.0, y1=62.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)
        images = [_make_extracted_image(1, 1, y0=50.0)]

        builder = MarkdownBuilder()
        result = builder.build(analysis, images)

        assert "![page1_img1.png](images/page1_img1.png)" in result

    def test_build_stats_populated(self):
        blocks = [
            _make_text_block("Title", font_size=24.0, y0=10.0, y1=30.0),
            _make_text_block("Body", font_size=12.0, y0=50.0, y1=62.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        builder.build(analysis, [])

        assert builder.stats.pages_processed == 1
        assert builder.stats.headings_found >= 1

    def test_mixed_text_and_scan_pages(self):
        pages = [
            _make_page_analysis(
                1, PageMode.TEXT, [_make_text_block("Text page", y0=10.0, y1=22.0)]
            ),
            _make_page_analysis(2, PageMode.SCAN, []),
        ]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert "Text page" in result
        # Scan page with no OCR → empty, but shouldn't crash

    def test_scan_page_without_ocr_returns_empty(self):
        pages = [_make_page_analysis(1, PageMode.SCAN, [])]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert result == ""


# ---------------------------------------------------------------------------
# Full build_with_ocr tests
# ---------------------------------------------------------------------------


class TestBuildWithOcr:
    def test_ocr_page_processed(self):
        pages = [_make_page_analysis(1, PageMode.SCAN, [])]
        analysis = _make_document_analysis(pages)

        ocr_results = {
            1: _make_ocr_result(
                1,
                [
                    OCRResult("OCR Line 1", 10, 10, 100, 20, 0.9),
                    OCRResult("OCR Line 2", 10, 30, 100, 40, 0.85),
                ],
            ),
        }

        builder = MarkdownBuilder()
        result = builder.build_with_ocr(analysis, [], ocr_results)

        assert "OCR Line 1" in result
        assert "OCR Line 2" in result

    def test_missing_ocr_returns_empty(self, caplog):
        pages = [_make_page_analysis(1, PageMode.SCAN, [])]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build_with_ocr(analysis, [], {})

        assert result == ""
        assert "No OCR results available" in caplog.text

    def test_mixed_text_and_ocr_pages(self):
        text_blocks = [
            _make_text_block("Title", font_size=24.0, y0=10.0, y1=30.0),
            _make_text_block("Body", font_size=12.0, y0=40.0, y1=52.0),
        ]
        pages = [
            _make_page_analysis(1, PageMode.TEXT, text_blocks),
            _make_page_analysis(2, PageMode.SCAN, []),
        ]
        analysis = _make_document_analysis(pages)

        ocr_results = {
            2: _make_ocr_result(
                2,
                [OCRResult("Scanned text", 10, 10, 100, 20, 0.9)],
            ),
        }

        builder = MarkdownBuilder()
        result = builder.build_with_ocr(analysis, [], ocr_results)

        assert "# Title" in result
        assert "Scanned text" in result

    def test_ocr_stats_tracked(self):
        pages = [_make_page_analysis(1, PageMode.SCAN, [])]
        analysis = _make_document_analysis(pages)
        ocr_results = {
            1: _make_ocr_result(
                1,
                [OCRResult("Text", 10, 10, 100, 20, 0.9)],
            ),
        }

        builder = MarkdownBuilder()
        builder.build_with_ocr(analysis, [], ocr_results)

        assert builder.stats.ocr_pages == 1
        assert builder.stats.pages_processed == 1

    def test_empty_ocr_results(self):
        pages = [_make_page_analysis(1, PageMode.SCAN, [])]
        analysis = _make_document_analysis(pages)
        ocr_results = {1: PageOCRResult(page_number=1)}  # empty results

        builder = MarkdownBuilder()
        result = builder.build_with_ocr(analysis, [], ocr_results)

        assert result == ""


# ---------------------------------------------------------------------------
# End-to-end integration-style tests
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_document_with_headings_and_body(self):
        """Test heading inference with 5 font sizes so body is paragraph."""
        blocks = [
            _make_text_block("Main Title", font_size=28.0, y0=10.0, y1=38.0),
            _make_text_block("Section", font_size=22.0, y0=50.0, y1=72.0),
            _make_text_block("Subsection", font_size=16.0, y0=84.0, y1=100.0),
            _make_text_block("Sub-sub", font_size=14.0, y0=114.0, y1=128.0),
            _make_text_block("Body text paragraph", font_size=12.0, y0=142.0, y1=154.0),
            _make_text_block("Footnote", font_size=10.0, y0=166.0, y1=176.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert "# Main Title" in result
        assert "## Section" in result
        assert "### Subsection" in result
        assert "#### Sub-sub" in result
        assert "Body text paragraph" in result
        assert "Footnote" in result

    def test_document_with_bullet_list(self):
        """Test bullet list detection — all same-size blocks so list is
        detected (no non-list text to dilute the percentage)."""
        blocks = [
            _make_text_block("• Apples", x0=20.0, font_size=12.0, y0=10.0, y1=22.0),
            _make_text_block("• Bananas", x0=20.0, font_size=12.0, y0=34.0, y1=46.0),
            _make_text_block("  • Red banana", x0=40.0, font_size=12.0, y0=58.0, y1=70.0),
            _make_text_block("• Cherries", x0=20.0, font_size=12.0, y0=82.0, y1=94.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert "- Apples" in result
        assert "- Bananas" in result
        assert "- Cherries" in result
        assert "  - Red banana" in result  # nested

    def test_document_with_code_block(self):
        """Test code block detection — monospace font blocks grouped
        into one paragraph by proximity."""
        blocks = [
            _make_text_block("def hello():", font_name="Courier", y0=10.0, y1=22.0),
            _make_text_block("    print('hi')", font_name="Courier", y0=26.0, y1=38.0),
            _make_text_block("    return 0", font_name="Courier", y0=42.0, y1=54.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert "```" in result
        assert "def hello():" in result
        assert "    print('hi')" in result
        assert "    return 0" in result

    def test_document_with_images(self):
        """Test image insertion in build output."""
        blocks = [
            _make_text_block("Page content", font_size=12.0, y0=10.0, y1=22.0),
        ]
        pages = [_make_page_analysis(1, PageMode.TEXT, blocks)]
        analysis = _make_document_analysis(pages)
        images = [
            _make_extracted_image(1, 1, y0=50.0),
            _make_extracted_image(1, 2, y0=150.0),
        ]

        builder = MarkdownBuilder()
        result = builder.build(analysis, images)

        assert "![page1_img1.png](images/page1_img1.png)" in result
        assert "![page1_img2.png](images/page1_img2.png)" in result

    def test_multi_page_document(self):
        page1_blocks = [
            _make_text_block("Page 1 Title", font_size=24.0, y0=10.0, y1=34.0),
            _make_text_block("Page 1 content", font_size=12.0, y0=50.0, y1=62.0),
        ]
        page2_blocks = [
            _make_text_block("Page 2 Title", font_size=24.0, y0=10.0, y1=34.0),
            _make_text_block("Page 2 content", font_size=12.0, y0=50.0, y1=62.0),
        ]

        pages = [
            _make_page_analysis(1, PageMode.TEXT, page1_blocks),
            _make_page_analysis(2, PageMode.TEXT, page2_blocks),
        ]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder(add_page_breaks=True)
        result = builder.build(analysis, [])

        assert "Page 1 Title" in result
        assert "Page 2 Title" in result
        assert "---" in result

    def test_empty_page_skipped(self):
        pages = [
            _make_page_analysis(1, PageMode.TEXT, []),  # Empty page
            _make_page_analysis(
                2, PageMode.TEXT, [_make_text_block("Content", y0=10.0, y1=22.0)]
            ),
        ]
        analysis = _make_document_analysis(pages)

        builder = MarkdownBuilder()
        result = builder.build(analysis, [])

        assert "Content" in result
        # Empty page should not contribute blank content
