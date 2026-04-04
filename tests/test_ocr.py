"""Tests for pdf2md OCR module."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from pdf2md.ocr import (
    _CONFIDENCE_THRESHOLD,
    _LANG_MAP,
    OCRResult,
    OCREngine,
    PageOCRResult,
    _lang_to_rapidocr,
    pixmap_to_numpy,
    pixmap_to_pil,
)


# ---------------------------------------------------------------------------
# Helper constants
# ---------------------------------------------------------------------------

# Minimal valid PDF bytes for creating temporary test files
_MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"trailer<</Root 1 0 R/Size 4>>\n%%EOF"
)

# Patch target — RapidOCR is imported lazily inside _initialize_engine
_RAPIDOCR_PATCH = "rapidocr_onnxruntime.RapidOCR"


# ---------------------------------------------------------------------------
# Language mapping tests
# ---------------------------------------------------------------------------


class TestLangToRapidocr:
    def test_en(self):
        assert _lang_to_rapidocr("en") == "en"

    def test_ch_sim(self):
        assert _lang_to_rapidocr("ch_sim") == "ch"

    def test_ch_tra(self):
        assert _lang_to_rapidocr("ch_tra") == "chinese_cht"

    def test_auto_returns_none(self):
        assert _lang_to_rapidocr("auto") is None

    def test_unsupported_language_raises(self):
        with pytest.raises(ValueError, match="Unsupported OCR language"):
            _lang_to_rapidocr("french")


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestOCRResult:
    def test_creation(self):
        result = OCRResult(
            text="Hello",
            x0=10.0,
            y0=20.0,
            x1=100.0,
            y1=30.0,
            confidence=0.95,
        )
        assert result.text == "Hello"
        assert result.x0 == 10.0
        assert result.confidence == 0.95

    def test_dataclass_equality(self):
        r1 = OCRResult("test", 0, 0, 10, 10, 0.9)
        r2 = OCRResult("test", 0, 0, 10, 10, 0.9)
        assert r1 == r2


class TestPageOCRResult:
    def test_defaults(self):
        page = PageOCRResult(page_number=1)
        assert page.results == []
        assert page.full_text == ""

    def test_with_data(self):
        results = [
            OCRResult("Line 1", 0, 10, 100, 20, 0.9),
            OCRResult("Line 2", 0, 30, 100, 40, 0.8),
        ]
        page = PageOCRResult(
            page_number=2,
            results=results,
            full_text="Line 1\nLine 2",
        )
        assert page.page_number == 2
        assert len(page.results) == 2
        assert page.full_text == "Line 1\nLine 2"


# ---------------------------------------------------------------------------
# OCREngine initialisation tests
# ---------------------------------------------------------------------------


class TestOCREngineInit:
    def test_default_language(self):
        with patch(_RAPIDOCR_PATCH) as mock_rapidocr:
            mock_rapidocr.return_value = MagicMock()
            engine = OCREngine()
            assert engine.lang == "auto"
            mock_rapidocr.assert_called_once_with()

    def test_english_language(self):
        with patch(_RAPIDOCR_PATCH) as mock_rapidocr:
            mock_rapidocr.return_value = MagicMock()
            engine = OCREngine(lang="en")
            assert engine.lang == "en"
            mock_rapidocr.assert_called_once_with(lang="en")

    def test_chinese_simplified(self):
        with patch(_RAPIDOCR_PATCH) as mock_rapidocr:
            mock_rapidocr.return_value = MagicMock()
            engine = OCREngine(lang="ch_sim")
            assert engine.lang == "ch_sim"
            mock_rapidocr.assert_called_once_with(lang="ch")

    def test_chinese_traditional(self):
        with patch(_RAPIDOCR_PATCH) as mock_rapidocr:
            mock_rapidocr.return_value = MagicMock()
            engine = OCREngine(lang="ch_tra")
            mock_rapidocr.assert_called_once_with(lang="chinese_cht")

    def test_unsupported_language_raises(self):
        with pytest.raises(ValueError, match="Unsupported OCR language"):
            OCREngine(lang="french")

    def test_rapidocr_initialisation_failure_raises(self):
        with patch(_RAPIDOCR_PATCH) as mock_rapidocr:
            mock_rapidocr.side_effect = Exception("Model download failed")
            with pytest.raises(RuntimeError, match="Failed to initialise"):
                OCREngine()


# ---------------------------------------------------------------------------
# Image conversion utility tests
# ---------------------------------------------------------------------------


class TestPixmapToPil:
    def test_grayscale_converted_to_rgb(self):
        """Grayscale pixmaps (n=1) should be converted to RGB before PIL."""
        import fitz  # noqa: PLC0415

        # Create a small grayscale pixmap
        page = fitz.open(stream=_MINIMAL_PDF, filetype="pdf")[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1))
        # Force grayscale by creating a new grayscale pixmap
        gray = fitz.Pixmap(fitz.csGRAY, pixmap)

        result = pixmap_to_pil(gray)
        assert result.mode == "RGB"
        assert result.size == (gray.width, gray.height)

    def test_rgb_pixmap(self):
        """RGB pixmaps should convert directly."""
        import fitz  # noqa: PLC0415

        page = fitz.open(stream=_MINIMAL_PDF, filetype="pdf")[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1))
        result = pixmap_to_pil(pixmap)
        assert result.mode == "RGB"


class TestPixmapToNumpy:
    def test_returns_correct_shape(self):
        """Numpy array should be (H, W, C)."""
        import fitz  # noqa: PLC0415

        page = fitz.open(stream=_MINIMAL_PDF, filetype="pdf")[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1))
        arr = pixmap_to_numpy(pixmap)
        assert arr.shape == (pixmap.height, pixmap.width, pixmap.n)
        assert arr.dtype == np.uint8

    def test_grayscale_converted_to_rgb(self):
        """Grayscale pixmaps should be converted to RGB (3 channels)."""
        import fitz  # noqa: PLC0415

        page = fitz.open(stream=_MINIMAL_PDF, filetype="pdf")[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1))
        gray = fitz.Pixmap(fitz.csGRAY, pixmap)
        arr = pixmap_to_numpy(gray)
        assert arr.shape[2] == 3  # RGB


# ---------------------------------------------------------------------------
# OCREngine processing tests (mocked RapidOCR)
# ---------------------------------------------------------------------------


class _DummyRapidOCR:
    """Fake RapidOCR that returns predictable results."""

    def __init__(self, results: list | None = None, raise_on_call: bool = False):
        self._results = results
        self._raise = raise_on_call

    def __call__(self, image):
        if self._raise:
            raise RuntimeError("Simulated OCR failure")
        return self._results, 0.5  # (results, elapsed_time)


def _make_dummy_result(text: str, x: float, y: float, confidence: float = 0.9):
    """Create a single RapidOCR result item."""
    w, h = 100.0, 20.0
    box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    return [box, text, confidence]


class TestProcessPixmap:
    def _create_engine(
        self, ocr_results: list | None = None, raise_on_call: bool = False
    ):
        """Create OCREngine with a mocked RapidOCR backend."""
        engine = OCREngine.__new__(OCREngine)
        engine.lang = "en"
        engine._rapidocr_lang = "en"
        engine._engine = _DummyRapidOCR(ocr_results, raise_on_call)
        return engine

    def test_basic_ocr_extraction(self):
        raw = [_make_dummy_result("Hello World", 10, 20, 0.95)]
        eng = self._create_engine(raw)

        # Create a simple test image
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        assert result.page_number == 1
        assert len(result.results) == 1
        assert result.results[0].text == "Hello World"
        assert result.results[0].confidence == 0.95
        assert result.full_text == "Hello World"

    def test_multiple_lines_sorted_by_y0(self):
        raw = [
            _make_dummy_result("Bottom", 10, 60, 0.9),
            _make_dummy_result("Top", 10, 10, 0.95),
            _make_dummy_result("Middle", 10, 30, 0.85),
        ]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        texts = [r.text for r in result.results]
        assert texts == ["Top", "Middle", "Bottom"]

    def test_low_confidence_filtered(self):
        raw = [
            _make_dummy_result("Good", 10, 10, 0.9),
            _make_dummy_result("Bad", 10, 30, 0.1),  # below threshold
        ]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        assert len(result.results) == 1
        assert result.results[0].text == "Good"

    def test_empty_text_filtered(self):
        raw = [
            _make_dummy_result("   ", 10, 10, 0.9),
            _make_dummy_result("", 10, 30, 0.9),
        ]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        assert len(result.results) == 0
        assert result.full_text == ""

    def test_ocr_failure_returns_empty_result(self, caplog):
        eng = self._create_engine(raise_on_call=True)
        img = Image.new("RGB", (200, 100), color="white")

        with caplog.at_level(logging.WARNING):
            result = eng.process_pil_image(img, page_number=5)

        assert result.page_number == 5
        assert result.results == []
        assert result.full_text == ""
        assert "OCR returned no results" in caplog.text

    def test_none_engine_returns_empty(self):
        eng = OCREngine.__new__(OCREngine)
        eng.lang = "auto"
        eng._rapidocr_lang = None
        eng._engine = None

        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        assert result.results == []
        assert result.full_text == ""

    def test_full_text_concatenation(self):
        raw = [
            _make_dummy_result("First line", 10, 10, 0.9),
            _make_dummy_result("Second line", 10, 40, 0.85),
            _make_dummy_result("Third line", 10, 70, 0.8),
        ]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        assert result.full_text == "First line\nSecond line\nThird line"

    def test_malformed_box_skipped(self, caplog):
        raw = [
            [["bad", "data"], "text", 0.9],  # non-numeric coords
            _make_dummy_result("Valid", 10, 10, 0.9),
        ]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")

        with caplog.at_level(logging.DEBUG):
            result = eng.process_pil_image(img, page_number=1)

        assert len(result.results) == 1
        assert result.results[0].text == "Valid"
        assert "Malformed box" in caplog.text

    def test_incomplete_item_skipped(self):
        raw = [
            ["short"],  # len < 3, should be skipped
        ]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        assert len(result.results) == 0

    def test_text_stripped(self):
        raw = [_make_dummy_result("  padded text  ", 10, 10, 0.9)]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        assert result.results[0].text == "padded text"

    def test_bounding_box_computed_from_corners(self):
        # Irregular quadrilateral box
        box = [[10, 50], [110, 40], [120, 60], [5, 70]]
        raw = [[box, "test", 0.9]]
        eng = self._create_engine(raw)
        img = Image.new("RGB", (200, 100), color="white")
        result = eng.process_pil_image(img, page_number=1)

        r = result.results[0]
        assert r.x0 == 5.0
        assert r.y0 == 40.0
        assert r.x1 == 120.0
        assert r.y1 == 70.0


# ---------------------------------------------------------------------------
# Integration test with real pixmap (requires fitz)
# ---------------------------------------------------------------------------


class TestProcessPixmapIntegration:
    def test_process_pixmap_with_real_pixmap(self):
        """Test process_pixmap with a real fitz.Pixmap."""
        import fitz  # noqa: PLC0415

        page = fitz.open(stream=_MINIMAL_PDF, filetype="pdf")[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1))

        eng = OCREngine.__new__(OCREngine)
        eng.lang = "auto"
        eng._rapidocr_lang = None
        # Return empty result — we just verify no crash and correct structure
        eng._engine = _DummyRapidOCR([])

        result = eng.process_pixmap(pixmap, page_number=1)
        assert result.page_number == 1
        assert isinstance(result, PageOCRResult)


# ---------------------------------------------------------------------------
# Confidence threshold constant test
# ---------------------------------------------------------------------------


class TestConstants:
    def test_confidence_threshold(self):
        assert _CONFIDENCE_THRESHOLD == 0.3

    def test_lang_map_keys(self):
        assert set(_LANG_MAP.keys()) == {"en", "ch_sim", "ch_tra", "auto"}
