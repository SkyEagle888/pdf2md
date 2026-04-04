"""Output writer for pdf2md — writes .md files or .zip bundles."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from pdf2md.images import ExtractedImage
from pdf2md.logging import get_logger

logger = get_logger()


class OutputWriter:
    """Handles writing conversion output as a single .md file or a .zip bundle."""

    def __init__(
        self,
        output_path: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        """Initialise the output writer.

        Args:
            output_path: Explicit output file path (.md or .zip).
            output_dir: Output directory (overrides *output_path* for directory
                mode when set).
        """
        self.output_path = Path(output_path) if output_path else None
        self.output_dir = Path(output_dir) if output_dir else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(
        self,
        markdown: str,
        images: list[ExtractedImage],
        input_path: str,
    ) -> Path:
        """Write the conversion output.

        The output mode is chosen automatically:

        * No images → single ``.md`` file.
        * Images present and ``--output-dir`` not set → ``.zip`` bundle.
        * Images present and ``--output-dir`` set → directory with ``.md``
          and ``images/`` sub-folder.

        Args:
            markdown: Complete Markdown string.
            images: List of extracted images.
            input_path: Original input PDF path (used for default naming).

        Returns:
            Path to the created output file or directory.

        Raises:
            OSError: If the output path is not writable.
        """
        mode, target = self._determine_output_mode(images, input_path)

        if mode == "md":
            return self._write_markdown_only(markdown, target)
        if mode == "zip":
            return self._write_zip_bundle(markdown, images, target)
        # mode == "dir"
        md_filename = target.name
        if not md_filename.endswith(".md"):
            md_filename = f"{Path(input_path).stem}.md"
        return self._write_to_directory(markdown, images, target, md_filename)

    def validate_output(self) -> tuple[bool, str | None]:
        """Validate that the output path is writable.

        Returns:
            ``(True, None)`` when valid, ``(False, error_message)`` when
            invalid.
        """
        try:
            if self.output_dir:
                target = self.output_dir.resolve()
                if target.exists():
                    if not target.is_dir():
                        return (
                            False,
                            f"Output path exists but is not a directory: {self.output_dir}",
                        )
                    if not os.access(target, os.W_OK):
                        return (
                            False,
                            f"Output directory is not writable: {self.output_dir}",
                        )
                else:
                    # Walk up a few levels to find an existing ancestor
                    ancestor = target
                    for _ in range(10):  # Limit depth to avoid reaching root
                        if ancestor.parent.exists():
                            break
                        ancestor = ancestor.parent
                    else:
                        # Walked to root without finding existing parent
                        return (
                            False,
                            f"Cannot create output directory, parent does not exist: {target.parent}",
                        )
                    existing_parent = ancestor.parent
                    if not os.access(existing_parent, os.W_OK):
                        return (
                            False,
                            f"Cannot create output directory, parent is not writable: {existing_parent}",
                        )
            elif self.output_path:
                parent = self.output_path.resolve().parent
                if not parent.exists():
                    return (
                        False,
                        f"Output directory does not exist: {parent}",
                    )
                if not os.access(parent, os.W_OK):
                    return (
                        False,
                        f"Output directory is not writable: {parent}",
                    )

            return True, None
        except Exception as exc:  # noqa: BLE001 — surface actionable message
            return False, f"Output validation failed: {exc}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _determine_output_mode(
        self,
        images: list[ExtractedImage],
        input_path: str,
    ) -> tuple[str, Path]:
        """Determine output file path and mode.

        Returns:
            Tuple of ``(mode, output_path)`` where *mode* is one of
            ``'md'``, ``'zip'``, or ``'dir'``.
        """
        input_stem = Path(input_path).stem

        # 1. Explicit output directory → dir mode
        if self.output_dir:
            return ("dir", self.output_dir)

        # 2. Explicit output path → infer from extension
        if self.output_path:
            ext = self.output_path.suffix.lower()
            if ext == ".zip":
                return ("zip", self.output_path)
            # .md or anything else → md mode
            return ("md", self.output_path)

        # 3. No explicit path — auto-detect
        if images:
            return ("zip", Path(f"{input_stem}.zip"))
        return ("md", Path(f"{input_stem}.md"))

    def _write_markdown_only(
        self,
        markdown: str,
        output_path: Path,
    ) -> Path:
        """Write a single ``.md`` file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        logger.info(f"Output written: {output_path}")
        return output_path

    def _write_zip_bundle(
        self,
        markdown: str,
        images: list[ExtractedImage],
        output_path: Path,
    ) -> Path:
        """Create a ``.zip`` file containing the ``.md`` and ``images/``."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        md_name = f"{output_path.stem}.md"

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(md_name, markdown)
            for image in images:
                arc_name = f"images/{image.filename}"
                zf.writestr(arc_name, image.data)

        file_size = output_path.stat().st_size
        logger.info(f"Output written: {output_path} ({file_size:,} bytes)")
        return output_path

    def _write_to_directory(
        self,
        markdown: str,
        images: list[ExtractedImage],
        output_dir: Path,
        md_filename: str,
    ) -> Path:
        """Write ``.md`` and ``images/`` to a directory."""
        output_dir.mkdir(parents=True, exist_ok=True)

        md_path = output_dir / md_filename
        md_path.write_text(markdown, encoding="utf-8")

        if images:
            images_dir = output_dir / "images"
            images_dir.mkdir(exist_ok=True)
            for image in images:
                img_path = images_dir / image.filename
                img_path.write_bytes(image.data)

        logger.info(f"Output written to: {output_dir}")
        return output_dir
