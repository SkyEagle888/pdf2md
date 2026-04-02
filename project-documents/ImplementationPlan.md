# Implementation Plan — pdf2md

## Implementation Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| PDF Text Extraction | `PyMuPDF` (`fitz`) — text layer, image extraction, page rendering |
| OCR Engine | `RapidOCR` — ONNX-based, offline, CJK support, lightweight |
| CLI Framework | `argparse` (stdlib) |
| ZIP Packaging | `zipfile` (stdlib) |
| Packaging | PyInstaller for Windows `.exe` (standalone, models bundled) |
| Version Management | `hatch-vcs` (Git tag-based automatic versioning) |

---

## Task Checklist

### Phase 1: Project Setup

- [x] 1.1 Create `pyproject.toml` with project metadata and dependencies
- [x] 1.2 Set up virtual environment and install dependencies (`uv` recommended)
- [x] 1.3 Create basic package structure (`src/pdf2md/`)
- [x] 1.4 Configure logging (for `--verbose` flag)
- [x] 1.5 Create `project-documents/Requirements.md` and `ImplementationPlan.md`

### Phase 2: PDF Analysis Engine

- [ ] 2.1 Implement PDF page analyser (`analyser.py`)
  - [ ] 2.1.1 Open PDF with PyMuPDF (`fitz.open`)
  - [ ] 2.1.2 Per-page: attempt `page.get_text("dict")` to retrieve text blocks with font metadata
  - [ ] 2.1.3 Determine page mode: `TEXT` if extracted chars > 50 (configurable threshold), else `SCAN`
  - [ ] 2.1.4 For SCAN pages: render to `fitz.Pixmap` at 150 DPI and pass to OCR module
  - [ ] 2.1.5 Collect per-page result: list of text blocks with bounding boxes, font sizes, font names
- [ ] 2.2 Implement image extractor (`images.py`)
  - [ ] 2.2.1 Use `page.get_images(full=True)` to retrieve all embedded images
  - [ ] 2.2.2 Filter images by pixel dimensions (default min: 50×50 px)
  - [ ] 2.2.3 Extract image bytes via `fitz.Pixmap`, save as PNG
  - [ ] 2.2.4 Record image bounding box (`y0`) for insertion position in Markdown
  - [ ] 2.2.5 Name files as `page{N}_img{M}.png` (1-based page and image index)

### Phase 3: OCR Module

- [ ] 3.1 Implement OCR wrapper (`ocr.py`)
  - [ ] 3.1.1 Initialise RapidOCR engine (load ONNX models once at startup)
  - [ ] 3.1.2 Accept `fitz.Pixmap` or PIL image as input
  - [ ] 3.1.3 Return list of `(text, bbox, confidence)` tuples, sorted top-to-bottom
  - [ ] 3.1.4 Support language hint: `en`, `ch_sim`, `ch_tra`, `auto`
  - [ ] 3.1.5 Handle OCR errors gracefully — log warning, return empty block for page
- [ ] 3.2 Verify CJK accuracy
  - [ ] 3.2.1 Test Traditional Chinese sample page
  - [ ] 3.2.2 Test Simplified Chinese sample page
  - [ ] 3.2.3 Test mixed EN + Chinese page

### Phase 4: Markdown Builder

- [ ] 4.1 Implement heading inference (`builder.py`)
  - [ ] 4.1.1 Collect all unique font sizes across the document
  - [ ] 4.1.2 Map largest → H1, next → H2, etc. (up to H4; smaller sizes → paragraph)
  - [ ] 4.1.3 Bold-only spans at paragraph font size → treat as H3 if no larger headings nearby
- [ ] 4.2 Implement paragraph and list detection
  - [ ] 4.2.1 Group consecutive text blocks by proximity (gap < line height = same paragraph)
  - [ ] 4.2.2 Detect bullet patterns: `•`, `-`, `*`, `·`, `○`, `■`, CJK bullets
  - [ ] 4.2.3 Detect numbered list patterns: `1.`, `（1）`, `①`, etc.
  - [ ] 4.2.4 Indent nested lists based on `x0` left-margin offset
- [ ] 4.3 Implement code block detection
  - [ ] 4.3.1 Identify blocks where font name contains `Mono`, `Courier`, `Consolas`, `Menlo`, `Code`
  - [ ] 4.3.2 Wrap detected regions in triple-backtick fenced blocks
  - [ ] 4.3.3 Preserve internal whitespace and indentation exactly
  - [ ] 4.3.4 Attempt language detection from preceding heading/label text
- [ ] 4.4 Implement table detection (best-effort)
  - [ ] 4.4.1 Detect grid-aligned text blocks that form rows and columns
  - [ ] 4.4.2 Output as GFM table (`| col | col |` format)
  - [ ] 4.4.3 Fall back to plain text block if table structure is ambiguous
- [ ] 4.5 Implement image insertion
  - [ ] 4.5.1 Sort extracted images by `y0` coordinate per page
  - [ ] 4.5.2 Insert `![pageN_imgM](images/pageN_imgM.png)` at the correct position in the text flow
- [ ] 4.6 Assemble full document Markdown
  - [ ] 4.6.1 Concatenate all pages in order
  - [ ] 4.6.2 Add horizontal rule (`---`) between pages (configurable, default: off)
  - [ ] 4.6.3 Clean up excessive blank lines (collapse 3+ blank lines to 2)

### Phase 5: Output Module

- [ ] 5.1 Implement output writer (`output.py`)
  - [ ] 5.1.1 Detect whether any images were extracted
  - [ ] 5.1.2 If no images: write single `.md` file to output path
  - [ ] 5.1.3 If images present and `--output-dir` not set: create `.zip` using `zipfile.ZipFile`
    - [ ] Add `<name>.md` at zip root
    - [ ] Add all images under `images/` inside the zip
  - [ ] 5.1.4 If `--output-dir` is set: write `.md` and `images/` folder to the specified directory
  - [ ] 5.1.5 Validate output path is writable before conversion starts (exit code `5` if not)

### Phase 6: CLI Implementation

- [ ] 6.1 Implement CLI with `argparse` (`cli.py`)
  - [ ] 6.1.1 Positional argument: `input` (PDF file path)
  - [ ] 6.1.2 Optional: `-o, --output` (output `.md` or `.zip` path)
  - [ ] 6.1.3 Optional: `--output-dir` (output to folder instead of ZIP)
  - [ ] 6.1.4 Optional: `--min-image-size <WxH>` (default: `50x50`)
  - [ ] 6.1.5 Optional: `--ocr-lang` (`en` / `ch_sim` / `ch_tra` / `auto`, default: `auto`)
  - [ ] 6.1.6 Optional: `--skip-ocr` (text layer only, no OCR fallback)
  - [ ] 6.1.7 Optional: `--verbose` / `--quiet`
  - [ ] 6.1.8 Optional: `--version` / `--help`
- [ ] 6.2 Implement exit codes (0–6 per Requirements)
- [ ] 6.3 Implement actionable error messages
  - [ ] 6.3.1 Missing PDF input → exit code `3`
  - [ ] 6.3.2 Unreadable/corrupted PDF → exit code `3`
  - [ ] 6.3.3 OCR model missing → exit code `6` with path hint
  - [ ] 6.3.4 Output path not writable → exit code `5`
  - [ ] 6.3.5 Conflicting `--output` + `--output-dir` flags → exit code `2`

### Phase 7: Testing & Validation

- [ ] 7.1 Create test documents in `testdata/`
  - [ ] `text_en.pdf` — text-based, English, includes a code block
  - [ ] `text_cjk.pdf` — text-based, Traditional + Simplified Chinese
  - [ ] `scanned_en.pdf` — scanned page, English
  - [ ] `scanned_cjk.pdf` — scanned page, Chinese
  - [ ] `mixed_images.pdf` — text-based with embedded images
- [ ] 7.2 Manual acceptance tests (per Requirements §7.2)
  - [ ] Text-based EN → correct headings, lists, code block
  - [ ] Text-based CJK → correct Chinese characters
  - [ ] Scanned EN → OCR triggered, readable output
  - [ ] Scanned CJK → OCR triggered, readable Chinese output
  - [ ] Images PDF → ZIP output with images folder and correct relative paths
  - [ ] Unzip and render `.md` in VS Code → images display correctly
- [ ] 7.3 Error scenario tests
  - [ ] Non-existent PDF → exit code `3`
  - [ ] Read-only output directory → exit code `5`
  - [ ] `--version` command works

### Phase 8: Windows Distribution

- [ ] 8.1 Create PyInstaller hook (`hooks/hook-rapidocr.py`)
  - [ ] Include RapidOCR ONNX model files in the bundle
  - [ ] Include PyMuPDF font data
- [ ] 8.2 Build Windows `.exe` with PyInstaller
  ```powershell
  pyinstaller --onefile --name pdf2md `
    --icon=assets/pdf2md-logo.ico `
    --additional-hooks-dir=./hooks `
    src/pdf2md/__main__.py
  ```
- [ ] 8.3 Test `.exe` on a clean Windows 11 machine (no Python installed)
- [ ] 8.4 Package as `pdf2md-win64.zip`
- [ ] 8.5 Create GitHub release with `pdf2md-win64.zip` as a release asset
- [ ] 8.6 Configure `hatch-vcs` for automatic versioning from Git tags

### Phase 9: Windows 11 Context Menu

- [ ] 9.1 Create `assets/pdf2md.bat` — batch wrapper script
  ```batch
  @echo off
  set filename=%~1
  "C:\Program Files\pdf2md\pdf2md.exe" "%filename%"
  ```
- [ ] 9.2 Create `assets/pdf2md-windows.reg` — registry file for context menu
  ```reg
  Windows Registry Editor Version 5.00

  [HKEY_CLASSES_ROOT\SystemFileAssociations\.pdf\shell\Convert to Markdown]
  @="Convert to Markdown"

  [HKEY_CLASSES_ROOT\SystemFileAssociations\.pdf\shell\Convert to Markdown\command]
  @="\"C:\\Program Files\\pdf2md\\pdf2md.bat\" \"%1\""
  ```
- [ ] 9.3 Document context menu installation in `README.md`
  - Copy `pdf2md.exe` and `pdf2md.bat` to installation folder
  - Edit paths in `pdf2md.bat` and `pdf2md-windows.reg`
  - Run `reg import pdf2md-windows.reg` as Administrator
  - Restart Windows Explorer

### Phase 10: Documentation

- [ ] 10.1 Write `README.md` with:
  - [ ] Feature overview and badges
  - [ ] Installation (Windows `.exe`, Linux pipx/pip)
  - [ ] CLI usage examples (text PDF, scanned PDF, images PDF, output-dir mode)
  - [ ] All CLI options table
  - [ ] Exit codes table
  - [ ] Windows 11 context menu setup guide
  - [ ] Supported languages
  - [ ] Troubleshooting section
- [ ] 10.2 Finalise `Requirements.md` and `ImplementationPlan.md`

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "pdf2md"
dynamic = ["version"]
requires-python = ">=3.10"

dependencies = [
    "pymupdf>=1.23",
    "rapidocr-onnxruntime>=1.3",
    "pillow>=10.0",
]

[project.optional-dependencies]
dev = [
    "pyinstaller>=6.0",
    "hatch-vcs>=0.4",
]

[project.scripts]
pdf2md = "pdf2md.cli:main"

[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"
```

---

## File Structure (Target)

```
pdf2md/
├── pyproject.toml
├── uv.lock
├── .venv/
├── src/pdf2md/
│   ├── __init__.py          # Dynamic version import
│   ├── __main__.py          # Package entry point
│   ├── cli.py               # CLI argument parsing and entry point
│   ├── analyser.py          # PDF page analysis (text vs. scan detection)
│   ├── ocr.py               # RapidOCR wrapper
│   ├── images.py            # Image extraction from PDF
│   ├── builder.py           # Markdown assembly (headings, lists, code, tables)
│   └── output.py            # Output writer (.md single file or .zip bundle)
├── hooks/
│   └── hook-rapidocr.py     # PyInstaller hook: bundle ONNX models
├── assets/
│   ├── pdf2md-logo.ico          # Windows icon for .exe
│   ├── pdf2md-logo.png          # Logo image
│   ├── pdf2md.bat               # Batch wrapper for Windows context menu
│   └── pdf2md-windows.reg       # Windows 11 context menu registry file
├── testdata/
│   ├── text_en.pdf
│   ├── text_cjk.pdf
│   ├── scanned_en.pdf
│   ├── scanned_cjk.pdf
│   └── mixed_images.pdf
├── project-documents/
│   ├── Requirements.md
│   └── ImplementationPlan.md
└── README.md
```

---

## CLI Options (Final)

| Option | Description | Default |
|--------|-------------|---------|
| `input` | Input PDF file (required) | — |
| `-o, --output` | Output `.md` or `.zip` path | `<input_basename>.md` or `.zip` |
| `--output-dir` | Output to folder instead of ZIP | — |
| `--min-image-size` | Min image size to extract (WxH) | `50x50` |
| `--ocr-lang` | OCR language hint | `auto` |
| `--skip-ocr` | Disable OCR fallback | Off |
| `--verbose` | Debug logs and per-page progress | Off |
| `--quiet` | Minimal output | Off |
| `--version` | Show version | — |
| `--help` | Show help | — |

---

## Exit Codes

| Code | Meaning | When |
|------|---------|------|
| 0 | Success | Output created successfully |
| 1 | Generic failure | Unexpected error |
| 2 | Invalid CLI usage | Conflicting flags, missing arguments |
| 3 | Input file not found | PDF missing or unreadable |
| 4 | Conversion failure | Extraction or build error |
| 5 | Output not writable | Permission denied |
| 6 | OCR model not found | RapidOCR ONNX models missing |

---

## Verbose Progress Output

```
Reading: document.pdf (4.2 MB, 12 pages)
  Page 1/12: text layer detected
  Page 2/12: text layer detected
  Page 3/12: no text layer — running OCR...
  Page 4/12: text layer detected
  ...
  Extracting images: 5 found, 3 above threshold (50x50 px)
  Building Markdown...
  Packaging output: document.zip (1.2 MB)
  Done.
```

---

## Key Design Decisions

### Why RapidOCR over Full PaddleOCR

PaddleOCR full runtime is approximately 1GB and difficult to bundle with PyInstaller. RapidOCR provides the same ONNX-exported models at ~80MB, runs on CPU without any GPU or CUDA dependency, and is PyInstaller-compatible — consistent with the lean executable target of the md2pdf companion tool.

### Why PyMuPDF for Text Extraction

PyMuPDF's `page.get_text("dict")` returns not just raw text but font names, font sizes, bounding boxes, and block types — all essential for heading inference, code block detection, and image insertion at the correct Markdown position. It is the same engine used by md2pdf, ensuring consistent packaging and hooks.

### Output Mode Auto-Detection

Rather than requiring the user to pre-specify whether they want `.md` or `.zip`, the tool detects this at extraction time. If any images above the minimum size threshold are found, the output automatically switches to `.zip`. The user can override with `--output-dir` for a folder-based output preferred in Git workflows.

### Heading Inference Strategy

PDF does not encode semantic heading levels — only visual font sizes. The strategy maps the largest observed font size to H1, second-largest to H2, etc., relative to the document's body text size. This heuristic works well for typical reports and documentation PDFs, though heavily stylised PDFs may require manual post-editing.

---

## Future Enhancements (Backlog)

- [ ] Unit tests with pytest
- [ ] CI/CD pipeline (GitHub Actions) — build and release on tag push
- [ ] PyPI publishing for `pipx install pdf2md`
- [ ] Marker integration as optional high-accuracy backend (for complex layouts)
- [ ] Multi-column academic paper layout reflow
- [ ] LaTeX math block detection and conversion (via `pix2tex` or similar)
- [ ] Mermaid/SVG diagram pass-through
- [ ] `--page-range` option to convert specific pages only
- [ ] Batch mode: `pdf2md *.pdf --output-dir ./output/`
