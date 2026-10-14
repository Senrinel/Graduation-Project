"""
獨立硬體運算裝置檢查腳本 (Hardware Device Check)
==============================================
獨立確認系統可用之運算裝置（優先檢測 GPU，無則說明 CPU 降級相容），
方便排查環境問題。

用法：
    python scripts/check_gpu.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ocr.gpu_check import detect_compute_device  # noqa: E402


if __name__ == "__main__":
    use_gpu, device_type, gpu_info = detect_compute_device(verbose=True)
    if use_gpu:
        print(f"\n[檢查結果] GPU 硬體環境健全，將獲得最佳執行效能。")
    else:
        print(f"\n[檢查結果] 未偵測到可用 GPU，系統將在 CPU 模式下相容執行。")
