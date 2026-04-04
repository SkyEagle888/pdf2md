"""Image extraction from PDF documents."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image

from pdf2md.logging import get_logger


@dataclass
class ExtractedImage:
    """An image extracted from a PDF page."""

    page_number: int  # 1-based
    image_index: int  # 1-based on this page
    filename: str  # e.g., "page1_img2.png"
    width: int
    height: int
    y0: float  # Vertical position for insertion ordering
    data: bytes  # PNG bytes


def extract_images(
    doc: Any,  # fitz.Document
    min_width: int = 50,
    min_height: int = 50,
) -> list[ExtractedImage]:
    """Extract images from all pages of a PDF document.

    Args:
        doc: Open fitz.Document
        min_width: Minimum image width in pixels
        min_height: Minimum image height in pixels

    Returns:
        List of ExtractedImage objects (filtered by size)
    """
    import fitz  # noqa: PLC0415

    logger = get_logger()

    extracted: list[ExtractedImage] = []
    total_found = 0
    total_filtered = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_number = page_num + 1  # 1-based
        image_index = 0

        image_list = page.get_images(full=True)
        total_found += len(image_list)

        if not image_list:
            continue

        logger.debug(f"Page {page_number}: Found {len(image_list)} embedded image(s)")

        for img_info in image_list:
            xref = img_info[0]
            image_index += 1

            # Extract raw image bytes
            try:
                base_image = doc.extract_image(xref)
            except Exception as e:
                logger.warning(f"Page {page_number}, image {image_index}: Failed to extract: {e}")
                continue

            if base_image is None:
                logger.debug(f"Page {page_number}, image {image_index}: No image data at xref {xref}")
                continue

            image_bytes = base_image["image"]
            image_ext = base_image.get("ext", "png")

            # Create pixmap to get dimensions
            try:
                pixmap = fitz.Pixmap(doc, xref)
            except Exception as e:
                logger.warning(f"Page {page_number}, image {image_index}: Failed to create pixmap: {e}")
                continue

            width = pixmap.width
            height = pixmap.height

            # Filter by minimum dimensions
            if width < min_width or height < min_height:
                total_filtered += 1
                logger.debug(
                    f"Page {page_number}, image {image_index}: Filtered out "
                    f"({width}x{height} < {min_width}x{min_height})"
                )
                pixmap = None  # Free pixmap
                continue

            # Get image position on page for ordering
            y0 = _get_image_y0(page, xref, height)

            # Convert to PNG bytes for consistent output
            png_bytes = _convert_to_png(pixmap, image_bytes, image_ext)

            filename = f"page{page_number}_img{image_index}.png"

            extracted.append(
                ExtractedImage(
                    page_number=page_number,
                    image_index=image_index,
                    filename=filename,
                    width=width,
                    height=height,
                    y0=y0,
                    data=png_bytes,
                )
            )

            pixmap = None  # Free pixmap

    logger.info(
        f"Image extraction: {len(extracted)} images kept "
        f"({total_filtered} filtered out of {total_found} found)"
    )

    # Sort by page then y0 for correct insertion order
    extracted.sort(key=lambda img: (img.page_number, img.y0))

    return extracted


def _get_image_y0(page: Any, xref: int, default_height: int) -> float:
    """Get the vertical position (y0) of an image on a page.

    Args:
        page: fitz.Page object
        xref: Image XREF
        default_height: Fallback y0 if rect cannot be determined

    Returns:
        y0 coordinate for ordering
    """
    try:
        rects = page.get_image_rects(xref)
        if rects:
            return rects[0].y0
    except Exception:
        pass

    # Fallback: use a large value so images without position info
    # are placed at the end of the page
    return float(default_height)


def _convert_to_png(
    pixmap: Any,  # fitz.Pixmap
    image_bytes: bytes,
    image_ext: str,
) -> bytes:
    """Convert image data to PNG bytes.

    Args:
        pixmap: fitz.Pixmap of the image
        image_bytes: Raw image bytes
        image_ext: Original image extension

    Returns:
        PNG-encoded bytes
    """
    try:
        # If pixmap has alpha channel, convert to RGB first for PIL
        if pixmap.n > 3:
            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)

        # Use pixmap's built-in PNG conversion (most reliable)
        return pixmap.tobytes("png")
    except Exception:
        pass

    # Fallback: try to load via PIL and re-encode as PNG
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:
        get_logger().warning(f"Failed to convert image to PNG: {e}")
        # Last resort: return original bytes (may not be PNG)
        return image_bytes
