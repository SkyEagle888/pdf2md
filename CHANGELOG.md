# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v0.3.0] - 2026-04-09

### Added

- First standalone Windows `.exe` build via PyInstaller
- PyInstaller spec file (`pdf2md.spec`) for reproducible builds
- PyInstaller hook for bundling RapidOCR ONNX models (`hooks/hook-rapidocr_onnxruntime.py`)
- Python 3.13 compatibility

### Changed

- Updated README with Windows standalone installation instructions
- Added Python 3.13 classifier to `pyproject.toml`

### Build

- Single-file binary (~107 MB) with all dependencies bundled:
  PyMuPDF, RapidOCR-onnxruntime, Pillow, ONNX runtime models
- Build command: `uv run pyinstaller pdf2md.spec --clean --noconfirm`
- Output: `dist/pdf2md.exe`

## [v0.2.0] - 2026-04-02

### Changed

- Documentation updates for v0.1.0 release
- Added `.qwen/` to `.gitignore`

## [v0.1.0] - 2026-04-01

### Added

- Complete PDF-to-Markdown conversion pipeline (Phases 2-6)
- PDF analysis engine: text layer vs. scanned page detection per page
- OCR module with RapidOCR-onnxruntime (CJK support)
- Markdown builder: headings, lists, code blocks, tables inference
- Image extraction with configurable minimum size
- Output module: single `.md`, `.zip` with images, or directory output
- CLI with full argument parsing and validation
- Exit codes 0-6 per requirements specification
- Logging system (verbose/quiet modes)
- Test PDF generation script
- PyInstaller hook (renamed to match package name)
- hatch-vcs for automatic versioning from Git tags

[Unreleased]: https://github.com/SkyEagle888/pdf2md/compare/v0.3.0...HEAD
[v0.3.0]: https://github.com/SkyEagle888/pdf2md/compare/v0.2.0...v0.3.0
[v0.2.0]: https://github.com/SkyEagle888/pdf2md/compare/v0.1.0...v0.2.0
[v0.1.0]: https://github.com/SkyEagle888/pdf2md/releases/tag/v0.1.0
