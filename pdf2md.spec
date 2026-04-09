# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for pdf2md.

Builds a single-file Windows executable with all dependencies bundled,
including RapidOCR ONNX model files.

Usage:
    pyinstaller pdf2md.spec
"""

block_cipher = None

# SPECPATH is injected by PyInstaller and points to the directory containing this .spec file
a = Analysis(
    ["src/pdf2md/cli.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pdf2md",
        "pdf2md.analyser",
        "pdf2md.images",
        "pdf2md.ocr",
        "pdf2md.builder",
        "pdf2md.output",
        "pdf2md.logging",
        "fitz",
        "rapidocr_onnxruntime",
        "PIL",
    ],
    hookspath=["hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "numpy.testing",
        "pytest",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pdf2md",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Single-file output
    onefile=True,
)
