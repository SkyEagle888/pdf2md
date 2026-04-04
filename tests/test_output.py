"""Tests for pdf2md output module."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pdf2md.images import ExtractedImage
from pdf2md.output import OutputWriter


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_extracted_image(
    page_number: int = 1,
    image_index: int = 1,
    filename: str | None = None,
    width: int = 200,
    height: int = 150,
    y0: float = 100.0,
    data: bytes = b"fake-png-data",
) -> ExtractedImage:
    """Create an ``ExtractedImage`` with sensible defaults."""
    return ExtractedImage(
        page_number=page_number,
        image_index=image_index,
        filename=filename or f"page{page_number}_img{image_index}.png",
        width=width,
        height=height,
        y0=y0,
        data=data,
    )


SAMPLE_MD = "# Title\n\nSome body text.\n"
INPUT_PDF = "/some/path/document.pdf"


# ---------------------------------------------------------------------------
# OutputWriter initialisation tests
# ---------------------------------------------------------------------------


class TestOutputWriterInit:
    def test_defaults(self):
        writer = OutputWriter()
        assert writer.output_path is None
        assert writer.output_dir is None

    def test_explicit_output_path(self):
        writer = OutputWriter(output_path="out.md")
        assert writer.output_path == Path("out.md")
        assert writer.output_dir is None

    def test_explicit_output_dir(self):
        writer = OutputWriter(output_dir="./out_dir")
        assert writer.output_dir == Path("./out_dir")
        assert writer.output_path is None

    def test_both_set(self):
        writer = OutputWriter(output_path="out.md", output_dir="./out_dir")
        assert writer.output_path == Path("out.md")
        assert writer.output_dir == Path("./out_dir")


# ---------------------------------------------------------------------------
# _determine_output_mode tests
# ---------------------------------------------------------------------------


class TestDetermineOutputMode:
    def test_output_dir_set_returns_dir_mode(self):
        writer = OutputWriter(output_dir="./output")
        mode, target = writer._determine_output_mode([], INPUT_PDF)
        assert mode == "dir"
        assert target == Path("./output")

    def test_output_dir_set_overrides_images(self):
        """Even with images, output_dir forces dir mode."""
        writer = OutputWriter(output_dir="./output")
        images = [_make_extracted_image()]
        mode, target = writer._determine_output_mode(images, INPUT_PDF)
        assert mode == "dir"
        assert target == Path("./output")

    def test_explicit_md_path_returns_md_mode(self):
        writer = OutputWriter(output_path="custom.md")
        mode, target = writer._determine_output_mode([], INPUT_PDF)
        assert mode == "md"
        assert target == Path("custom.md")

    def test_explicit_zip_path_returns_zip_mode(self):
        writer = OutputWriter(output_path="custom.zip")
        mode, target = writer._determine_output_mode([], INPUT_PDF)
        assert mode == "zip"
        assert target == Path("custom.zip")

    def test_explicit_zip_path_with_images_returns_zip_mode(self):
        writer = OutputWriter(output_path="custom.zip")
        images = [_make_extracted_image()]
        mode, target = writer._determine_output_mode(images, INPUT_PDF)
        assert mode == "zip"
        assert target == Path("custom.zip")

    def test_explicit_unknown_extension_returns_md_mode(self):
        writer = OutputWriter(output_path="custom.txt")
        mode, target = writer._determine_output_mode([], INPUT_PDF)
        assert mode == "md"
        assert target == Path("custom.txt")

    def test_no_explicit_path_no_images_returns_md_mode(self):
        writer = OutputWriter()
        mode, target = writer._determine_output_mode([], INPUT_PDF)
        assert mode == "md"
        assert target == Path("document.md")

    def test_no_explicit_path_with_images_returns_zip_mode(self):
        writer = OutputWriter()
        images = [_make_extracted_image()]
        mode, target = writer._determine_output_mode(images, INPUT_PDF)
        assert mode == "zip"
        assert target == Path("document.zip")

    def test_input_path_stem_used_for_default_naming(self):
        writer = OutputWriter()
        mode, target = writer._determine_output_mode([], "/a/b/my_report.pdf")
        assert mode == "md"
        assert target == Path("my_report.md")

    def test_input_path_stem_with_images(self):
        writer = OutputWriter()
        images = [_make_extracted_image()]
        mode, target = writer._determine_output_mode(images, "/a/b/my_report.pdf")
        assert mode == "zip"
        assert target == Path("my_report.zip")


# ---------------------------------------------------------------------------
# validate_output tests
# ---------------------------------------------------------------------------


class TestValidateOutput:
    def test_no_paths_set_is_valid(self):
        writer = OutputWriter()
        valid, error = writer.validate_output()
        assert valid is True
        assert error is None

    def test_existing_writable_dir_is_valid(self, tmp_path: Path):
        writer = OutputWriter(output_dir=str(tmp_path))
        valid, error = writer.validate_output()
        assert valid is True
        assert error is None

    def test_nonexistent_dir_with_writable_parent_is_valid(self, tmp_path: Path):
        subdir = tmp_path / "sub" / "output"
        writer = OutputWriter(output_dir=str(subdir))
        valid, error = writer.validate_output()
        assert valid is True
        assert error is None

    def test_existing_path_that_is_not_directory(self, tmp_path: Path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("hello")
        writer = OutputWriter(output_dir=str(file_path))
        valid, error = writer.validate_output()
        assert valid is False
        assert "not a directory" in (error or "")

    def test_nonexistent_dir_parent_does_not_exist(self):
        """Use a UNC path whose parent truly doesn't exist on any platform."""
        writer = OutputWriter(output_dir=r"\\nonexistent_host\share\dir")
        valid, error = writer.validate_output()
        assert valid is False
        assert "parent does not exist" in (error or "")

    def test_explicit_output_path_parent_exists(self, tmp_path: Path):
        out_file = tmp_path / "output.md"
        writer = OutputWriter(output_path=str(out_file))
        valid, error = writer.validate_output()
        assert valid is True
        assert error is None

    def test_explicit_output_path_parent_not_exists(self):
        """Use a UNC path that has no existing parent."""
        writer = OutputWriter(output_path=r"\\nonexistent_host\share\file.md")
        valid, error = writer.validate_output()
        assert valid is False
        assert "does not exist" in (error or "")


# ---------------------------------------------------------------------------
# write — md-only mode tests
# ---------------------------------------------------------------------------


class TestWriteMarkdownOnly:
    def test_writes_md_file(self, tmp_path: Path):
        out_file = tmp_path / "result.md"
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write(SAMPLE_MD, [], INPUT_PDF)
        assert result == out_file
        assert out_file.read_text(encoding="utf-8") == SAMPLE_MD

    def test_creates_parent_directories(self, tmp_path: Path):
        out_file = tmp_path / "sub" / "dir" / "result.md"
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write(SAMPLE_MD, [], INPUT_PDF)
        assert result == out_file
        assert out_file.exists()

    def test_default_naming_no_images(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        writer = OutputWriter()
        result = writer.write(SAMPLE_MD, [], INPUT_PDF)
        # When no explicit path is given, the result is a relative path
        # written in the current working directory
        assert result == Path("document.md")
        assert result.resolve() == tmp_path / "document.md"
        assert result.read_text(encoding="utf-8") == SAMPLE_MD

    def test_empty_markdown(self, tmp_path: Path):
        out_file = tmp_path / "empty.md"
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write("", [], INPUT_PDF)
        assert result == out_file
        assert out_file.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# write — zip bundle tests
# ---------------------------------------------------------------------------


class TestWriteZipBundle:
    def test_creates_zip_with_md_and_images(self, tmp_path: Path):
        out_file = tmp_path / "bundle.zip"
        images = [
            _make_extracted_image(1, 1, data=b"img1"),
            _make_extracted_image(1, 2, data=b"img2"),
        ]
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write(SAMPLE_MD, images, INPUT_PDF)
        assert result == out_file
        assert out_file.exists()
        assert out_file.stat().st_size > 0

        with zipfile.ZipFile(out_file, "r") as zf:
            names = zf.namelist()
            assert "bundle.md" in names
            assert "images/page1_img1.png" in names
            assert "images/page1_img2.png" in names
            assert zf.read("bundle.md").decode("utf-8") == SAMPLE_MD
            assert zf.read("images/page1_img1.png") == b"img1"
            assert zf.read("images/page1_img2.png") == b"img2"

    def test_zip_uses_deflated_compression(self, tmp_path: Path):
        out_file = tmp_path / "bundle.zip"
        images = [_make_extracted_image()]
        writer = OutputWriter(output_path=str(out_file))
        writer.write(SAMPLE_MD, images, INPUT_PDF)

        with zipfile.ZipFile(out_file, "r") as zf:
            for info in zf.infolist():
                assert info.compress_type == zipfile.ZIP_DEFLATED

    def test_default_naming_with_images(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        writer = OutputWriter()
        images = [_make_extracted_image()]
        result = writer.write(SAMPLE_MD, images, INPUT_PDF)
        # When no explicit path is given, the result is a relative path
        assert result == Path("document.zip")
        assert result.resolve() == tmp_path / "document.zip"
        assert result.exists()

    def test_zip_stem_used_for_md_name(self, tmp_path: Path):
        out_file = tmp_path / "my_output.zip"
        images = [_make_extracted_image()]
        writer = OutputWriter(output_path=str(out_file))
        writer.write(SAMPLE_MD, images, INPUT_PDF)

        with zipfile.ZipFile(out_file, "r") as zf:
            assert "my_output.md" in zf.namelist()

    def test_creates_parent_directories(self, tmp_path: Path):
        out_file = tmp_path / "sub" / "deep" / "bundle.zip"
        images = [_make_extracted_image()]
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write(SAMPLE_MD, images, INPUT_PDF)
        assert result == out_file
        assert out_file.exists()


# ---------------------------------------------------------------------------
# write — directory mode tests
# ---------------------------------------------------------------------------


class TestWriteToDirectory:
    def test_writes_md_and_images(self, tmp_path: Path):
        out_dir = tmp_path / "output"
        images = [
            _make_extracted_image(1, 1, data=b"img1"),
            _make_extracted_image(2, 1, data=b"img2"),
        ]
        writer = OutputWriter(output_dir=str(out_dir))
        result = writer.write(SAMPLE_MD, images, INPUT_PDF)
        assert result == out_dir
        assert (out_dir / "document.md").exists()
        assert (out_dir / "document.md").read_text(encoding="utf-8") == SAMPLE_MD
        assert (out_dir / "images" / "page1_img1.png").exists()
        assert (out_dir / "images" / "page1_img1.png").read_bytes() == b"img1"
        assert (out_dir / "images" / "page2_img1.png").exists()
        assert (out_dir / "images" / "page2_img1.png").read_bytes() == b"img2"

    def test_writes_md_only_when_no_images(self, tmp_path: Path):
        out_dir = tmp_path / "output"
        writer = OutputWriter(output_dir=str(out_dir))
        result = writer.write(SAMPLE_MD, [], INPUT_PDF)
        assert result == out_dir
        assert (out_dir / "document.md").exists()
        assert not (out_dir / "images").exists()

    def test_creates_directory_if_not_exists(self, tmp_path: Path):
        out_dir = tmp_path / "new_dir" / "nested"
        writer = OutputWriter(output_dir=str(out_dir))
        result = writer.write(SAMPLE_MD, [], INPUT_PDF)
        assert result == out_dir
        assert out_dir.exists()

    def test_existing_directory_is_reused(self, tmp_path: Path):
        out_dir = tmp_path / "existing"
        out_dir.mkdir()
        writer = OutputWriter(output_dir=str(out_dir))
        result = writer.write(SAMPLE_MD, [], INPUT_PDF)
        assert result == out_dir

    def test_image_data_written_correctly(self, tmp_path: Path):
        out_dir = tmp_path / "output"
        img_data = b"\x89PNG\r\n\x1a\nfake-image-bytes"
        images = [_make_extracted_image(1, 1, data=img_data)]
        writer = OutputWriter(output_dir=str(out_dir))
        writer.write(SAMPLE_MD, images, INPUT_PDF)
        img_path = out_dir / "images" / "page1_img1.png"
        assert img_path.read_bytes() == img_data

    def test_multiple_pages_images_sorted(self, tmp_path: Path):
        out_dir = tmp_path / "output"
        images = [
            _make_extracted_image(2, 1, data=b"p2i1"),
            _make_extracted_image(1, 1, data=b"p1i1"),
            _make_extracted_image(1, 2, data=b"p1i2"),
        ]
        writer = OutputWriter(output_dir=str(out_dir))
        writer.write(SAMPLE_MD, images, INPUT_PDF)
        images_dir = out_dir / "images"
        assert (images_dir / "page1_img1.png").read_bytes() == b"p1i1"
        assert (images_dir / "page1_img2.png").read_bytes() == b"p1i2"
        assert (images_dir / "page2_img1.png").read_bytes() == b"p2i1"


# ---------------------------------------------------------------------------
# Integration-style tests (full write flow)
# ---------------------------------------------------------------------------


class TestWriteIntegration:
    def test_full_flow_md_auto_detect(self, tmp_path: Path, monkeypatch):
        """No images, no explicit output → auto .md file."""
        monkeypatch.chdir(tmp_path)
        writer = OutputWriter()
        result = writer.write("# Doc\n\nBody\n", [], "/path/to/report.pdf")
        assert result.suffix == ".md"
        assert result.name == "report.md"
        assert result.read_text(encoding="utf-8") == "# Doc\n\nBody\n"

    def test_full_flow_zip_auto_detect(self, tmp_path: Path, monkeypatch):
        """Images, no explicit output → auto .zip bundle."""
        monkeypatch.chdir(tmp_path)
        writer = OutputWriter()
        images = [_make_extracted_image(data=b"pixel")]
        result = writer.write("# Doc\n\nBody\n", images, "/path/to/report.pdf")
        assert result.suffix == ".zip"
        assert result.name == "report.zip"
        with zipfile.ZipFile(result, "r") as zf:
            assert "report.md" in zf.namelist()
            assert "images/page1_img1.png" in zf.namelist()

    def test_full_force_zip_with_no_images(self, tmp_path: Path):
        """User explicitly requests .zip even without images."""
        out_file = tmp_path / "forced.zip"
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write("# Doc\n", [], INPUT_PDF)
        assert result == out_file
        with zipfile.ZipFile(result, "r") as zf:
            assert "forced.md" in zf.namelist()
            # No images/ directory in the zip
            assert not any(n.startswith("images/") for n in zf.namelist())

    def test_full_force_md_with_images(self, tmp_path: Path):
        """User explicitly requests .md even with images (images dropped)."""
        out_file = tmp_path / "forced.md"
        images = [_make_extracted_image()]
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write("# Doc\n", images, INPUT_PDF)
        assert result == out_file
        assert result.read_text(encoding="utf-8") == "# Doc\n"

    def test_full_dir_mode_with_images(self, tmp_path: Path):
        """Output dir + images → directory with .md and images/."""
        out_dir = tmp_path / "out"
        writer = OutputWriter(output_dir=str(out_dir))
        images = [_make_extracted_image(data=b"data")]
        result = writer.write("# Report\n", images, INPUT_PDF)
        assert result == out_dir
        assert (out_dir / "document.md").exists()
        assert (out_dir / "images" / "page1_img1.png").exists()


# ---------------------------------------------------------------------------
# Edge cases and error handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_images_list_handled_gracefully(self, tmp_path: Path):
        out_dir = tmp_path / "output"
        writer = OutputWriter(output_dir=str(out_dir))
        result = writer.write("Markdown", [], INPUT_PDF)
        assert result == out_dir
        assert not (out_dir / "images").exists()

    def test_unicode_markdown(self, tmp_path: Path):
        out_file = tmp_path / "unicode.md"
        md = "# 标题\n\n中文内容\n\n© 2024\n"
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write(md, [], INPUT_PDF)
        assert result.read_text(encoding="utf-8") == md

    def test_large_image_data(self, tmp_path: Path):
        out_dir = tmp_path / "output"
        large_data = b"x" * (1024 * 1024)  # 1 MB
        images = [_make_extracted_image(data=large_data)]
        writer = OutputWriter(output_dir=str(out_dir))
        result = writer.write("# Doc\n", images, INPUT_PDF)
        assert (out_dir / "images" / "page1_img1.png").read_bytes() == large_data

    def test_output_path_with_dots_in_name(self, tmp_path: Path):
        """File names containing dots should still work."""
        out_file = tmp_path / "my.report.final.md"
        writer = OutputWriter(output_path=str(out_file))
        result = writer.write(SAMPLE_MD, [], INPUT_PDF)
        assert result == out_file
        assert result.read_text(encoding="utf-8") == SAMPLE_MD

    def test_zip_name_preserves_stem_with_dots(self, tmp_path: Path):
        """my.report.final.zip → my.report.final.md inside."""
        out_file = tmp_path / "my.report.final.zip"
        images = [_make_extracted_image()]
        writer = OutputWriter(output_path=str(out_file))
        writer.write(SAMPLE_MD, images, INPUT_PDF)
        with zipfile.ZipFile(out_file, "r") as zf:
            assert "my.report.final.md" in zf.namelist()
