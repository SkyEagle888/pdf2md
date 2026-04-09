# pdf2md v0.3.0

## Windows Standalone Executable Release

This is the first standalone Windows release of **pdf2md** -- a CLI tool that converts PDF documents to Markdown with OCR support for both text-based and scanned PDFs.

### Download

- **`pdf2md.exe`** -- Single-file Windows executable (~107 MB)
  - SHA256: `a77bef113edfddefef5cd065bc9c055298a6102c91b8b569aa36111a130bb164`
  - No Python installation required -- all dependencies bundled

### What's New

- First standalone Windows `.exe` build via PyInstaller
- All dependencies bundled: PyMuPDF, RapidOCR-onnxruntime, Pillow, ONNX runtime models
- PyInstaller spec file (`pdf2md.spec`) for reproducible builds
- Python 3.13 compatibility
- CHANGELOG.md added to track releases

### Features

- **Dual-mode extraction**: Automatically detects text-based and scanned pages per-page
- **OCR fallback**: Built-in RapidOCR engine for scanned pages (no internet required)
- **CJK support**: Full support for Simplified Chinese, Traditional Chinese, and Japanese
- **Image extraction**: Extracts embedded images with correct Markdown insertion points
- **Smart formatting**: Infers headings, lists, code blocks, and tables from PDF layout
- **Proper exit codes**: 0-6 for clear error reporting

### Quick Start

```powershell
# Basic conversion
.\pdf2md.exe document.pdf

# With verbose output
.\pdf2md.exe document.pdf --verbose

# Scanned PDF with Chinese text
.\pdf2md.exe scanned.pdf --ocr-lang ch_sim

# Output to directory (preserves images)
.\pdf2md.exe document.pdf --output-dir .\output\

# Show help
.\pdf2md.exe --help
```

### Full CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `input` | Input PDF file (required) | -- |
| `-o, --output` | Output `.md` or `.zip` file path | `<input>.md` or `.zip` |
| `--output-dir` | Output to folder instead of ZIP | -- |
| `--min-image-size` | Min image size to extract (WxH) | `50x50` |
| `--ocr-lang` | OCR language hint | `auto` |
| `--skip-ocr` | Disable OCR fallback | Off |
| `--verbose` | Debug logging and per-page progress | Off |
| `--quiet` | Minimal output (errors only) | Off |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic failure |
| 2 | Invalid CLI usage |
| 3 | Input file not found |
| 4 | Conversion failure |
| 5 | Output not writable |
| 6 | OCR model not found |

### Build from Source

```bash
git clone https://github.com/SkyEagle888/pdf2md.git
cd pdf2md
uv run pyinstaller pdf2md.spec --clean --noconfirm
# Output: dist/pdf2md.exe
```

### Changelog

See [CHANGELOG.md](https://github.com/SkyEagle888/pdf2md/blob/v0.3.0/CHANGELOG.md) for full release history.

---

**Full commit history**: [v0.2.0...v0.3.0](https://github.com/SkyEagle888/pdf2md/compare/v0.2.0...v0.3.0)
