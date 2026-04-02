"""pdf2md - Convert PDF documents to Markdown with OCR support."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("pdf2md")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]
