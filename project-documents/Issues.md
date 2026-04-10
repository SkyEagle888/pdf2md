# pdf2md — Known Issues & Suggested Improvements

> **Source:** Analysis based on converting `Venchi-Stamp.pdf` to `Venchi-Stamp.md`
> **Date:** 2026-04-10
> **File:** `src/pdf2md/builder.py`

---

## Issue 1 — Bold Fallback Promotes Bullet Text to `###` Headings

**Severity:** High
**Status:** Open

### Description

In `_get_heading_level()`, there is a fallback rule that promotes **any bold, non-italic text block** to an H3 heading regardless of its content:

```python
# Current problematic code in builder.py
if block.is_bold and not block.is_italic:
    return min(3, self.max_heading_level)
```

Many PDFs render bullet body text in bold font. This causes every bullet point line to be output as `### • Text...` instead of a proper list item. The result is a `.md` file saturated with `###` headings, making the preview look like an outline rather than a document.

### Suggested Fix

Guard the bold fallback with:
1. A bullet/numbered prefix check — bullet text should never become a heading.
2. A word-count limit — real headings are short phrases, not full sentences.

```python
def _get_heading_level(self, block: TextBlock) -> int | None:
    # Never treat bullet/numbered lines as headings
    if self._is_bullet(block.text) or self._is_numbered(block.text):
        return None

    # Exact font size match from size map
    if block.font_size in self._font_size_map:
        return self._font_size_map[block.font_size]

    # Bold fallback — only apply to short lines (likely a real title)
    if block.is_bold and not block.is_italic:
        word_count = len(block.text.split())
        if word_count <= 10:
            return min(3, self.max_heading_level)

    return None
```

---

## Issue 2 — Font Size Map Does Not Filter Near-Body Sizes

**Severity:** High
**Status:** Open

### Description

`_build_font_size_map()` naively maps the top N distinct font sizes to H1–H4 without checking whether those sizes are meaningfully larger than body text. In many PDFs (especially business documents), body text and bullet text differ by only 0.5–1pt, causing body-size text to be mapped as a heading level.

```python
# Current code — maps ALL top N sizes regardless of gap
for i, size in enumerate(sorted_sizes):
    if i < self.max_heading_level:
        size_map[size] = i + 1
```

### Suggested Fix

Add a minimum size difference threshold relative to the smallest (body) font size:

```python
body_size = sorted_sizes[-1]  # smallest size = body text
MIN_HEADING_SIZE_DIFF = 1.5   # minimum pt difference to qualify as heading

size_map: dict[float, int] = {}
for i, size in enumerate(sorted_sizes):
    if i < self.max_heading_level and (size - body_size) >= MIN_HEADING_SIZE_DIFF:
        size_map[size] = i + 1
```

---

## Issue 3 — List Detection Threshold Too Strict (50%)

**Severity:** Medium
**Status:** Open

### Description

`_detect_and_build_list()` requires at least **50% of blocks** in a paragraph group to match bullet or numbered patterns before treating the group as a list:

```python
if (bullet_count + numbered_count) < total * 0.5:
    return None
```

When a PDF wraps long bullet text across multiple `TextBlock` entries (continuation lines without a bullet prefix), the ratio drops below 50% and the entire paragraph falls through to the heading path — causing those continuation lines to also become headings.

### Suggested Fix

Lower the threshold to 30% and additionally treat continuation lines (non-matching blocks inside a list group) as list continuations rather than separate headings:

```python
# Be more lenient — 30% triggers list mode
if (bullet_count + numbered_count) < total * 0.3:
    return None
```

---

## Issue 4 — No CLI Option to Cap Heading Level

**Severity:** Low
**Status:** Open

### Description

`max_heading_level` is already a constructor parameter of `MarkdownBuilder` (default: 4), but it is not exposed in the CLI. Users converting document-type PDFs (proposals, specs, reports) cannot limit heading generation from the command line. A `--max-heading-level 2` flag would prevent `###` and `####` from appearing entirely for such documents.

### Suggested Fix

Expose the parameter in `cli.py`:

```python
parser.add_argument(
    "--max-heading-level",
    type=int,
    default=4,
    choices=[1, 2, 3, 4, 5, 6],
    help="Maximum heading level to infer from font sizes (default: 4). "
         "Use 2 for business documents to suppress ### and ####."
)
```

Then pass it through to the builder:

```python
builder = MarkdownBuilder(
    add_page_breaks=args.page_breaks,
    max_heading_level=args.max_heading_level,
)
```

---

## Issue 5 — Bullet Pattern May Not Match All `•` Variants in PDFs

**Severity:** Medium
**Status:** Open

### Description

`BULLET_PATTERNS` in `builder.py` includes `•` in the first regex:

```python
re.compile(r"^[•\-\*·○■]\s+"),
```

However, some PDFs encode bullet characters using different Unicode code points (e.g., `U+2022` vs `U+00B7` vs ligature substitutions). If the bullet character in the extracted text does not match any pattern in `BULLET_PATTERNS`, the block is not identified as a list item and falls through to heading detection.

### Suggested Fix

Expand `BULLET_PATTERNS` to cover additional Unicode bullet variants, and add a catch-all for common PDF bullet encodings:

```python
BULLET_PATTERNS = [
    re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219\-\*·○■◦▪▸►]\s+"),
    re.compile(r"^[-*+]\s+"),
    re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*"),
    re.compile(r"^[（(]\d+[）)]\s*"),
]
```

---

## Summary

| # | Issue | File | Severity | Status |
|---|-------|------|----------|--------|
| 1 | Bold fallback promotes bullets to `###` | `builder.py` `_get_heading_level()` | High | Open |
| 2 | Font size map includes near-body sizes as headings | `builder.py` `_build_font_size_map()` | High | Open |
| 3 | List detection threshold too strict (50%) | `builder.py` `_detect_and_build_list()` | Medium | Open |
| 4 | No CLI flag to cap heading level | `cli.py` | Low | Open |
| 5 | Bullet pattern may miss PDF Unicode variants | `builder.py` `BULLET_PATTERNS` | Medium | Open |
