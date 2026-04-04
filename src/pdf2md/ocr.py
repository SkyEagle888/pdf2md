"""OCR module using RapidOCR engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from pdf2md.logging import get_logger

# Language hint mapping: user-friendly names → RapidOCR lang codes
_LANG_MAP: dict[str, str | None] = {
    "en": "en",
    "ch_sim": "ch",
    "ch_tra": "chinese_cht",
    "auto": None,  # Use RapidOCR default (Chinese + English)
}

# Minimum confidence threshold for including a result
_CONFIDENCE_THRESHOLD = 0.3


@dataclass
class OCRResult:
    """Result from OCR processing for a single text block."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float


@dataclass
class PageOCRResult:
    """OCR result for an entire page."""

    page_number: int  # 1-based
    results: list[OCRResult] = field(default_factory=list)
    full_text: str = ""


def _lang_to_rapidocr(lang: str) -> str | None:
    """Map user-friendly language hint to RapidOCR lang code.

    Args:
        lang: Language hint — 'en', 'ch_sim', 'ch_tra', 'auto'

    Returns:
        RapidOCR lang code string, or None to use default

    Raises:
        ValueError: If language hint is not supported
    """
    if lang not in _LANG_MAP:
        supported = ", ".join(sorted(_LANG_MAP.keys()))
        raise ValueError(
            f"Unsupported OCR language hint: '{lang}'. Supported: {supported}"
        )
    return _LANG_MAP[lang]


def pixmap_to_pil(pixmap: Any) -> Image.Image:
    """Convert a fitz.Pixmap to a PIL Image.

    Args:
        pixmap: fitz.Pixmap to convert

    Returns:
        PIL Image in RGB mode
    """
    import fitz  # noqa: PLC0415

    # Ensure RGB colourspace
    if pixmap.n < 3:
        pixmap = fitz.Pixmap(fitz.csRGB, pixmap)

    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def pixmap_to_numpy(pixmap: Any) -> np.ndarray:
    """Convert a fitz.Pixmap to a numpy array (H, W, C).

    Args:
        pixmap: fitz.Pixmap to convert

    Returns:
        Numpy array of shape (height, width, channels) dtype uint8
    """
    import fitz  # noqa: PLC0415

    # Ensure RGB colourspace
    if pixmap.n < 3:
        pixmap = fitz.Pixmap(fitz.csRGB, pixmap)

    samples = np.frombuffer(pixmap.samples, dtype=np.uint8)
    return samples.reshape(pixmap.height, pixmap.width, pixmap.n)


class OCREngine:
    """RapidOCR wrapper with language support."""

    def __init__(self, lang: str = "auto") -> None:
        """Initialize OCR engine.

        Args:
            lang: Language hint — 'en', 'ch_sim', 'ch_tra', 'auto'

        Raises:
            ValueError: If language hint is not supported
            RuntimeError: If RapidOCR models cannot be loaded
        """
        if lang not in _LANG_MAP:
            supported = ", ".join(sorted(_LANG_MAP.keys()))
            raise ValueError(
                f"Unsupported OCR language hint: '{lang}'. Supported: {supported}"
            )

        self.lang = lang
        self._rapidocr_lang = _lang_to_rapidocr(lang)
        self._engine: Any | None = None
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        """Load RapidOCR engine with appropriate models.

        Raises:
            RuntimeError: If the engine cannot be imported or initialised
        """
        logger = get_logger()

        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "rapidocr-onnxruntime is not installed. "
                "Run: uv pip install rapidocr-onnxruntime"
            ) from exc

        try:
            kwargs: dict[str, Any] = {}
            if self._rapidocr_lang is not None:
                kwargs["lang"] = self._rapidocr_lang

            self._engine = RapidOCR(**kwargs)
            lang_display = self._rapidocr_lang if self._rapidocr_lang else "default (auto)"
            logger.debug(f"RapidOCR engine initialised (lang: {lang_display})")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise RapidOCR engine: {exc}"
            ) from exc

    def _run_ocr(self, image: np.ndarray | Image.Image) -> list[list[Any]] | None:
        """Run OCR on a numpy array or PIL Image.

        Args:
            image: Input image as numpy array (H, W, C) or PIL Image

        Returns:
            Raw RapidOCR result list, or None on failure
        """
        if self._engine is None:
            return None

        try:
            result, _elapsed = self._engine(image)
            return result
        except Exception as exc:
            get_logger().warning(f"OCR inference failed: {exc}")
            return None

    def process_pixmap(self, pixmap: Any, page_number: int = 0) -> PageOCRResult:
        """Process a fitz.Pixmap with OCR.

        Args:
            pixmap: fitz.Pixmap to process
            page_number: Page number (1-based) for logging

        Returns:
            PageOCRResult with extracted text and metadata
        """
        try:
            img_array = pixmap_to_numpy(pixmap)
        except Exception as exc:
            get_logger().warning(
                f"Page {page_number}: Failed to convert pixmap for OCR: {exc}"
            )
            return PageOCRResult(page_number=page_number)

        return self._process_image(img_array, page_number)

    def process_pil_image(self, image: Image.Image, page_number: int = 0) -> PageOCRResult:
        """Process a PIL Image with OCR.

        Args:
            image: PIL Image to process
            page_number: Page number (1-based) for logging

        Returns:
            PageOCRResult with extracted text and metadata
        """
        # Convert to numpy for RapidOCR
        img_array = np.array(image.convert("RGB"))
        return self._process_image(img_array, page_number)

    def _process_image(
        self, image: np.ndarray, page_number: int
    ) -> PageOCRResult:
        """Run OCR on a numpy image and build PageOCRResult.

        Args:
            image: Numpy array of shape (H, W, C) dtype uint8
            page_number: Page number (1-based) for logging

        Returns:
            PageOCRResult sorted top-to-bottom by y0
        """
        logger = get_logger()

        raw = self._run_ocr(image)

        if raw is None:
            logger.warning(f"Page {page_number}: OCR returned no results")
            return PageOCRResult(page_number=page_number)

        results: list[OCRResult] = []

        for item in raw:
            # RapidOCR result format:
            # [
            #   [[x0,y0], [x1,y1], [x2,y2], [x3,y3]],  # box corners
            #   "text",                                   # recognised text
            #   confidence,                               # 0.0–1.0
            # ]
            if len(item) < 3:
                continue

            box = item[0]
            text = item[1]
            confidence = float(item[2])

            # Filter out very low confidence results
            if confidence < _CONFIDENCE_THRESHOLD:
                logger.debug(
                    f"Page {page_number}: Filtering low-confidence result "
                    f"(conf={confidence:.2f}): {text!r}"
                )
                continue

            # Skip empty / whitespace-only text
            if not text or not text.strip():
                continue

            # Compute bounding box from corner points
            # box = [[x0,y0], [x1,y1], [x2,y2], [x3,y3]] in reading order
            try:
                x_coords = [float(p[0]) for p in box]
                y_coords = [float(p[1]) for p in box]
                x0 = min(x_coords)
                y0 = min(y_coords)
                x1 = max(x_coords)
                y1 = max(y_coords)
            except (IndexError, TypeError, ValueError) as exc:
                logger.debug(
                    f"Page {page_number}: Malformed box in OCR result: {exc}"
                )
                continue

            results.append(
                OCRResult(
                    text=text.strip(),
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    confidence=confidence,
                )
            )

        # Sort top-to-bottom by y0
        results.sort(key=lambda r: r.y0)

        full_text = "\n".join(r.text for r in results)

        logger.info(
            f"Page {page_number}: OCR found {len(results)} text block(s)"
        )

        return PageOCRResult(
            page_number=page_number,
            results=results,
            full_text=full_text,
        )
