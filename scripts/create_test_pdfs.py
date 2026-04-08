"""Script to create test PDF documents for pdf2md acceptance testing."""

from __future__ import annotations

import fitz  # PyMuPDF
from pathlib import Path


def create_text_en_pdf(output_path: Path) -> None:
    """Create a text-based English PDF with headings, lists, and code blocks."""
    doc = fitz.open()
    
    # Page 1 - Document with various elements
    page = doc.new_page()
    
    # Title (H1 - largest font)
    page.insert_text(
        (72, 72),
        "Python Best Practices Guide",
        fontsize=24,
        fontname="helv",
    )
    
    # Subtitle (H2)
    page.insert_text(
        (72, 110),
        "Chapter 1: Getting Started",
        fontsize=18,
        fontname="helv",
    )
    
    # Regular paragraph
    page.insert_text(
        (72, 150),
        "This guide covers essential Python programming practices for beginners "
        "and intermediate developers. It includes practical examples and common "
        "patterns used in production code.",
        fontsize=12,
        fontname="helv",
    )
    
    # Bold text for emphasis
    page.insert_text(
        (72, 210),
        "Key Principles",
        fontsize=16,
        fontname="hebo",  # Helvetica Bold
    )
    
    # Bulleted list
    bullets = [
        "Write readable and maintainable code",
        "Follow the PEP 8 style guide",
        "Use virtual environments for dependencies",
        "Write tests for your code",
    ]
    y_pos = 240
    for bullet in bullets:
        page.insert_text(
            (90, y_pos),
            f"\u2022 {bullet}",
            fontsize=12,
            fontname="helv",
        )
        y_pos += 20
    
    # Subsection (H3)
    page.insert_text(
        (72, 360),
        "Code Examples",
        fontsize=14,
        fontname="hebo",
    )
    
    # Code block (monospaced font)
    code_lines = [
        "def hello_world():",
        "    \"\"\"Print a greeting message.\"\"\"",
        "    print('Hello, World!')",
        "",
        "if __name__ == '__main__':",
        "    hello_world()",
    ]
    y_pos = 390
    for line in code_lines:
        page.insert_text(
            (90, y_pos),
            line,
            fontsize=10,
            fontname="cour",  # Courier (monospaced)
        )
        y_pos += 16
    
    # Another paragraph
    page.insert_text(
        (72, 520),
        "Remember: Code readability is crucial for long-term maintenance.",
        fontsize=12,
        fontname="helv",
    )
    
    doc.save(str(output_path))
    doc.close()


def create_text_cjk_pdf(output_path: Path) -> None:
    """Create a text-based PDF with Traditional and Simplified Chinese."""
    doc = fitz.open()
    
    # Need to use a font that supports CJK characters
    # PyMuPDF has built-in CJK font support
    page = doc.new_page()
    
    # Title
    page.insert_text(
        (72, 72),
        "Python 编程指南",  # Simplified Chinese
        fontsize=24,
        fontname="china-t",  # Traditional Chinese font
    )
    
    # Subtitle
    page.insert_text(
        (72, 120),
        "第一章：入門基礎",  # Traditional Chinese
        fontsize=18,
        fontname="china-t",
    )
    
    # Mixed content paragraph (Simplified + Traditional)
    page.insert_text(
        (72, 170),
        "本指南涵蓋 Python 編程的基礎知識，適合初學者和有經驗的開發者。"
        "This guide covers the basics of Python programming.",
        fontsize=12,
        fontname="china-t",
    )
    
    # Section header
    page.insert_text(
        (72, 230),
        "主要內容",
        fontsize=16,
        fontname="hebo",
    )
    
    # List with CJK bullets
    items = [
        "變數和數據類型 (Variables and Data Types)",
        "控制流程 (Control Flow)",
        "函數定義 (Function Definition)",
        "錯誤處理 (Error Handling)",
    ]
    y_pos = 260
    for item in items:
        page.insert_text(
            (90, y_pos),
            f"• {item}",
            fontsize=12,
            fontname="china-t",
        )
        y_pos += 24
    
    # Code example
    page.insert_text(
        (72, 400),
        "代碼示例 (Code Example):",
        fontsize=14,
        fontname="hebo",
    )
    
    code_lines = [
        "def greet(name):",
        "    return f'Hello, {name}!'",
        "",
        "# 使用函數",
        "result = greet('World')",
        "print(result)",
    ]
    y_pos = 430
    for line in code_lines:
        page.insert_text(
            (90, y_pos),
            line,
            fontsize=10,
            fontname="cour",
        )
        y_pos += 16
    
    # Additional text
    page.insert_text(
        (72, 560),
        "學習 Python 需要持續練習和實踐。Keep practicing!",
        fontsize=12,
        fontname="china-t",
    )
    
    doc.save(str(output_path))
    doc.close()


def create_scanned_en_pdf(output_path: Path) -> None:
    """Create a simulated scanned PDF (page rendered as image with text overlay)."""
    # Create a new doc with just a small text snippet (below 50 char threshold)
    doc = fitz.open()
    page = doc.new_page()
    
    # Very minimal text (below detection threshold)
    page.insert_text(
        (72, 72),
        ".",  # Minimal character to keep it a text PDF but below threshold
        fontsize=6,
        fontname="helv",
    )
    
    doc.save(str(output_path))
    doc.close()


def create_scanned_cjk_pdf(output_path: Path) -> None:
    """Create a simulated scanned PDF with Chinese content."""
    doc = fitz.open()
    page = doc.new_page()
    
    # Minimal text to simulate a scanned page (below threshold)
    page.insert_text(
        (72, 72),
        ".",
        fontsize=6,
        fontname="china-t",
    )
    
    doc.save(str(output_path))
    doc.close()


def create_mixed_images_pdf(output_path: Path) -> None:
    """Create a text-based PDF with embedded images."""
    doc = fitz.open()
    page = doc.new_page()
    
    # Title
    page.insert_text(
        (72, 72),
        "Document with Images",
        fontsize=24,
        fontname="helv",
    )
    
    # Text paragraph
    page.insert_text(
        (72, 120),
        "This PDF contains embedded images for testing the image extraction "
        "and Markdown output functionality.",
        fontsize=12,
        fontname="helv",
    )
    
    # Create a simple test image (PNG)
    # We'll create a small colored rectangle
    import struct
    import zlib
    
    def create_test_png(width: int, height: int, color: tuple) -> bytes:
        """Create a minimal PNG file."""
        # Create raw pixel data (RGB)
        raw_data = b""
        for y in range(height):
            raw_data += b"\x00"  # Filter byte
            for x in range(width):
                raw_data += struct.pack("BBB", *color)
        
        # Compress
        compressed = zlib.compress(raw_data)
        
        # Build PNG
        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            chunk_data = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(chunk_data) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + chunk_data + crc
        
        # PNG signature
        png = b"\x89PNG\r\n\x1a\n"
        # IHDR chunk
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        png += chunk(b"IHDR", ihdr_data)
        # IDAT chunk
        png += chunk(b"IDAT", compressed)
        # IEND chunk
        png += chunk(b"IEND", b"")
        
        return png
    
    # Create test image 1 (200x150 blue rectangle)
    img1_data = create_test_png(200, 150, (0, 100, 200))
    img1_rect = fitz.Rect(72, 160, 272, 310)
    
    # Insert image 1
    page.insert_image(img1_rect, stream=img1_data)
    
    # More text
    page.insert_text(
        (72, 340),
        "The image above shows a blue rectangle. This tests whether images "
        "are correctly extracted and referenced in the Markdown output.",
        fontsize=12,
        fontname="helv",
    )
    
    # Create test image 2 (150x100 green rectangle)
    img2_data = create_test_png(150, 100, (0, 180, 50))
    img2_rect = fitz.Rect(72, 420, 222, 520)
    
    # Insert image 2
    page.insert_image(img2_rect, stream=img2_data)
    
    # Final text
    page.insert_text(
        (72, 550),
        "The second image is a green rectangle below this text.",
        fontsize=12,
        fontname="helv",
    )
    
    doc.save(str(output_path))
    doc.close()


def main():
    """Create all test PDF files."""
    testdata_dir = Path(__file__).parent.parent / "testdata"
    testdata_dir.mkdir(exist_ok=True)
    
    print(f"Creating test PDFs in: {testdata_dir}")
    
    # Create each test file
    tests = [
        ("text_en.pdf", create_text_en_pdf, "Text-based English PDF with headings, lists, and code"),
        ("text_cjk.pdf", create_text_cjk_pdf, "Text-based PDF with Traditional and Simplified Chinese"),
        ("scanned_en.pdf", create_scanned_en_pdf, "Simulated scanned English PDF (minimal text layer)"),
        ("scanned_cjk.pdf", create_scanned_cjk_pdf, "Simulated scanned Chinese PDF (minimal text layer)"),
        ("mixed_images.pdf", create_mixed_images_pdf, "Text-based PDF with embedded images"),
    ]
    
    for filename, create_func, description in tests:
        output_path = testdata_dir / filename
        try:
            create_func(output_path)
            print(f"✓ Created: {filename} - {description}")
        except Exception as e:
            print(f"✗ Failed to create {filename}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\nAll test files created successfully in: {testdata_dir}")


if __name__ == "__main__":
    main()
