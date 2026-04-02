"""Logging configuration for pdf2md."""

import logging
import sys


def setup_logger(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """Set up and return the logger with appropriate level and handler.

    Args:
        verbose: Enable debug logging if True
        quiet: Suppress all output except errors if True

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("pdf2md")

    # Determine log level
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create formatter
    if verbose:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        formatter = logging.Formatter("%(message)s")

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the pdf2md logger instance.

    Returns:
        Logger instance (may be unconfigured if setup_logger hasn't been called)
    """
    return logging.getLogger("pdf2md")
