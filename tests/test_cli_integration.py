"""Comprehensive integration tests for pdf2md CLI (Phase 6).

Covers argument parsing, validation, helper functions, and the full
conversion pipeline with mocked dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pdf2md.analyser import DocumentAnalysis, PageAnalysis, PageMode, TextBlock
from pdf2md.cli import (
    EXIT_CONVERSION_FAILURE,
    EXIT_GENERIC_FAILURE,
    EXIT_INPUT_NOT_FOUND,
    EXIT_INVALID_USAGE,
    EXIT_OCR_MODEL_NOT_FOUND,
    EXIT_OUTPUT_NOT_WRITABLE,
    EXIT_SUCCESS,
    _has_scan_pages,
    _parse_min_image_size,
    main,
    parse_args,
    validate_args,
)

# ---------------------------------------------------------------------------
# Fixtures — reusable mock objects
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_text_analysis() -> DocumentAnalysis:
    """Mock DocumentAnalysis with TEXT pages only."""
    return DocumentAnalysis(
        total_pages=1,
        pages=[
            PageAnalysis(
                page_number=1,
                mode=PageMode.TEXT,
                text_blocks=[
                    TextBlock(
                        text="Hello World",
                        x0=10,
                        y0=10,
                        x1=100,
                        y1=20,
                        font_size=12.0,
                        font_name="Arial",
                    ),
                ],
            ),
        ],
        file_size_bytes=1000,
        file_path="/test/doc.pdf",
    )


@pytest.fixture
def mock_scan_analysis() -> DocumentAnalysis:
    """Mock DocumentAnalysis with SCAN pages only."""
    mock_pixmap = Mock()
    return DocumentAnalysis(
        total_pages=1,
        pages=[
            PageAnalysis(
                page_number=1,
                mode=PageMode.SCAN,
                text_blocks=[],
                pixmap=mock_pixmap,
            ),
        ],
        file_size_bytes=2000,
        file_path="/test/scanned.pdf",
    )


@pytest.fixture
def mock_mixed_analysis() -> DocumentAnalysis:
    """Mock DocumentAnalysis with both TEXT and SCAN pages."""
    mock_pixmap = Mock()
    return DocumentAnalysis(
        total_pages=3,
        pages=[
            PageAnalysis(
                page_number=1,
                mode=PageMode.TEXT,
                text_blocks=[
                    TextBlock(
                        text="Page 1 text",
                        x0=10,
                        y0=10,
                        x1=100,
                        y1=20,
                        font_size=14.0,
                        font_name="Arial",
                    ),
                ],
            ),
            PageAnalysis(
                page_number=2,
                mode=PageMode.SCAN,
                text_blocks=[],
                pixmap=mock_pixmap,
            ),
            PageAnalysis(
                page_number=3,
                mode=PageMode.TEXT,
                text_blocks=[
                    TextBlock(
                        text="Page 3 text",
                        x0=10,
                        y0=10,
                        x1=100,
                        y1=20,
                        font_size=12.0,
                        font_name="Times",
                    ),
                ],
            ),
        ],
        file_size_bytes=5000,
        file_path="/test/mixed.pdf",
    )


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    """Create a minimal fake PDF file on disk."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake pdf content")
    return pdf


@pytest.fixture
def fake_non_pdf(tmp_path: Path) -> Path:
    """Create a non-PDF file to test extension validation."""
    txt = tmp_path / "document.txt"
    txt.write_bytes(b"This is not a PDF")
    return txt


# ---------------------------------------------------------------------------
# Helper: patch all pipeline modules
# ---------------------------------------------------------------------------


def _patch_pipeline_mocks(
    analysis: DocumentAnalysis,
    images: list | None = None,
    ocr_error: Exception | None = None,
    extract_images_error: Exception | None = None,
) -> dict[str, MagicMock]:
    """Patch all pipeline modules and return the mock objects.

    Args:
        analysis: DocumentAnalysis to return from analyze_pdf.
        images: List of ExtractedImage (default: empty).
        ocr_error: If set, make OCREngine constructor raise this.
        extract_images_error: If set, make extract_images raise this.

    Returns:
        Dict of mock objects keyed by module name.
    """
    if images is None:
        images = []

    mock_analyse = MagicMock(return_value=analysis)

    if extract_images_error is not None:
        mock_extract = MagicMock(side_effect=extract_images_error)
    else:
        mock_extract = MagicMock(return_value=images)

    if ocr_error is not None:
        mock_ocr_cls = MagicMock(side_effect=ocr_error)
    else:
        mock_ocr_instance = MagicMock()
        mock_ocr_cls = MagicMock(return_value=mock_ocr_instance)

    mock_builder_instance = MagicMock()
    mock_builder_instance.stats = MagicMock()
    mock_builder_instance.stats.pages_processed = analysis.total_pages
    mock_builder_instance.stats.headings_found = 0
    mock_builder_instance.stats.lists_found = 0
    mock_builder_instance.stats.code_blocks_found = 0
    mock_builder_instance.stats.tables_found = 0
    mock_builder_instance.stats.images_placed = 0
    mock_builder_instance.build = MagicMock(
        return_value="# Markdown\n\nBody text\n"
    )
    mock_builder_instance.build_with_ocr = MagicMock(
        return_value="# Markdown\n\nOCR text\n"
    )
    mock_builder_cls = MagicMock(return_value=mock_builder_instance)

    mock_writer_instance = MagicMock()
    mock_writer_instance.validate_output = MagicMock(return_value=(True, None))
    mock_writer_instance.write = MagicMock(return_value=Path("/tmp/output.md"))
    mock_writer_cls = MagicMock(return_value=mock_writer_instance)

    # Mock fitz.open to prevent real PDF file access during tests.
    mock_fitz_doc = MagicMock()
    mock_fitz_open = MagicMock(return_value=mock_fitz_doc)

    patchers = {
        "analyse": patch("pdf2md.analyser.analyze_pdf", mock_analyse),
        "extract": patch("pdf2md.images.extract_images", mock_extract),
        "ocr": patch("pdf2md.ocr.OCREngine", mock_ocr_cls),
        "builder": patch("pdf2md.builder.MarkdownBuilder", mock_builder_cls),
        "writer": patch("pdf2md.output.OutputWriter", mock_writer_cls),
        "fitz_open": patch("fitz.open", mock_fitz_open),
    }

    mocks: dict[str, MagicMock] = {}
    for name, p in patchers.items():
        mocks[name] = p.start()

    return mocks


def _stop_all_patches() -> None:
    """Stop all active patchers."""
    patch.stopall()


# ---------------------------------------------------------------------------
# 1. CLI Argument Parsing tests
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Tests for ``parse_args`` — verify argparse configuration."""

    def test_positional_input(self):
        args = parse_args(["document.pdf"])
        assert args.input == "document.pdf"

    def test_output_flag_short(self):
        args = parse_args(["doc.pdf", "-o", "out.md"])
        assert args.output == "out.md"

    def test_output_flag_long(self):
        args = parse_args(["doc.pdf", "--output", "out.zip"])
        assert args.output == "out.zip"

    def test_output_dir_flag(self):
        args = parse_args(["doc.pdf", "--output-dir", "./output/"])
        assert args.output_dir == "./output/"

    def test_min_image_size_default(self):
        args = parse_args(["doc.pdf"])
        assert args.min_image_size == "50x50"

    def test_min_image_size_custom(self):
        args = parse_args(["doc.pdf", "--min-image-size", "100x200"])
        assert args.min_image_size == "100x200"

    def test_ocr_lang_default(self):
        args = parse_args(["doc.pdf"])
        assert args.ocr_lang == "auto"

    def test_ocr_lang_en(self):
        args = parse_args(["doc.pdf", "--ocr-lang", "en"])
        assert args.ocr_lang == "en"

    def test_ocr_lang_ch_sim(self):
        args = parse_args(["doc.pdf", "--ocr-lang", "ch_sim"])
        assert args.ocr_lang == "ch_sim"

    def test_ocr_lang_ch_tra(self):
        args = parse_args(["doc.pdf", "--ocr-lang", "ch_tra"])
        assert args.ocr_lang == "ch_tra"

    def test_skip_ocr_default_false(self):
        args = parse_args(["doc.pdf"])
        assert args.skip_ocr is False

    def test_skip_ocr_flag(self):
        args = parse_args(["doc.pdf", "--skip-ocr"])
        assert args.skip_ocr is True

    def test_verbose_default_false(self):
        args = parse_args(["doc.pdf"])
        assert args.verbose is False

    def test_verbose_flag(self):
        args = parse_args(["doc.pdf", "--verbose"])
        assert args.verbose is True

    def test_quiet_default_false(self):
        args = parse_args(["doc.pdf"])
        assert args.quiet is False

    def test_quiet_flag(self):
        args = parse_args(["doc.pdf", "--quiet"])
        assert args.quiet is True

    def test_combined_flags(self):
        args = parse_args(
            [
                "doc.pdf",
                "-o",
                "result.md",
                "--ocr-lang",
                "en",
                "--skip-ocr",
                "--verbose",
                "--min-image-size",
                "80x80",
            ]
        )
        assert args.input == "doc.pdf"
        assert args.output == "result.md"
        assert args.ocr_lang == "en"
        assert args.skip_ocr is True
        assert args.verbose is True
        assert args.min_image_size == "80x80"

    def test_version_flag_exits(self, capsys):
        """--version prints version and raises SystemExit(0)."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["doc.pdf", "--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "pdf2md" in captured.out

    def test_help_flag_exits(self, capsys):
        """--help prints usage and raises SystemExit(0)."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "pdf2md" in captured.out
        assert "input" in captured.out


# ---------------------------------------------------------------------------
# 2. CLI Validation tests
# ---------------------------------------------------------------------------


class TestValidateArgs:
    """Tests for ``validate_args`` — check constraint enforcement."""

    def test_valid_input(self, fake_pdf: Path):
        is_valid, error, code = validate_args(parse_args([str(fake_pdf)]))
        assert is_valid is True
        assert error is None
        assert code == EXIT_SUCCESS

    def test_missing_input_file(self):
        is_valid, error, code = validate_args(
            parse_args(["/nonexistent/file.pdf"])
        )
        assert is_valid is False
        assert code == EXIT_INPUT_NOT_FOUND
        assert "not found" in (error or "")

    def test_non_pdf_file(self, fake_non_pdf: Path):
        is_valid, error, code = validate_args(parse_args([str(fake_non_pdf)]))
        assert is_valid is False
        assert code == EXIT_INPUT_NOT_FOUND
        assert "must be a PDF" in (error or "")

    def test_conflicting_output_and_output_dir(self, fake_pdf: Path):
        is_valid, error, code = validate_args(
            parse_args([str(fake_pdf), "-o", "out.md", "--output-dir", "./out/"])
        )
        assert is_valid is False
        assert code == EXIT_INVALID_USAGE
        assert "both --output and --output-dir" in (error or "")

    def test_invalid_min_image_size_format(self, fake_pdf: Path):
        is_valid, error, code = validate_args(
            parse_args([str(fake_pdf), "--min-image-size", "abc"])
        )
        assert is_valid is False
        assert code == EXIT_INVALID_USAGE
        assert "Invalid --min-image-size" in (error or "")

    def test_invalid_min_image_size_partial(self, fake_pdf: Path):
        is_valid, error, code = validate_args(
            parse_args([str(fake_pdf), "--min-image-size", "50"])
        )
        assert is_valid is False
        assert code == EXIT_INVALID_USAGE

    def test_input_path_is_directory(self, tmp_path: Path):
        is_valid, error, code = validate_args(parse_args([str(tmp_path)]))
        assert is_valid is False
        assert code == EXIT_INPUT_NOT_FOUND
        assert "not a file" in (error or "")

    def test_valid_with_all_output_options(self, fake_pdf: Path):
        """Output + verbose + skip-ocr should all validate."""
        is_valid, error, code = validate_args(
            parse_args(
                [
                    str(fake_pdf),
                    "-o",
                    "out.zip",
                    "--verbose",
                    "--skip-ocr",
                    "--min-image-size",
                    "100x100",
                ]
            )
        )
        assert is_valid is True
        assert error is None
        assert code == EXIT_SUCCESS


# ---------------------------------------------------------------------------
# 3. Helper function tests
# ---------------------------------------------------------------------------


class TestParseMinImageSize:
    """Tests for the ``_parse_min_image_size`` helper."""

    def test_50x50(self):
        assert _parse_min_image_size("50x50") == (50, 50)

    def test_100x200(self):
        assert _parse_min_image_size("100x200") == (100, 200)

    def test_0x0(self):
        assert _parse_min_image_size("0x0") == (0, 0)

    def test_large_values(self):
        assert _parse_min_image_size("1920x1080") == (1920, 1080)

    def test_asymmetric(self):
        assert _parse_min_image_size("1x999") == (1, 999)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            _parse_min_image_size("no-x-here")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            _parse_min_image_size("axb")


class TestHasScanPages:
    """Tests for the ``_has_scan_pages`` helper."""

    def test_all_text_pages_returns_false(self, mock_text_analysis: DocumentAnalysis):
        assert _has_scan_pages(mock_text_analysis) is False

    def test_all_scan_pages_returns_true(self, mock_scan_analysis: DocumentAnalysis):
        assert _has_scan_pages(mock_scan_analysis) is True

    def test_mixed_pages_returns_true(self, mock_mixed_analysis: DocumentAnalysis):
        assert _has_scan_pages(mock_mixed_analysis) is True

    def test_empty_pages_returns_false(self):
        analysis = DocumentAnalysis(
            total_pages=0,
            pages=[],
            file_size_bytes=0,
            file_path="/empty.pdf",
        )
        assert _has_scan_pages(analysis) is False


# ---------------------------------------------------------------------------
# 4. Full pipeline integration tests (mocked)
# ---------------------------------------------------------------------------


class TestFullPipelineTextPdf:
    """Pipeline tests for text-only PDFs (no OCR triggered)."""

    def test_text_pdf_full_pipeline(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Text-only PDF should complete successfully without OCR."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
            mocks["analyse"].assert_called_once()
            mocks["extract"].assert_called_once()
            # OCR should NOT be called for text-only PDF
            mocks["ocr"].assert_not_called()
            mocks["builder"].return_value.build.assert_called_once()
            mocks["builder"].return_value.build_with_ocr.assert_not_called()
            mocks["writer"].return_value.write.assert_called_once()
        finally:
            _stop_all_patches()

    def test_text_pdf_with_skip_ocr(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Text-only PDF with --skip-ocr should still succeed."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out), "--skip-ocr"])
            assert exit_code == EXIT_SUCCESS
            mocks["ocr"].assert_not_called()
        finally:
            _stop_all_patches()

    def test_text_pdf_default_output(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis, monkeypatch
    ):
        """Text-only PDF with auto-named output (no -o flag)."""
        monkeypatch.chdir(tmp_path)
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = tmp_path / "doc.md"

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_SUCCESS
        finally:
            _stop_all_patches()


class TestFullPipelineScannedPdf:
    """Pipeline tests for scanned PDFs (OCR triggered)."""

    def test_scanned_pdf_triggers_ocr(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Scanned PDF should trigger OCR engine initialisation."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_scan_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
            mocks["ocr"].assert_called_once()
            mocks["builder"].return_value.build_with_ocr.assert_called_once()
            mocks["builder"].return_value.build.assert_not_called()
        finally:
            _stop_all_patches()

    def test_scanned_pdf_skip_ocr(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Scanned PDF with --skip-ocr should NOT run OCR."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_scan_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out), "--skip-ocr"])
            assert exit_code == EXIT_SUCCESS
            mocks["ocr"].assert_not_called()
            mocks["builder"].return_value.build.assert_called_once()
        finally:
            _stop_all_patches()

    def test_scanned_pdf_ocr_lang_passed(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """OCR engine should receive the language hint from CLI."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_scan_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            main([str(pdf), "-o", str(out), "--ocr-lang", "en"])
            mocks["ocr"].assert_called_once_with(lang="en")
        finally:
            _stop_all_patches()


class TestFullPipelineMixedPdf:
    """Pipeline tests for mixed documents (text + scanned pages)."""

    def test_mixed_pdf_triggers_ocr(
        self, tmp_path: Path, mock_mixed_analysis: DocumentAnalysis
    ):
        """Mixed PDF should trigger OCR for scan pages."""
        pdf = tmp_path / "mixed.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_mixed_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
            mocks["ocr"].assert_called_once()
            mocks["builder"].return_value.build_with_ocr.assert_called_once()
        finally:
            _stop_all_patches()


class TestFullPipelineWithImages:
    """Pipeline tests involving image extraction."""

    def test_pdf_with_images_produces_zip(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """PDF with images and no -o should auto-produce a .zip."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        from pdf2md.images import ExtractedImage

        images = [
            ExtractedImage(
                page_number=1,
                image_index=1,
                filename="page1_img1.png",
                width=200,
                height=150,
                y0=100.0,
                data=b"\x89PNG\r\n\x1a\nfake",
            ),
        ]

        mocks = _patch_pipeline_mocks(mock_text_analysis, images=images)
        mocks["analyse"].return_value.file_path = str(pdf)
        zip_path = tmp_path / "doc.zip"
        mocks["writer"].return_value.write.return_value = zip_path

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_SUCCESS
        finally:
            _stop_all_patches()

    def test_pdf_with_images_and_output_dir(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """PDF with images and --output-dir should write to directory."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        from pdf2md.images import ExtractedImage

        images = [
            ExtractedImage(
                page_number=1,
                image_index=1,
                filename="page1_img1.png",
                width=200,
                height=150,
                y0=100.0,
                data=b"imgdata",
            ),
        ]

        out_dir = tmp_path / "output"
        mocks = _patch_pipeline_mocks(mock_text_analysis, images=images)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out_dir

        try:
            exit_code = main([str(pdf), "--output-dir", str(out_dir)])
            assert exit_code == EXIT_SUCCESS
            # OutputWriter should be constructed with output_dir
            mocks["writer"].assert_called_once_with(
                output_path=None,
                output_dir=str(out_dir),
            )
        finally:
            _stop_all_patches()

    def test_image_extraction_failure_returns_conversion_error(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """If extract_images raises, return EXIT_CONVERSION_FAILURE."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(
            mock_text_analysis,
            extract_images_error=RuntimeError("Image extraction failed"),
        )
        mocks["analyse"].return_value.file_path = str(pdf)

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_CONVERSION_FAILURE
        finally:
            _stop_all_patches()


class TestFullPipelineOutputModes:
    """Tests for different output mode scenarios."""

    def test_output_dir_mode(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """--output-dir should pass directory to OutputWriter."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out_dir = tmp_path / "output"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out_dir

        try:
            exit_code = main([str(pdf), "--output-dir", str(out_dir)])
            assert exit_code == EXIT_SUCCESS
            mocks["writer"].assert_called_once_with(
                output_path=None,
                output_dir=str(out_dir),
            )
        finally:
            _stop_all_patches()

    def test_explicit_md_output(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Explicit -o out.md should pass path to OutputWriter."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "result.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
            mocks["writer"].assert_called_once_with(
                output_path=str(out),
                output_dir=None,
            )
        finally:
            _stop_all_patches()

    def test_explicit_zip_output(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Explicit -o out.zip should pass path to OutputWriter."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "result.zip"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
            mocks["writer"].assert_called_once_with(
                output_path=str(out),
                output_dir=None,
            )
        finally:
            _stop_all_patches()


# ---------------------------------------------------------------------------
# 5. Exit code tests
# ---------------------------------------------------------------------------


class TestExitCodes:
    """Verify correct exit codes for all error scenarios."""

    def test_success_exit_code_0(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Successful conversion returns EXIT_SUCCESS (0)."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
        finally:
            _stop_all_patches()

    def test_input_not_found_exit_code_3(self):
        """Non-existent input returns EXIT_INPUT_NOT_FOUND (3)."""
        exit_code = main(["/nonexistent/path/file.pdf"])
        assert exit_code == EXIT_INPUT_NOT_FOUND

    def test_conflicting_flags_exit_code_2(self, fake_pdf: Path):
        """--output + --output-dir returns EXIT_INVALID_USAGE (2)."""
        exit_code = main(
            [str(fake_pdf), "-o", "out.md", "--output-dir", "./out/"]
        )
        assert exit_code == EXIT_INVALID_USAGE

    def test_output_not_writable_exit_code_5(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Output validation failure returns EXIT_OUTPUT_NOT_WRITABLE (5)."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.validate_output = MagicMock(
            return_value=(False, "Permission denied")
        )

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_OUTPUT_NOT_WRITABLE
        finally:
            _stop_all_patches()

    def test_ocr_model_missing_exit_code_6(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """OCR initialisation failure returns EXIT_OCR_MODEL_NOT_FOUND (6)."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(
            mock_scan_analysis,
            ocr_error=RuntimeError("RapidOCR models not found"),
        )
        mocks["analyse"].return_value.file_path = str(pdf)

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_OCR_MODEL_NOT_FOUND
        finally:
            _stop_all_patches()

    def test_ocr_unexpected_error_exit_code_6(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Unexpected OCR error also returns EXIT_OCR_MODEL_NOT_FOUND (6)."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(
            mock_scan_analysis,
            ocr_error=Exception("Unexpected crash"),
        )
        mocks["analyse"].return_value.file_path = str(pdf)

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_OCR_MODEL_NOT_FOUND
        finally:
            _stop_all_patches()

    def test_conversion_failure_exit_code_4(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Generic RuntimeError returns EXIT_CONVERSION_FAILURE (4)."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["analyse"].side_effect = RuntimeError(
            "Conversion pipeline crashed"
        )

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_CONVERSION_FAILURE
        finally:
            _stop_all_patches()

    def test_generic_failure_exit_code_1(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Unexpected exception returns EXIT_GENERIC_FAILURE (1)."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["analyse"].side_effect = ValueError(
            "Unexpected value error"
        )

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_GENERIC_FAILURE
        finally:
            _stop_all_patches()


# ---------------------------------------------------------------------------
# 6. End-to-end flow tests (scenario-based)
# ---------------------------------------------------------------------------


class TestEndToEndScenarios:
    """Scenario-based end-to-end tests covering real-world usage patterns."""

    def test_scenario_text_only_no_images_no_ocr(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """Text-only PDF: no OCR, no images, outputs .md."""
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "report.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out), "--verbose"])
            assert exit_code == EXIT_SUCCESS
            mocks["ocr"].assert_not_called()
            mocks["builder"].return_value.build.assert_called_once()
        finally:
            _stop_all_patches()

    def test_scenario_scanned_with_ocr(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Scanned PDF: OCR runs, build_with_ocr called."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "scanned.md"

        mocks = _patch_pipeline_mocks(mock_scan_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out), "--ocr-lang", "en"])
            assert exit_code == EXIT_SUCCESS
            mocks["ocr"].assert_called_once_with(lang="en")
            mocks["builder"].return_value.build_with_ocr.assert_called_once()
        finally:
            _stop_all_patches()

    def test_scenario_mixed_document(
        self, tmp_path: Path, mock_mixed_analysis: DocumentAnalysis
    ):
        """Mixed document: OCR for scan pages, build_with_ocr for all."""
        pdf = tmp_path / "mixed.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "mixed.md"

        mocks = _patch_pipeline_mocks(mock_mixed_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
            # OCR should be called because there are scan pages
            mocks["ocr"].assert_called_once()
            mocks["builder"].return_value.build_with_ocr.assert_called_once()
        finally:
            _stop_all_patches()

    def test_scenario_skip_ocr_on_scanned(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Scanned PDF with --skip-ocr: OCR skipped, plain build."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_scan_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out), "--skip-ocr"])
            assert exit_code == EXIT_SUCCESS
            mocks["ocr"].assert_not_called()
            mocks["builder"].return_value.build.assert_called_once()
        finally:
            _stop_all_patches()

    def test_scenario_output_directory_mode(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """--output-dir writes to a directory instead of a file."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out_dir = tmp_path / "output_dir"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out_dir

        try:
            exit_code = main([str(pdf), "--output-dir", str(out_dir)])
            assert exit_code == EXIT_SUCCESS
            mocks["writer"].assert_called_once_with(
                output_path=None,
                output_dir=str(out_dir),
            )
        finally:
            _stop_all_patches()

    def test_scenario_verbose_logging_enabled(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """--verbose flag should not affect pipeline success."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out), "--verbose"])
            assert exit_code == EXIT_SUCCESS
        finally:
            _stop_all_patches()

    def test_scenario_quiet_mode(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """--quiet flag should not affect pipeline success."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out), "--quiet"])
            assert exit_code == EXIT_SUCCESS
        finally:
            _stop_all_patches()

    def test_scenario_custom_min_image_size(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """--min-image-size should be parsed and passed to extract_images."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main(
                [str(pdf), "-o", str(out), "--min-image-size", "100x100"]
            )
            assert exit_code == EXIT_SUCCESS
            # extract_images should be called with min_width=100, min_height=100
            mocks["extract"].assert_called_once()
            call_args = mocks["extract"].call_args
            assert call_args[0][1] == 100  # min_width
            assert call_args[0][2] == 100  # min_height
        finally:
            _stop_all_patches()

    def test_scenario_analyze_pdf_called(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """analyze_pdf should be called with the input path."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            main([str(pdf), "-o", str(out)])
            mocks["analyse"].assert_called_once_with(str(pdf))
        finally:
            _stop_all_patches()

    def test_scenario_builder_configured_correctly(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """MarkdownBuilder should be created with default config."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            main([str(pdf), "-o", str(out)])
            mocks["builder"].assert_called_once_with(
                add_page_breaks=False,
                max_heading_level=4,
            )
        finally:
            _stop_all_patches()


# ---------------------------------------------------------------------------
# 7. Edge cases and error propagation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and unusual input scenarios."""

    def test_empty_pdf_zero_pages(self, tmp_path: Path):
        """PDF with zero pages should still complete successfully."""
        analysis = DocumentAnalysis(
            total_pages=0,
            pages=[],
            file_size_bytes=100,
            file_path="/empty.pdf",
        )
        pdf = tmp_path / "empty.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
        finally:
            _stop_all_patches()

    def test_multi_page_text_pdf(self, tmp_path: Path):
        """Multi-page text PDF should process all pages."""
        analysis = DocumentAnalysis(
            total_pages=5,
            pages=[
                PageAnalysis(
                    page_number=i,
                    mode=PageMode.TEXT,
                    text_blocks=[
                        TextBlock(
                            text=f"Page {i} content",
                            x0=10,
                            y0=10,
                            x1=100,
                            y1=20,
                            font_size=12.0,
                            font_name="Arial",
                        ),
                    ],
                )
                for i in range(1, 6)
            ],
            file_size_bytes=10000,
            file_path="/multi.pdf",
        )
        pdf = tmp_path / "multi.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            exit_code = main([str(pdf), "-o", str(out)])
            assert exit_code == EXIT_SUCCESS
            assert len(analysis.pages) == 5
        finally:
            _stop_all_patches()

    def test_file_not_found_inside_pipeline(self, tmp_path: Path):
        """FileNotFoundError in pipeline returns EXIT_INPUT_NOT_FOUND."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mock_analyse = MagicMock(
            side_effect=FileNotFoundError("PDF vanished")
        )

        patchers = [
            patch("pdf2md.analyser.analyze_pdf", mock_analyse),
            patch("pdf2md.images.extract_images", MagicMock(return_value=[])),
            patch("pdf2md.ocr.OCREngine", MagicMock()),
            patch("pdf2md.builder.MarkdownBuilder", MagicMock()),
            patch("pdf2md.output.OutputWriter", MagicMock()),
            patch("fitz.open", MagicMock()),
        ]
        for p in patchers:
            p.start()

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_INPUT_NOT_FOUND
        finally:
            patch.stopall()

    def test_rapidocr_specific_error_exit_code_6(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Error message containing 'RapidOCR' returns EXIT_OCR_MODEL_NOT_FOUND."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(
            mock_scan_analysis,
            ocr_error=RuntimeError("RapidOCR model file corrupted"),
        )
        mocks["analyse"].return_value.file_path = str(pdf)

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_OCR_MODEL_NOT_FOUND
        finally:
            _stop_all_patches()

    def test_lowercase_rapidocr_error_exit_code_6(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Error message containing 'rapidocr' (lowercase) returns exit 6."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mocks = _patch_pipeline_mocks(
            mock_scan_analysis,
            ocr_error=RuntimeError("rapidocr backend unavailable"),
        )
        mocks["analyse"].return_value.file_path = str(pdf)

        try:
            exit_code = main([str(pdf)])
            assert exit_code == EXIT_OCR_MODEL_NOT_FOUND
        finally:
            _stop_all_patches()


# ---------------------------------------------------------------------------
# 8. CLI main() argument passthrough tests
# ---------------------------------------------------------------------------


class TestMainArgumentPassthrough:
    """Verify that CLI arguments are correctly passed through the pipeline."""

    def test_ocr_lang_auto_passed_to_engine(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """Default 'auto' lang should be passed to OCREngine."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_scan_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            main([str(pdf), "-o", str(out)])
            mocks["ocr"].assert_called_once_with(lang="auto")
        finally:
            _stop_all_patches()

    def test_ocr_lang_ch_sim_passed_to_engine(
        self, tmp_path: Path, mock_scan_analysis: DocumentAnalysis
    ):
        """'ch_sim' lang should be passed to OCREngine."""
        pdf = tmp_path / "scanned.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_scan_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            main([str(pdf), "-o", str(out), "--ocr-lang", "ch_sim"])
            mocks["ocr"].assert_called_once_with(lang="ch_sim")
        finally:
            _stop_all_patches()

    def test_min_image_size_80x60_passed_to_extract(
        self, tmp_path: Path, mock_text_analysis: DocumentAnalysis
    ):
        """--min-image-size 80x60 should be parsed and passed to extract_images."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "out.md"

        mocks = _patch_pipeline_mocks(mock_text_analysis)
        mocks["analyse"].return_value.file_path = str(pdf)
        mocks["writer"].return_value.write.return_value = out

        try:
            main([str(pdf), "-o", str(out), "--min-image-size", "80x60"])
            call_args = mocks["extract"].call_args
            assert call_args[0][1] == 80
            assert call_args[0][2] == 60
        finally:
            _stop_all_patches()
