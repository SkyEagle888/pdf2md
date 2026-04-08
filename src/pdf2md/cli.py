"""Command-line interface for pdf2md."""

import argparse
import sys
from pathlib import Path

from pdf2md import __version__
from pdf2md.logging import setup_logger, get_logger

# Exit codes per Requirements.md
EXIT_SUCCESS = 0
EXIT_GENERIC_FAILURE = 1
EXIT_INVALID_USAGE = 2
EXIT_INPUT_NOT_FOUND = 3
EXIT_CONVERSION_FAILURE = 4
EXIT_OUTPUT_NOT_WRITABLE = 5
EXIT_OCR_MODEL_NOT_FOUND = 6


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: List of arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="pdf2md",
        description="Convert PDF documents to Markdown with OCR support.",
        epilog="Examples:\n"
        "  pdf2md document.pdf\n"
        "  pdf2md document.pdf -o output.md\n"
        "  pdf2md scanned.pdf --ocr-lang ch_sim\n"
        "  pdf2md document.pdf --output-dir ./output/\n",
    )

    parser.add_argument(
        "input",
        type=str,
        help="Input PDF file path",
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        dest="output",
        help="Output .md or .zip file path (default: <input_basename>.md or .zip)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        dest="output_dir",
        help="Output to folder instead of ZIP (creates .md and images/ subfolder)",
    )

    parser.add_argument(
        "--min-image-size",
        type=str,
        default="50x50",
        help="Minimum image size to extract (WxH, default: 50x50)",
    )

    parser.add_argument(
        "--ocr-lang",
        type=str,
        default="auto",
        choices=["en", "ch_sim", "ch_tra", "auto"],
        help="OCR language hint (default: auto)",
    )

    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Disable OCR fallback for scanned pages",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging and per-page progress",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (errors only)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args(args)


def validate_args(args: argparse.Namespace) -> tuple[bool, str | None, int]:
    """Validate parsed arguments.

    Args:
        args: Parsed arguments namespace

    Returns:
        Tuple of (is_valid, error_message, exit_code)
    """
    # Check for conflicting output options
    if args.output and args.output_dir:
        return False, "Cannot specify both --output and --output-dir", EXIT_INVALID_USAGE

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        return False, f"Input file not found: {args.input}", EXIT_INPUT_NOT_FOUND

    if not input_path.is_file():
        return False, f"Input path is not a file: {args.input}", EXIT_INPUT_NOT_FOUND

    # Validate input is a PDF
    if input_path.suffix.lower() != ".pdf":
        return False, f"Input file must be a PDF: {args.input}", EXIT_INPUT_NOT_FOUND

    # Validate min-image-size format
    try:
        width, height = args.min_image_size.split("x")
        int(width)
        int(height)
    except ValueError:
        return False, f"Invalid --min-image-size format: {args.min_image_size} (expected WxH)", EXIT_INVALID_USAGE

    return True, None, EXIT_SUCCESS


def _parse_min_image_size(size_str: str) -> tuple[int, int]:
    """Parse min-image-size string (WxH) into tuple.

    Args:
        size_str: Size string like "50x50"

    Returns:
        Tuple of (width, height)
    """
    width, height = size_str.split("x")
    return int(width), int(height)


def _has_scan_pages(analysis) -> bool:
    """Check if any pages require OCR.

    Args:
        analysis: DocumentAnalysis from analyser.py

    Returns:
        True if any pages are in SCAN mode
    """
    from pdf2md.analyser import PageMode  # noqa: PLC0415

    return any(page.mode == PageMode.SCAN for page in analysis.pages)


def main(args: list[str] | None = None) -> int:
    """Main entry point for pdf2md CLI.

    Args:
        args: List of arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    parsed_args = parse_args(args)

    # Set up logging early so we can log during validation
    logger = setup_logger(verbose=parsed_args.verbose, quiet=parsed_args.quiet)

    # Validate arguments
    is_valid, error_message, exit_code = validate_args(parsed_args)
    if not is_valid:
        logger.error(error_message)
        return exit_code

    # Parse min-image-size
    min_width, min_height = _parse_min_image_size(parsed_args.min_image_size)

    try:
        # Import modules (lazy to avoid startup cost)
        from pdf2md.analyser import analyze_pdf  # noqa: PLC0415
        from pdf2md.images import extract_images  # noqa: PLC0415
        from pdf2md.ocr import OCREngine  # noqa: PLC0415
        from pdf2md.builder import MarkdownBuilder  # noqa: PLC0415
        from pdf2md.output import OutputWriter  # noqa: PLC0415

        # Step 1: Analyze PDF
        logger.info(f"Reading: {parsed_args.input}")
        analysis = analyze_pdf(parsed_args.input)

        input_path = Path(parsed_args.input)
        file_size_mb = analysis.file_size_bytes / (1024 * 1024)
        logger.info(
            f"  {input_path.name} "
            f"({file_size_mb:.1f} MB, {analysis.total_pages} pages)"
        )

        # Log per-page detection
        for page in analysis.pages:
            from pdf2md.analyser import PageMode  # noqa: PLC0415

            if page.mode == PageMode.TEXT:
                logger.info(
                    f"  Page {page.page_number}/{analysis.total_pages}: "
                    f"text layer detected"
                )
            else:
                logger.info(
                    f"  Page {page.page_number}/{analysis.total_pages}: "
                    f"no text layer — running OCR..."
                )

        # Step 2: Extract images
        images = []
        try:
            import fitz  # noqa: PLC0415

            with fitz.open(parsed_args.input) as doc:
                images = extract_images(doc, min_width, min_height)
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            return EXIT_CONVERSION_FAILURE

        if images:
            logger.info(
                f"  Extracting images: {len(images)} found, "
                f"all above threshold ({min_width}x{min_height} px)"
            )
        else:
            logger.info("  Extracting images: none found")

        # Step 3: OCR (if needed and not skipped)
        ocr_results = {}
        if not parsed_args.skip_ocr and _has_scan_pages(analysis):
            logger.info("  Running OCR on scanned pages...")
            try:
                ocr_engine = OCREngine(lang=parsed_args.ocr_lang)
            except RuntimeError as e:
                logger.error(f"OCR engine failed to initialise: {e}")
                return EXIT_OCR_MODEL_NOT_FOUND
            except Exception as e:
                logger.error(f"Unexpected error initialising OCR: {e}")
                return EXIT_OCR_MODEL_NOT_FOUND

            # Process each SCAN page
            for page in analysis.pages:
                from pdf2md.analyser import PageMode  # noqa: PLC0415

                if page.mode == PageMode.SCAN and page.pixmap is not None:
                    try:
                        ocr_result = ocr_engine.process_pixmap(
                            page.pixmap,
                            page.page_number,
                        )
                        ocr_results[page.page_number] = ocr_result
                    except Exception as e:
                        logger.warning(
                            f"  Page {page.page_number}: OCR failed: {e}"
                        )

        # Step 4: Build Markdown
        logger.info("  Building Markdown...")
        builder = MarkdownBuilder(
            add_page_breaks=False,
            max_heading_level=4,
        )

        if ocr_results:
            markdown = builder.build_with_ocr(
                analysis, images, ocr_results
            )
        else:
            markdown = builder.build(analysis, images)

        # Log build statistics
        stats = builder.stats
        logger.debug(
            f"  Build stats: {stats.pages_processed} pages, "
            f"{stats.headings_found} headings, "
            f"{stats.lists_found} lists, "
            f"{stats.code_blocks_found} code blocks, "
            f"{stats.tables_found} tables, "
            f"{stats.images_inserted} images"
        )

        # Step 5: Write output
        writer = OutputWriter(
            output_path=parsed_args.output,
            output_dir=parsed_args.output_dir,
        )

        # Validate output path before conversion
        is_valid, error = writer.validate_output()
        if not is_valid:
            logger.error(f"Output not writable: {error}")
            return EXIT_OUTPUT_NOT_WRITABLE

        try:
            output_path = writer.write(markdown, images, parsed_args.input)
        except PermissionError as e:
            logger.error(f"Output not writable: {e}")
            return EXIT_OUTPUT_NOT_WRITABLE
        except OSError as e:
            logger.error(f"Output not writable: {e}")
            return EXIT_OUTPUT_NOT_WRITABLE

        # Log completion
        if output_path.is_file():
            output_size_mb = output_path.stat().st_size / (1024 * 1024)
            if output_path.suffix == ".zip":
                logger.info(
                    f"  Packaging output: {output_path.name} "
                    f"({output_size_mb:.1f} MB)"
                )
            else:
                logger.info(
                    f"  Output written: {output_path.name} "
                    f"({output_size_mb:.1f} MB)"
                )
        else:
            logger.info(f"  Output written to: {output_path}")

        logger.info("  Done.")
        return EXIT_SUCCESS

    except FileNotFoundError as e:
        logger.error(f"Input file not found: {e}")
        return EXIT_INPUT_NOT_FOUND

    except RuntimeError as e:
        if "RapidOCR" in str(e) or "rapidocr" in str(e).lower():
            logger.error(
                f"OCR model not found: {e}\n"
                f"Try running with --verbose for details."
            )
            return EXIT_OCR_MODEL_NOT_FOUND
        logger.error(f"Conversion failed: {e}")
        return EXIT_CONVERSION_FAILURE

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug("Exception details:", exc_info=True)
        return EXIT_GENERIC_FAILURE


if __name__ == "__main__":
    sys.exit(main())
