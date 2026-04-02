# Requirements.md — pdf2md

## 1. Overview

### 1.1 Purpose

Build a cross-platform command-line application that converts PDF files into Markdown (`.md`), preserving text structure, formatting, code blocks, images, and multilingual content (English, Traditional Chinese, Simplified Chinese).

The tool detects whether the PDF contains an embedded text layer (text-based) or requires optical character recognition (scanned/image-based), and selects the appropriate extraction pipeline automatically.

### 1.2 Target Users

- Windows 11 users who want a standalone `.exe` (no Python install required).
- Developers and technical writers who need to migrate PDF documentation into editable, version-controllable Markdown.
- Enterprise users working with mixed-language (EN/TC/SC) documents and legacy PDFs.

### 1.3 Key Outcomes

- Accurate Markdown output preserving document structure (headings, lists, tables, code blocks).
- Full Unicode support: English, Traditional Chinese, Simplified Chinese.
- Smart output mode: single `.md` file for text-only PDFs; `.zip` bundle (`.md` + images) for PDFs containing images.
- Windows 11 context menu integration for right-click conversion.
- GitHub releases with standalone Windows `.exe`.

---

## 2. In Scope (MVP)

### 2.1 Inputs

- A single PDF file (`.pdf`) as input.
- PDFs may be:
  - **Text-based**: contain an embedded text/font layer (selectable text in a PDF viewer).
  - **Scanned/image-based**: pages are raster images, no embedded text layer.
  - **Mixed**: some pages are text-based, others are scanned.

### 2.2 Output Modes

| Condition | Output |
|-----------|--------|
| PDF has no embedded images | Single `.md` file |
| PDF contains one or more embedded images | `.zip` archive containing `<name>.md` and an `images/` sub-folder |

The `images/` sub-folder contains extracted images named `page{N}_img{M}.png` (N = 1-based page number, M = 1-based image index on page). Images are referenced in the Markdown using relative paths (e.g., `![page1_img1](images/page1_img1.png)`).

Small decorative images (below a configurable pixel threshold, default: 50×50 px) are excluded to filter out bullets, borders, and watermark artefacts.

### 2.3 Markdown Features (MVP)

- Headings (H1–H6), inferred from font size and weight
- Paragraphs with correct reading order
- Emphasis (bold, italic) where detectable
- Ordered and unordered lists
- Blockquotes
- Fenced code blocks (triple backticks) — detected via monospaced font regions or OCR layout cues
- Basic tables (where PDF structure allows extraction)
- Inline images via relative paths
- Hyperlinks (where embedded in PDF metadata)

### 2.4 Language Support

- **English**: full support via text extraction and OCR.
- **Traditional Chinese (繁體中文)**: full support via PaddleOCR (CJK-trained models) and PyMuPDF Unicode extraction.
- **Simplified Chinese (简体中文)**: full support via PaddleOCR (CJK-trained models) and PyMuPDF Unicode extraction.
- **Mixed-language documents**: handled correctly within the same page.

### 2.5 Implementation Stack (v0.1)

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| PDF Text Extraction | `PyMuPDF` (`fitz`) — text layer extraction, image extraction |
| OCR Engine | `RapidOCR` (ONNX-based, lightweight, offline, CJK support) |
| Layout Analysis | PyMuPDF block/span analysis for reading order |
| CLI Framework | `argparse` (stdlib) |
| Packaging | PyInstaller for Windows `.exe` (standalone) |
| Version Management | `hatch-vcs` (Git tag-based automatic versioning) |

**OCR engine rationale**: RapidOCR is selected over PaddleOCR (full) because it uses PaddleOCR's trained ONNX models without requiring the full PaddleOCR runtime (~1GB). It runs on CPU, has no GPU requirement, ships as a lightweight Python package (~80MB), and is compatible with PyInstaller bundling — consistent with the lean executable philosophy of the md2pdf companion tool.

### 2.6 PDF Detection Logic

```
For each page:
  1. Attempt PyMuPDF text extraction (page.get_text())
  2. If extracted text length > threshold (e.g., 50 chars after stripping whitespace):
     → Use text extraction pipeline
  3. Else:
     → Render page as image (fitz.Pixmap)
     → Run RapidOCR on rendered image
     → Use OCR output
```

Mixed-mode documents are handled page-by-page; the final Markdown concatenates all pages in order.

---

## 3. Out of Scope (v0.1)

- LaTeX / mathematical formula rendering.
- Mermaid or SVG diagram recognition.
- PDF form field extraction.
- Multi-column academic paper layout reflow (best-effort only).
- GUI application (CLI only).
- macOS binary (Windows is the primary target; Linux via Python package).
- Right-to-left (RTL) language support (Arabic, Hebrew, etc.).
- Password-protected PDF decryption.

---

## 4. CLI Requirements

### 4.1 Command Name

- `pdf2md`

### 4.2 Basic Usage

```bash
# Single .md output (text-only PDF)
pdf2md input.pdf -o output.md

# ZIP output (PDF with images) — auto-detected
pdf2md input.pdf -o output.zip

# Auto output name (same as input basename)
pdf2md input.pdf
```

### 4.3 CLI Parameters (v0.1)

**Required:**

- `input`: Input PDF file path.

**Optional:**

- `-o, --output <path>`: Output path.
  - If PDF has no images: defaults to `<input_basename>.md` in the same folder.
  - If PDF has images: defaults to `<input_basename>.zip` in the same folder.
  - If the user specifies a `.md` path but images are detected, the tool warns and switches to `.zip` automatically.
- `--output-dir <path>`: Output to a folder instead of a ZIP (extracts the bundle in-place). Useful for Git workflows.
- `--min-image-size <WxH>`: Minimum pixel dimensions for image extraction (default: `50x50`). Images smaller than this are skipped.
- `--ocr-lang <lang>`: OCR language hint. Options: `en`, `ch_sim`, `ch_tra`, `auto` (default: `auto`).
- `--skip-ocr`: Disable OCR fallback; only use embedded text layer.
- `--verbose`: Print debug logs and step-by-step progress.
- `--quiet`: Minimal output.
- `--version`: Print version.
- `--help`: Print help.

### 4.4 Exit Codes

| Code | Meaning | When |
|------|---------|------|
| `0` | Success | Markdown (or ZIP) created successfully |
| `1` | Generic failure | Unexpected error |
| `2` | Invalid CLI usage | Invalid arguments or conflicting flags |
| `3` | Input file not found | PDF file does not exist or is unreadable |
| `4` | Conversion failure | Text extraction or OCR error |
| `5` | Output not writable | Permission denied on output path |
| `6` | OCR model not found | RapidOCR model files missing from package |

---

## 5. Functional Requirements

### 5.1 Text Extraction Correctness

- Extracted text must preserve the logical reading order of the document (top-to-bottom, left-to-right for LTR languages).
- Headings must be inferred from font size relative to body text (largest font size → H1, etc.).
- Paragraph boundaries must be detected from line spacing and block separation.
- Consecutive lines with matching bullet/numbering patterns must be grouped as lists.

### 5.2 OCR Correctness

- OCR must correctly recognise Traditional Chinese and Simplified Chinese characters.
- OCR output must preserve CJK punctuation (「」、。，).
- The tool must not mix OCR output from different pages out of order.

### 5.3 Code Block Detection

- Regions rendered in monospaced fonts (e.g., Courier, Consolas, Menlo) must be wrapped in fenced code blocks (` ``` `).
- Where possible, language hints from surrounding text (e.g., "Python example:") may be applied as the language specifier.
- Indentation and whitespace within code blocks must be preserved.

### 5.4 Image Extraction

- All raster images embedded in the PDF must be extracted and saved to `images/`.
- Images must be inserted at the correct position in the Markdown relative to surrounding text, using the vertical (`y0`) bounding box coordinate.
- Duplicate or near-identical images on the same page are extracted once only.
- SVG/vector elements embedded in the PDF are rendered to PNG for inclusion.

### 5.5 Output Structure — ZIP Bundle

When the output is a ZIP:

```
output.zip
└── document.md
└── images/
    ├── page1_img1.png
    ├── page1_img2.png
    └── page2_img1.png
```

The `.md` file references images as `images/page1_img1.png` (relative path). The ZIP is self-contained and can be unzipped anywhere for immediate use.

Alternatively, `--output-dir` extracts the same structure to a folder:

```
output/
├── document.md
└── images/
    └── ...
```

### 5.6 Error Messages

- Errors must be actionable:
  - Include the filename and page number where the error occurred.
  - For OCR failures, suggest running with `--verbose` for details.
  - For missing OCR models, provide the expected path and remediation step.
  - For permission errors, suggest checking write access to the output directory.

---

## 6. Non-Functional Requirements

### 6.1 Platform Support

- **Windows 11**: Distributable as a standalone `.exe` (no Python install required).
- **Linux (Ubuntu)**: Runnable via `pipx install` or `python -m pdf2md`.

### 6.2 Distribution & Packaging

**Windows:**
- Single-file or folder-based PyInstaller build.
- Bundle includes: RapidOCR ONNX model files, all Python dependencies.
- End-user does not need to install Python, CUDA, or any additional runtime.

**Linux:**
- `pipx install .` → run `pdf2md` from anywhere.
- `python -m pdf2md ...` for source installs.

### 6.3 Performance

- Text-based PDFs (no OCR): < 5 seconds for a typical 20-page document.
- Scanned PDFs (with OCR): best-effort; OCR is inherently slower. Progress feedback provided in `--verbose` mode per page.
- Executable size target: ≤ 80MB (ONNX models are larger than Pygments lexers; size is acceptable given offline OCR capability).

### 6.4 Offline Operation

- The tool must operate fully offline after installation.
- No API keys, cloud services, or internet connectivity required.
- RapidOCR ONNX models are bundled with the executable.

### 6.5 Progress Indicator

When `--verbose` is enabled, display step-by-step progress:

```
Reading: document.pdf (4.2 MB, 12 pages)
  Page 1/12: text layer detected
  Page 2/12: text layer detected
  Page 3/12: no text layer — running OCR...
  Page 4/12: text layer detected
  ...
  Extracting images: 5 found (3 above threshold)
  Building Markdown...
  Packaging output: document.zip (1.2 MB)
  Done.
```

### 6.6 Determinism

- Given the same input PDF and options, the output Markdown and images must be consistent across runs.

---

## 7. Acceptance Criteria (Definition of Done)

### 7.1 Test Documents

Create the following in `testdata/`:

| File | Description |
|------|-------------|
| `testdata/text_en.pdf` | Text-based PDF, English, includes code block |
| `testdata/text_cjk.pdf` | Text-based PDF, mixed Traditional + Simplified Chinese |
| `testdata/scanned_en.pdf` | Scanned/image-based PDF, English |
| `testdata/scanned_cjk.pdf` | Scanned/image-based PDF, Chinese |
| `testdata/mixed_images.pdf` | Text-based PDF with embedded images |

### 7.2 Acceptance Tests

- `pdf2md testdata/text_en.pdf` produces a valid `.md` with correct headings, lists, and a fenced code block.
- `pdf2md testdata/text_cjk.pdf` produces a `.md` with correct Traditional and Simplified Chinese characters.
- `pdf2md testdata/scanned_en.pdf` triggers OCR and produces readable English Markdown.
- `pdf2md testdata/scanned_cjk.pdf` triggers OCR and produces readable Chinese Markdown.
- `pdf2md testdata/mixed_images.pdf` produces a `.zip` containing a `.md` and an `images/` folder.
- Unzipping the output and opening the `.md` in any Markdown viewer renders images correctly via relative paths.
- Windows 11: `pdf2md.exe testdata\text_en.pdf` works on a machine without Python installed.
- Error handling:
  - Non-existent PDF input → exit code `3` with actionable message.
  - Output path not writable → exit code `5` with actionable message.

---

## 8. Windows 11 Context Menu Integration

- Right-clicking any `.pdf` file shows **"Convert to Markdown"** under "Show more options".
- Clicking the menu item runs `pdf2md.exe <filepath>` with default settings.
- Output is placed in the same folder as the source PDF.
- A `.bat` wrapper is provided for the context menu invocation (same pattern as md2pdf's `md2pdf.bat`).
- A `.reg` file (`assets/pdf2md-windows.reg`) is provided for registry installation.
- Installation instructions are documented in `README.md`.

---

## 9. Deliverables (v0.1)

- Source code (`src/pdf2md/`)
- `Requirements.md`
- `ImplementationPlan.md`
- `README.md` with usage examples and Windows context menu setup guide
- Release artifacts:
  - `pdf2md-win64.zip` — standalone Windows `.exe` with bundled OCR models
  - Linux instructions (pipx / pip install)
- Test data files (`testdata/`)
- `assets/pdf2md-windows.reg` — Windows 11 context menu registry file
- `assets/pdf2md.bat` — batch wrapper for context menu invocation
- `hooks/hook-rapidocr.py` — PyInstaller hook for bundling ONNX models
