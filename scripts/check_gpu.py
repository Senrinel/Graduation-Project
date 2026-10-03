"""
獨立 GPU 檢查腳本
====================
本機測試前的第一步：獨立確認 torch 能正確偵測到 GPU，
邏輯與 Phase 3（run_phase3.py）執行前做的檢查完全相同（都是呼叫
`src.ocr.gpu_check.ensure_gpu_available()`），差別只是不會接著跑 OCR，
方便單獨排查環境問題。

用法：
    python scripts/check_gpu.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ocr.gpu_check import ensure_gpu_available  # noqa: E402


if __name__ == "__main__":
    ensure_gpu_available()
    print("GPU 檢查通過，可以繼續執行 scripts/run_phase3.py。")
