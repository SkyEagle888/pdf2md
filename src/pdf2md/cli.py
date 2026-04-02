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

    # Log start message
    logger.debug(f"Input: {parsed_args.input}")
    logger.debug(f"Output: {parsed_args.output or 'auto'}")
    logger.debug(f"Output dir: {parsed_args.output_dir or 'not set'}")
    logger.debug(f"OCR language: {parsed_args.ocr_lang}")
    logger.debug(f"Skip OCR: {parsed_args.skip_ocr}")
    logger.debug(f"Min image size: {parsed_args.min_image_size}")

    # TODO: Implement conversion logic
    # - Phase 2: PDF Analysis Engine
    # - Phase 3: OCR Module
    # - Phase 4: Markdown Builder
    # - Phase 5: Output Module

    logger.info("pdf2md conversion not yet implemented.")
    logger.info("Coming in Phase 2: PDF Analysis Engine")

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
