"""PyInstaller hook for RapidOCR.

Ensures ONNX model files, configuration, and all submodules are bundled
with the executable. RapidOCR loads its .onnx models from the filesystem
at runtime, so PyInstaller must be told to include them as data files.

Note: collect_data_files may return empty for packages installed via uv
that don't declare data files in their RECORD metadata. We use a manual
approach to find and bundle the files.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# Ensure all submodules are discovered
hiddenimports = collect_submodules("rapidocr_onnxruntime")

# Find the rapidocr_onnxruntime package directory
try:
    import rapidocr_onnxruntime as _r
    _pkg_dir = Path(_r.__file__).resolve().parent
except ImportError:
    _pkg_dir = None

datas = []
if _pkg_dir is not None and _pkg_dir.exists():
    # Collect all non-Python, non-pycache files from the package
    for root, _dirs, files in os.walk(_pkg_dir):
        for fname in files:
            src_path = Path(root) / fname
            # Skip compiled Python files
            if fname.endswith((".pyc", ".pyo")):
                continue
            # Compute destination path within the bundle
            rel_path = src_path.relative_to(_pkg_dir.parent)
            dst_dir = str(rel_path.parent)
            datas.append((str(src_path), dst_dir))
