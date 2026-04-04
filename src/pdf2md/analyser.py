"""PDF page analysis with text/scan detection."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pdf2md.logging import get_logger


class PageMode(Enum):
    """Page detection mode."""

    TEXT = "text"
    SCAN = "scan"


@dataclass
class TextBlock:
    """A block of text extracted from a PDF page."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float
    font_name: str
    is_bold: bool = False
    is_italic: bool = False


@dataclass
class PageAnalysis:
    """Analysis result for a single PDF page."""

    page_number: int  # 1-based
    mode: PageMode
    text_blocks: list[TextBlock] = field(default_factory=list)
    pixmap: Any | None = None  # fitz.Pixmap for SCAN pages
    has_images: bool = False


@dataclass
class DocumentAnalysis:
    """Analysis result for the entire PDF document."""

    total_pages: int
    pages: list[PageAnalysis]
    file_size_bytes: int
    file_path: str


def _detect_font_flags(font_name: str, flags: int) -> tuple[bool, bool]:
    """Determine bold/italic status from font name and flags.

    PyMuPDF font flags: bit 0 = superscript, bit 1 = italic, bit 2 = serif,
    bit 3 = monospaced, bit 4 = bold.

    Args:
        font_name: Name of the font
        flags: Font flags integer from PyMuPDF

    Returns:
        Tuple of (is_bold, is_italic)
    """
    is_bold = bool(flags & (1 << 4)) or "Bold" in font_name
    is_italic = bool(flags & (1 << 1)) or "Italic" in font_name
    return is_bold, is_italic


def _extract_text_blocks(page_dict: dict) -> list[TextBlock]:
    """Parse PyMuPDF text dict into TextBlock objects.

    Args:
        page_dict: Dictionary from page.get_text("dict")

    Returns:
        List of TextBlock objects with extracted metadata
    """
    blocks: list[TextBlock] = []

    for page_block in page_dict.get("blocks", []):
        if page_block.get("type") != 0:  # type 0 = text, type 1 = image
            continue

        for line in page_block.get("lines", []):
            line_text_parts: list[str] = []
            line_x0 = line.get("bbox", [0, 0, 0, 0])[0]
            line_y0 = line.get("bbox", [0, 0, 0, 0])[1]
            line_x1 = line.get("bbox", [0, 0, 0, 0])[2]
            line_y1 = line.get("bbox", [0, 0, 0, 0])[3]
            line_font_size = -1.0
            line_font_name = ""
            line_flags = 0

            for span in line.get("spans", []):
                span_text = span.get("text", "")
                line_text_parts.append(span_text)

                size = span.get("size", 0.0)
                if size > line_font_size:
                    line_font_size = size
                    line_font_name = span.get("font", "")
                    line_flags = span.get("flags", 0)

            if not line_text_parts:
                continue

            full_text = "".join(line_text_parts).strip()
            if not full_text:
                continue

            is_bold, is_italic = _detect_font_flags(line_font_name, line_flags)

            blocks.append(
                TextBlock(
                    text=full_text,
                    x0=line_x0,
                    y0=line_y0,
                    x1=line_x1,
                    y1=line_y1,
                    font_size=line_font_size,
                    font_name=line_font_name,
                    is_bold=is_bold,
                    is_italic=is_italic,
                )
            )

    return blocks


def _count_text_chars(page_dict: dict) -> int:
    """Count non-whitespace characters in a page text dict.

    Args:
        page_dict: Dictionary from page.get_text("dict")

    Returns:
        Number of non-whitespace characters
    """
    char_count = 0
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                char_count += len(span.get("text", "").strip())
    return char_count


def analyze_pdf(
    pdf_path: str,
    text_threshold: int = 50,
    dpi: int = 150,
) -> DocumentAnalysis:
    """Analyze a PDF document and determine page modes.

    Args:
        pdf_path: Path to the PDF file
        text_threshold: Minimum character count to consider a page as text-based
        dpi: DPI for rendering SCAN pages

    Returns:
        DocumentAnalysis with per-page results

    Raises:
        FileNotFoundError: If PDF doesn't exist
        ValueError: If file is not a valid PDF
    """
    import fitz  # noqa: PLC0415

    logger = get_logger()

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"File is not a PDF: {pdf_path}")

    file_size_bytes = os.path.getsize(pdf_path)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Cannot open PDF: {pdf_path}: {e}") from e

    total_pages = len(doc)
    pages: list[PageAnalysis] = []

    logger.info(f"Analyzing PDF: {pdf_path} ({total_pages} pages, {file_size_bytes} bytes)")

    for page_num in range(total_pages):
        page_number = page_num + 1  # 1-based
        page = doc[page_num]

        # Check if page has embedded images
        images = page.get_images(full=True)
        has_images = len(images) > 0

        # Attempt text extraction
        try:
            page_dict = page.get_text("dict")
        except Exception:
            page_dict = {}

        char_count = _count_text_chars(page_dict)

        if char_count > text_threshold:
            mode = PageMode.TEXT
            text_blocks = _extract_text_blocks(page_dict)
            logger.debug(f"Page {page_number}: TEXT mode ({char_count} chars, {len(text_blocks)} blocks)")
            pages.append(
                PageAnalysis(
                    page_number=page_number,
                    mode=mode,
                    text_blocks=text_blocks,
                    has_images=has_images,
                )
            )
        else:
            mode = PageMode.SCAN
            logger.debug(f"Page {page_number}: SCAN mode ({char_count} chars)")

            # Render page to pixmap at specified DPI
            try:
                pixmap = page.get_pixmap(dpi=dpi)
            except Exception as e:
                logger.warning(f"Page {page_number}: Failed to render pixmap: {e}")
                pixmap = None

            pages.append(
                PageAnalysis(
                    page_number=page_number,
                    mode=mode,
                    text_blocks=[],
                    pixmap=pixmap,
                    has_images=has_images,
                )
            )

    doc.close()

    text_pages = sum(1 for p in pages if p.mode == PageMode.TEXT)
    scan_pages = sum(1 for p in pages if p.mode == PageMode.SCAN)
    logger.info(f"Analysis complete: {text_pages} text pages, {scan_pages} scan pages")

    return DocumentAnalysis(
        total_pages=total_pages,
        pages=pages,
        file_size_bytes=file_size_bytes,
        file_path=str(path.resolve()),
    )
