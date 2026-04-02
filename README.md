# pdf2md

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Convert PDF documents to Markdown with OCR support for both text-based and scanned PDFs.

## Features

- **Dual-mode extraction**: Automatically detects text-based and scanned pages
- **OCR fallback**: Built-in RapidOCR engine for scanned pages (no internet required)
- **CJK support**: Full support for Simplified Chinese, Traditional Chinese, and Japanese
- **Image extraction**: Extracts embedded images with correct Markdown insertion points
- **Smart formatting**: Infers headings, lists, code blocks, and tables from PDF layout
- **Cross-platform**: Works on Windows, Linux, and macOS
- **Standalone executable**: Single-file `.exe` for Windows with all dependencies bundled

## Installation

### Windows (Standalone Executable)

Download the latest release from the [Releases page](https://github.com/pdf2md/pdf2md/releases) and extract `pdf2md.exe` to your preferred location.

### Using pip

```bash
pip install pdf2md
```

### Using pipx (Recommended for CLI tools)

```bash
pipx install pdf2md
```

### From Source

```bash
git clone https://github.com/pdf2md/pdf2md.git
cd pdf2md
uv pip install -e .
```

## Usage

### Basic Usage

```bash
# Convert a text-based PDF
pdf2md document.pdf

# Convert with custom output path
pdf2md document.pdf -o output.md

# Convert a scanned PDF with Chinese text
pdf2md scanned.pdf --ocr-lang ch_sim

# Convert and output to a directory (preserves images folder)
pdf2md document.pdf --output-dir ./output/
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `input` | Input PDF file (required) | — |
| `-o, --output` | Output `.md` or `.zip` file path | `<input_basename>.md` or `.zip` |
| `--output-dir` | Output to folder instead of ZIP | — |
| `--min-image-size` | Min image size to extract (WxH) | `50x50` |
| `--ocr-lang` | OCR language hint (`en`, `ch_sim`, `ch_tra`, `auto`) | `auto` |
| `--skip-ocr` | Disable OCR fallback for scanned pages | Off |
| `--verbose` | Enable debug logging and per-page progress | Off |
| `--quiet` | Minimal output (errors only) | Off |
| `--version` | Show version number | — |
| `--help` | Show help message | — |

### Examples

```bash
# English document with verbose output
pdf2md report.pdf --verbose

# Mixed English and Chinese document
pdf2md mixed.pdf --ocr-lang auto

# Disable OCR for text-only PDFs (faster)
pdf2md text-only.pdf --skip-ocr

# Extract larger images only (100x100 minimum)
pdf2md images.pdf --min-image-size 100x100
```

## Output Modes

### Single Markdown File
When no images are extracted, outputs a single `.md` file.

### ZIP Archive
When images are extracted, outputs a `.zip` containing:
```
document.zip
├── document.md
└── images/
    ├── page1_img1.png
    ├── page1_img2.png
    └── page3_img1.png
```

### Directory Output
Use `--output-dir` to output unpacked files:
```
output/
├── document.md
└── images/
    └── ...
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic failure (unexpected error) |
| 2 | Invalid CLI usage (conflicting flags, missing arguments) |
| 3 | Input file not found or unreadable |
| 4 | Conversion failure (extraction or build error) |
| 5 | Output path not writable |
| 6 | OCR model not found (RapidOCR ONNX models missing) |

## Supported Languages

| Language | Code | Notes |
|----------|------|-------|
| English | `en` | Default OCR language |
| Simplified Chinese | `ch_sim` | Full CJK support |
| Traditional Chinese | `ch_tra` | Full CJK support |
| Auto-detect | `auto` | Attempts to detect language |

## Windows 11 Context Menu Integration

Add "Convert to Markdown" to the right-click menu for PDF files:

1. Copy `pdf2md.exe` and `pdf2md.bat` to `C:\Program Files\pdf2md\`
2. Edit `pdf2md.bat` and `pdf2md-windows.reg` with correct paths
3. Run `reg import pdf2md-windows.reg` as Administrator
4. Restart Windows Explorer

## Troubleshooting

### "Input file not found" (Exit Code 3)
Ensure the PDF file path is correct and the file is accessible.

### "OCR model not found" (Exit Code 6)
The RapidOCR ONNX models are missing. Reinstall the package or ensure you're using the standalone executable which bundles all models.

### Corrupted output with scanned PDFs
Try specifying the OCR language explicitly:
```bash
pdf2md scanned.pdf --ocr-lang ch_sim
```

### Images not appearing in output
- Check that images meet the minimum size threshold (default: 50x50 px)
- Use `--min-image-size 0x0` to extract all images
- Verify the images folder is alongside the `.md` file when viewing

### Slow conversion on large PDFs
- Use `--skip-ocr` if the PDF has a text layer
- Reduce DPI or OCR language complexity

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## Acknowledgments

- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF text extraction and rendering
- [RapidOCR](https://github.com/RapidAI/RapidOCR) - Fast OCR engine with CJK support
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - Underlying OCR models
