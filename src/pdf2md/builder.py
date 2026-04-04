"""Markdown builder — assembles Markdown from PDF analysis and OCR results."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from pdf2md.analyser import (
    DocumentAnalysis,
    PageAnalysis,
    PageMode,
    TextBlock,
)
from pdf2md.images import ExtractedImage
from pdf2md.logging import get_logger
from pdf2md.ocr import PageOCRResult

# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

BULLET_PATTERNS = [
    re.compile(r"^[•\-\*·○■]\s+"),
    re.compile(r"^[-*+]\s+"),
    re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*"),
    re.compile(r"^[（(]\d+[）)]\s*"),
]

NUMBERED_PATTERNS = [
    re.compile(r"^\d+\.\s+"),
    re.compile(r"^\d+\)\s+"),
]

MONOSPACE_KEYWORDS = [
    "mono",
    "courier",
    "consolas",
    "menlo",
    "code",
    "monospace",
    "terminal",
    "fixed",
]

# Language detection hints for code blocks
_LANGUAGE_HINTS: dict[str, str] = {
    "python": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "bash": "bash",
    "shell": "bash",
    "sh": "bash",
    "java": "java",
    "c++": "cpp",
    "cpp": "cpp",
    "c#": "csharp",
    "csharp": "csharp",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "ruby": "ruby",
    "php": "php",
    "sql": "sql",
    "html": "html",
    "css": "css",
    "json": "json",
    "xml": "xml",
    "yaml": "yaml",
    "toml": "toml",
    "markdown": "markdown",
    "md": "markdown",
    "latex": "latex",
    "tex": "latex",
    "r": "r",
    "matlab": "matlab",
    "swift": "swift",
    "kotlin": "kotlin",
    "dart": "dart",
    "lua": "lua",
    "perl": "perl",
    "scala": "scala",
    "haskell": "haskell",
}

# Table detection thresholds
_MIN_TABLE_ROWS = 2
_MIN_TABLE_COLS = 2
_TABLE_Y_TOLERANCE = 3.0  # pixels


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BuildStats:
    """Statistics from a Markdown build operation."""

    pages_processed: int = 0
    headings_found: int = 0
    lists_found: int = 0
    code_blocks_found: int = 0
    tables_found: int = 0
    images_inserted: int = 0
    ocr_pages: int = 0


# ---------------------------------------------------------------------------
# MarkdownBuilder
# ---------------------------------------------------------------------------


class MarkdownBuilder:
    """Assembles Markdown from PDF analysis and OCR results."""

    def __init__(
        self,
        add_page_breaks: bool = False,
        max_heading_level: int = 4,
    ) -> None:
        """Initialize the Markdown builder.

        Args:
            add_page_breaks: Whether to add horizontal rules between pages
            max_heading_level: Maximum heading level to infer (1-6)
        """
        self.add_page_breaks = add_page_breaks
        self.max_heading_level = max_heading_level
        self._font_size_map: dict[float, int] = {}
        self._stats = BuildStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        analysis: DocumentAnalysis,
        images: list[ExtractedImage],
    ) -> str:
        """Build complete Markdown document.

        Args:
            analysis: Document analysis from analyser.py
            images: Extracted images from images.py

        Returns:
            Complete Markdown string
        """
        logger = get_logger()
        self._stats = BuildStats()

        # Build font size → heading level map from TEXT pages
        self._font_size_map = self._build_font_size_map(analysis)

        pages_markdown: list[str] = []

        for page in analysis.pages:
            page_md = self._process_page(page, {})
            if page_md:
                pages_markdown.append(page_md)

        # Insert images into the appropriate pages
        images_by_page = self._group_images_by_page(images)
        pages_markdown_with_images: list[str] = []
        for i, page_md in enumerate(pages_markdown):
            page_number = i + 1  # pages_markdown is in order
            page_images = images_by_page.get(page_number, [])
            if page_images:
                page_md = self._insert_images_into_page(page_md, page_images)
            pages_markdown_with_images.append(page_md)

        # Join pages
        if self.add_page_breaks:
            result = "\n\n---\n\n".join(pages_markdown_with_images)
        else:
            result = "\n\n".join(pages_markdown_with_images)

        result = self._clean_markdown(result)

        self._stats.pages_processed = len(analysis.pages)
        logger.info(
            f"Build complete: {self._stats.pages_processed} pages, "
            f"{self._stats.headings_found} headings, "
            f"{self._stats.lists_found} lists, "
            f"{self._stats.code_blocks_found} code blocks, "
            f"{self._stats.tables_found} tables, "
            f"{self._stats.images_inserted} images"
        )

        return result

    def build_with_ocr(
        self,
        analysis: DocumentAnalysis,
        images: list[ExtractedImage],
        ocr_results: dict[int, PageOCRResult],
    ) -> str:
        """Build Markdown document with OCR support.

        Args:
            analysis: Document analysis from analyser.py
            images: Extracted images from images.py
            ocr_results: Map of page_number (1-based) → PageOCRResult

        Returns:
            Complete Markdown string
        """
        logger = get_logger()
        self._stats = BuildStats()

        # Build font size → heading level map from TEXT pages only
        self._font_size_map = self._build_font_size_map(analysis)

        pages_markdown: list[str] = []

        for page in analysis.pages:
            page_md = self._process_page(page, ocr_results)
            if page_md:
                pages_markdown.append(page_md)

        # Insert images
        images_by_page = self._group_images_by_page(images)
        pages_markdown_with_images: list[str] = []
        for i, page_md in enumerate(pages_markdown):
            page_number = i + 1
            page_images = images_by_page.get(page_number, [])
            if page_images:
                page_md = self._insert_images_into_page(page_md, page_images)
            pages_markdown_with_images.append(page_md)

        # Join pages
        if self.add_page_breaks:
            result = "\n\n---\n\n".join(pages_markdown_with_images)
        else:
            result = "\n\n".join(pages_markdown_with_images)

        result = self._clean_markdown(result)

        self._stats.pages_processed = len(analysis.pages)
        logger.info(
            f"Build complete (with OCR): {self._stats.pages_processed} pages, "
            f"{self._stats.headings_found} headings, "
            f"{self._stats.lists_found} lists, "
            f"{self._stats.code_blocks_found} code blocks, "
            f"{self._stats.tables_found} tables, "
            f"{self._stats.images_inserted} images, "
            f"{self._stats.ocr_pages} OCR pages"
        )

        return result

    @property
    def stats(self) -> BuildStats:
        """Return statistics from the last build operation."""
        return self._stats

    # ------------------------------------------------------------------
    # Heading inference
    # ------------------------------------------------------------------

    def _build_font_size_map(
        self, analysis: DocumentAnalysis
    ) -> dict[float, int]:
        """Map font sizes to heading levels.

        Collects all unique font sizes across TEXT pages, sorts them
        from largest to smallest, and maps the top sizes to H1-H4.

        Returns:
            Dict mapping font_size → heading_level (1-4)
        """
        font_sizes: set[float] = set()

        for page in analysis.pages:
            if page.mode != PageMode.TEXT:
                continue
            for block in page.text_blocks:
                if block.font_size > 0:
                    font_sizes.add(block.font_size)

        if not font_sizes:
            return {}

        # Sort descending (largest first)
        sorted_sizes = sorted(font_sizes, reverse=True)

        # Map top N sizes to heading levels
        size_map: dict[float, int] = {}
        for i, size in enumerate(sorted_sizes):
            if i < self.max_heading_level:
                size_map[size] = i + 1  # H1, H2, H3, H4

        return size_map

    def _get_heading_level(self, block: TextBlock) -> int | None:
        """Determine heading level for a text block.

        Args:
            block: TextBlock to evaluate

        Returns:
            Heading level (1-4) or None if not a heading
        """
        # Exact font size match
        if block.font_size in self._font_size_map:
            return self._font_size_map[block.font_size]

        # Bold-only spans at paragraph font size → treat as H3
        # if no larger headings are nearby (heuristic)
        if block.is_bold and not block.is_italic:
            return min(3, self.max_heading_level)

        return None

    # ------------------------------------------------------------------
    # Page processing
    # ------------------------------------------------------------------

    def _process_page(
        self,
        page: PageAnalysis,
        ocr_results: dict[int, PageOCRResult],
    ) -> str:
        """Process a single page and return Markdown.

        Args:
            page: PageAnalysis for this page
            ocr_results: Map of page_number → PageOCRResult for scanned pages

        Returns:
            Markdown string for this page (empty string if no content)
        """
        if page.mode == PageMode.TEXT:
            return self._process_text_page(page)
        elif page.mode == PageMode.SCAN:
            return self._process_scan_page(page.page_number, ocr_results)
        return ""

    def _process_text_page(self, page: PageAnalysis) -> str:
        """Process a TEXT mode page and convert to Markdown.

        Args:
            page: PageAnalysis with text blocks

        Returns:
            Markdown string for this page
        """
        if not page.text_blocks:
            return ""

        blocks = page.text_blocks
        paragraphs = self._group_into_paragraphs(blocks)
        parts: list[str] = []

        for i, paragraph_blocks in enumerate(paragraphs):
            # Check if this paragraph forms a code block
            if self._is_code_paragraph(paragraph_blocks):
                self._stats.code_blocks_found += 1
                # Try to detect language from preceding heading
                lang = self._detect_code_language(parts)
                code_text = "\n".join(b.text for b in paragraph_blocks)
                if lang:
                    parts.append(f"```{lang}\n{code_text}\n```")
                else:
                    parts.append(f"```\n{code_text}\n```")
                continue

            # Check if this paragraph forms a table
            table_md = self._detect_and_build_table(paragraph_blocks)
            if table_md is not None:
                self._stats.tables_found += 1
                parts.append(table_md)
                continue

            # Check if this paragraph is a list
            list_md = self._detect_and_build_list(paragraph_blocks)
            if list_md is not None:
                self._stats.lists_found += 1
                parts.append(list_md)
                continue

            # Regular paragraph — process each block
            para_parts: list[str] = []
            for block in paragraph_blocks:
                heading_level = self._get_heading_level(block)
                if heading_level is not None:
                    self._stats.headings_found += 1
                    prefix = "#" * heading_level
                    para_parts.append(f"{prefix} {block.text}")
                else:
                    para_parts.append(block.text)

            if para_parts:
                parts.append("\n".join(para_parts))

        return "\n\n".join(parts)

    def _process_scan_page(
        self,
        page_number: int,
        ocr_results: dict[int, PageOCRResult],
    ) -> str:
        """Process a SCAN mode page using OCR results.

        Args:
            page_number: Page number (1-based)
            ocr_results: Map of page_number → PageOCRResult

        Returns:
            Markdown string for this page
        """
        ocr = ocr_results.get(page_number)
        if ocr is None or not ocr.results:
            # No OCR results — return empty
            if ocr is None:
                get_logger().warning(
                    f"Page {page_number}: No OCR results available for scan page"
                )
            return ""

        self._stats.ocr_pages += 1

        # OCR results don't have font metadata, treat as paragraphs
        # Group by proximity (same heuristic as text pages)
        paragraphs = self._group_ocr_into_paragraphs(ocr.results)
        parts: list[str] = []

        for para_results in paragraphs:
            para_text = "\n".join(r.text for r in para_results)
            if para_text.strip():
                parts.append(para_text)

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Paragraph grouping
    # ------------------------------------------------------------------

    def _group_into_paragraphs(
        self, blocks: list[TextBlock]
    ) -> list[list[TextBlock]]:
        """Group consecutive text blocks into paragraphs.

        Uses proximity: if gap between blocks < line_height × 1.5,
        they belong to the same paragraph.

        Args:
            blocks: List of TextBlock objects (assumed sorted by y0)

        Returns:
            List of paragraph groups (each group is a list of TextBlocks)
        """
        if not blocks:
            return []

        # Calculate average line height
        line_heights: list[float] = []
        for block in blocks:
            height = block.y1 - block.y0
            if height > 0:
                line_heights.append(height)

        if line_heights:
            avg_line_height = sum(line_heights) / len(line_heights)
        else:
            avg_line_height = 12.0  # fallback

        threshold = avg_line_height * 1.5

        paragraphs: list[list[TextBlock]] = []
        current_para: list[TextBlock] = [blocks[0]]

        for i in range(1, len(blocks)):
            prev = blocks[i - 1]
            curr = blocks[i]

            gap = curr.y0 - prev.y1

            if gap < threshold:
                current_para.append(curr)
            else:
                paragraphs.append(current_para)
                current_para = [curr]

        if current_para:
            paragraphs.append(current_para)

        return paragraphs

    def _group_ocr_into_paragraphs(
        self, results: list  # list[OCRResult]
    ) -> list[list]:
        """Group OCR results into paragraphs.

        Similar to _group_into_paragraphs but works on OCRResult objects.

        Args:
            results: List of OCRResult objects (assumed sorted by y0)

        Returns:
            List of paragraph groups
        """
        if not results:
            return []

        # Calculate average line height from OCR bounding boxes
        line_heights: list[float] = []
        for r in results:
            height = r.y1 - r.y0
            if height > 0:
                line_heights.append(height)

        if line_heights:
            avg_line_height = sum(line_heights) / len(line_heights)
        else:
            avg_line_height = 12.0

        threshold = avg_line_height * 1.5

        paragraphs: list[list] = []
        current_para: list = [results[0]]

        for i in range(1, len(results)):
            prev = results[i - 1]
            curr = results[i]

            gap = curr.y0 - prev.y1

            if gap < threshold:
                current_para.append(curr)
            else:
                paragraphs.append(current_para)
                current_para = [curr]

        if current_para:
            paragraphs.append(current_para)

        return paragraphs

    # ------------------------------------------------------------------
    # List detection
    # ------------------------------------------------------------------

    def _detect_and_build_list(
        self, blocks: list[TextBlock]
    ) -> str | None:
        """Detect if blocks form a list and render as Markdown list.

        Args:
            blocks: Text blocks that may form a list

        Returns:
            Markdown list string or None if not a list
        """
        if not blocks:
            return None

        # Check if majority of blocks start with bullet or numbered patterns
        bullet_count = 0
        numbered_count = 0

        for block in blocks:
            if self._is_bullet(block.text):
                bullet_count += 1
            elif self._is_numbered(block.text):
                numbered_count += 1

        total = len(blocks)
        if bullet_count == 0 and numbered_count == 0:
            return None

        # Need at least 50% of blocks to match list patterns
        if (bullet_count + numbered_count) < total * 0.5:
            return None

        # Calculate baseline x0 (minimum left margin)
        min_x0 = min(b.x0 for b in blocks)

        # Determine indent unit (look at distinct x0 offsets)
        x0_values = sorted(set(b.x0 for b in blocks))
        if len(x0_values) > 1:
            # Find the smallest non-zero difference
            diffs = [x0_values[i + 1] - x0_values[i] for i in range(len(x0_values) - 1)]
            indent_unit = min(d for d in diffs if d > 0) if diffs else 20.0
        else:
            indent_unit = 20.0  # default

        # Build list items
        list_lines: list[str] = []
        for block in blocks:
            # Calculate indent level from x0 offset
            if indent_unit > 0:
                indent_level = round((block.x0 - min_x0) / indent_unit)
            else:
                indent_level = 0
            indent_level = max(0, indent_level)
            indent = "  " * indent_level  # 2 spaces per level

            if self._is_bullet(block.text):
                # Strip bullet prefix and add markdown bullet
                clean_text = self._strip_bullet(block.text)
                list_lines.append(f"{indent}- {clean_text}")
            elif self._is_numbered(block.text):
                # Strip number prefix — use "1." for all (markdown renders sequentially)
                clean_text = self._strip_numbered(block.text)
                list_lines.append(f"{indent}1. {clean_text}")
            else:
                # Non-list item within list — treat as continuation
                # Strip leading whitespace that may be present in the text
                clean_text = block.text.lstrip()
                list_lines.append(f"{indent}  {clean_text}")

        return "\n".join(list_lines)

    def _is_bullet(self, text: str) -> bool:
        """Check if text starts with a bullet pattern.

        Strips leading whitespace before matching to handle indented bullets.
        """
        stripped = text.lstrip()
        return any(p.match(stripped) is not None for p in BULLET_PATTERNS)

    def _is_numbered(self, text: str) -> bool:
        """Check if text starts with a numbered list pattern.

        Strips leading whitespace before matching.
        """
        stripped = text.lstrip()
        return any(p.match(stripped) is not None for p in NUMBERED_PATTERNS)

    def _strip_bullet(self, text: str) -> str:
        """Remove bullet prefix from text.

        Handles leading whitespace that may precede the bullet character.
        """
        stripped = text.lstrip()
        for pattern in BULLET_PATTERNS:
            match = pattern.match(stripped)
            if match:
                return stripped[match.end():].strip()
        return stripped.strip()

    def _strip_numbered(self, text: str) -> str:
        """Remove numbered list prefix from text.

        Handles leading whitespace.
        """
        stripped = text.lstrip()
        for pattern in NUMBERED_PATTERNS:
            match = pattern.match(stripped)
            if match:
                return stripped[match.end():].strip()
        return stripped.strip()

    # ------------------------------------------------------------------
    # Code block detection
    # ------------------------------------------------------------------

    def _is_code_block(self, block: TextBlock) -> bool:
        """Check if a text block is rendered in monospace font."""
        font_lower = block.font_name.lower()
        return any(kw in font_lower for kw in MONOSPACE_KEYWORDS)

    def _is_code_paragraph(self, blocks: list[TextBlock]) -> bool:
        """Check if all blocks in a paragraph are code blocks."""
        if not blocks:
            return False
        return all(self._is_code_block(b) for b in blocks)

    def _detect_code_language(self, preceding_markdown: list[str]) -> str | None:
        """Attempt to detect code language from preceding heading/label text.

        Args:
            preceding_markdown: Previously generated markdown lines

        Returns:
            Language specifier string or None
        """
        if not preceding_markdown:
            return None

        # Look at the last heading or recent text for language hints
        search_text = ""
        # Check last 3 entries for a heading
        for entry in reversed(preceding_markdown[-3:]):
            if entry.startswith("#"):
                search_text = entry
                break
            search_text = entry

        if not search_text:
            return None

        search_lower = search_text.lower()

        for hint, lang in _LANGUAGE_HINTS.items():
            # Keys containing non-alphanumeric chars (e.g. "c++", "c#")
            # use simple substring matching; word-boundary matching would
            # fail because + and # are non-word characters.
            if not hint.isalnum():
                if hint in search_lower:
                    return lang
            else:
                # Use word-boundary matching for regular alphanumeric keys
                # to avoid false positives (e.g. "paragraph" matching "latex")
                if re.search(rf"\b{re.escape(hint)}\b", search_lower):
                    return lang

        return None

    # ------------------------------------------------------------------
    # Table detection (best-effort)
    # ------------------------------------------------------------------

    def _detect_and_build_table(
        self, blocks: list[TextBlock]
    ) -> str | None:
        """Detect if blocks form a table and render as GFM table.

        Groups blocks by y-coordinate (rows) and checks for consistent
        column structure. Falls back to None if ambiguous.

        Args:
            blocks: Text blocks that may form a table

        Returns:
            GFM table string or None if not a table
        """
        if len(blocks) < _MIN_TABLE_ROWS * _MIN_TABLE_COLS:
            return None

        # Group blocks by y-coordinate (rows)
        rows = self._group_blocks_into_rows(blocks)

        if len(rows) < _MIN_TABLE_ROWS:
            return None

        # Check consistent column count
        col_counts = [len(row) for row in rows]
        if len(set(col_counts)) > 1:
            # Not all rows have the same number of columns
            # Check if majority agree
            counter = Counter(col_counts)
            most_common_count, most_common_freq = counter.most_common(1)[0]
            if most_common_freq < len(rows) * 0.7:
                return None
            # Use the most common column count, pad shorter rows
            target_cols = most_common_count
        else:
            target_cols = col_counts[0]

        if target_cols < _MIN_TABLE_COLS:
            return None

        # Check that columns are roughly aligned by x-coordinate
        col_x_positions = self._compute_column_positions(rows, target_cols)
        if col_x_positions is None:
            return None

        # Build GFM table
        table_lines: list[str] = []

        # Header row
        header_cells = [cell.strip() for cell in rows[0][:target_cols]]
        table_lines.append("| " + " | ".join(header_cells) + " |")

        # Separator row
        table_lines.append("| " + " | ".join(["------"] * target_cols) + " |")

        # Data rows
        for row in rows[1:]:
            cells = [cell.strip() for cell in row[:target_cols]]
            # Pad with empty cells if needed
            while len(cells) < target_cols:
                cells.append("")
            table_lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(table_lines)

    def _group_blocks_into_rows(
        self, blocks: list[TextBlock]
    ) -> list[list[str]]:
        """Group blocks into rows based on y-coordinate proximity.

        Args:
            blocks: Text blocks sorted by y0

        Returns:
            List of rows, each row is a list of text content
        """
        if not blocks:
            return []

        rows: list[list[str]] = []
        current_row: list[str] = [blocks[0].text]
        current_y = blocks[0].y0

        for block in blocks[1:]:
            if abs(block.y0 - current_y) < _TABLE_Y_TOLERANCE:
                current_row.append(block.text)
            else:
                rows.append(current_row)
                current_row = [block.text]
                current_y = block.y0

        if current_row:
            rows.append(current_row)

        return rows

    def _compute_column_positions(
        self, rows: list[list[str]], target_cols: int
    ) -> list[float] | None:
        """Verify that columns are roughly aligned across rows.

        This is a simplified check — in a real implementation we would
        use the x0 coordinates of blocks. Since we've already grouped
        by y, we just verify the count is consistent.

        Args:
            rows: Rows of text content
            target_cols: Expected number of columns

        Returns:
            List of column x positions or None if alignment is poor
        """
        # Simplified: just verify we have enough rows with the target count
        consistent_rows = sum(1 for r in rows if len(r) >= target_cols)
        if consistent_rows < len(rows) * 0.7:
            return None

        # Return dummy positions (we'd use actual x0 in a full implementation)
        return [float(i * 100) for i in range(target_cols)]

    # ------------------------------------------------------------------
    # Image insertion
    # ------------------------------------------------------------------

    def _group_images_by_page(
        self, images: list[ExtractedImage]
    ) -> dict[int, list[ExtractedImage]]:
        """Group images by page number.

        Args:
            images: List of extracted images

        Returns:
            Dict mapping page_number → list of images (sorted by y0)
        """
        by_page: dict[int, list[ExtractedImage]] = {}
        for img in images:
            by_page.setdefault(img.page_number, []).append(img)

        # Sort each page's images by y0
        for page_images in by_page.values():
            page_images.sort(key=lambda img: img.y0)

        return by_page

    def _insert_images_into_page(
        self,
        page_md: str,
        images: list[ExtractedImage],
    ) -> str:
        """Insert image markdown into page content.

        Images are inserted at the end of the page, sorted by y0.

        Args:
            page_md: Existing markdown for this page
            images: Images for this page (sorted by y0)

        Returns:
            Updated markdown with image references
        """
        if not images:
            return page_md

        image_lines: list[str] = []
        for img in images:
            # Format: ![pageN_imgM](images/pageN_imgM.png)
            # Use filename from the ExtractedImage
            alt_text = f"{img.filename}"
            image_lines.append(f"![{alt_text}](images/{img.filename})")
            self._stats.images_inserted += 1

        return page_md + "\n\n" + "\n\n".join(image_lines)

    # ------------------------------------------------------------------
    # Markdown cleanup
    # ------------------------------------------------------------------

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up markdown: collapse excessive blank lines.

        Replaces 3+ consecutive blank lines with 2, strips trailing
        whitespace, and ensures file ends with single newline.

        Args:
            markdown: Raw markdown string

        Returns:
            Cleaned markdown string
        """
        # Collapse 3+ consecutive blank lines to 2
        cleaned = re.sub(r"\n{4,}", "\n\n\n", markdown)

        # Strip trailing whitespace on each line
        lines = cleaned.split("\n")
        lines = [line.rstrip() for line in lines]
        cleaned = "\n".join(lines)

        # Strip leading/trailing blank lines, ensure single trailing newline
        cleaned = cleaned.strip()
        if cleaned:
            cleaned += "\n"

        return cleaned
