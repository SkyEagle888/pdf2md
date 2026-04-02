# Libraries for pdf2md Project

## Core Dependencies

### PDF Processing

| Library | Purpose | Notes |
|---------|---------|-------|
| **PyMuPDF (fitz)** | PDF text extraction, image extraction, page rendering | Core library for reading PDF files, extracting text layers, and rendering pages as images |

### OCR Engine

| Library | Purpose | Notes |
|---------|---------|-------|
| **RapidOCR** | Optical Character Recognition for scanned/image-based PDFs | ONNX-based, lightweight (~80MB), offline operation, CJK support. Uses PaddleOCR's trained models without full PaddleOCR runtime |
| **onnxruntime** | Runtime for executing ONNX models | Required by RapidOCR for inference |

### Image Processing

| Library | Purpose | Notes |
|---------|---------|-------|
| **Pillow (PIL)** | Image manipulation and processing | For filtering small images (decorative elements), image format conversion |

## Standard Library Modules

| Module | Purpose |
|--------|---------|
| **argparse** | CLI argument parsing and help generation |
| **zipfile** | Creating ZIP archives for output bundles |
| **os** / **pathlib** | File system operations |
| **sys** | System-specific parameters and exit codes |
| **re** | Regular expressions for text pattern matching |

## Build and Distribution

| Library | Purpose | Notes |
|---------|---------|-------|
| **PyInstaller** | Packaging Python application as standalone Windows `.exe` | Bundles all dependencies and OCR models |
| **hatch-vcs** | Git tag-based automatic versioning | Manages version numbers from Git tags |
| **hatch** | Build system and project management | Modern Python build backend |

## Development Dependencies (Optional)

| Library | Purpose |
|---------|---------|
| **pytest** | Unit and integration testing |
| **pytest-cov** | Code coverage reporting |
| **black** | Code formatting |
| **ruff** | Linting |

## Installation Summary

```bash
# Core dependencies (runtime)
pip install PyMuPDF
pip install rapidocr-onnxruntime
pip install Pillow

# Build dependencies
pip install pyinstaller
pip install hatch hatch-vcs

# Development dependencies (optional)
pip install pytest pytest-cov black ruff
```

## Notes

1. **PyMuPDF** is the foundation - it handles PDF parsing, text extraction, and image extraction
2. **RapidOCR** was chosen over full PaddleOCR for its smaller footprint (~80MB vs ~1GB) and PyInstaller compatibility
3. **Pillow** is commonly used with PyMuPDF for image manipulation tasks
4. All OCR models are bundled offline - no internet connection required at runtime
5. The stdlib modules (argparse, zipfile, etc.) require no additional installation
