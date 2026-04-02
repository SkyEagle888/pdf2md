"""PyInstaller hook for RapidOCR.

Ensures ONNX model files are bundled with the executable.
"""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("rapidocr_onnxruntime")
