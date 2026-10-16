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

import argparse
import subprocess

from src.ocr.gpu_check import check_nvidia_hardware, detect_compute_device  # noqa: E402


def fix_cuda_torch() -> bool:
    print("[自動修復] 正在為您重新安裝支援 CUDA 12.6 的 PyTorch 與 Torchvision...")
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--force-reinstall", "--no-deps",
        "torch", "torchvision",
        "--index-url", "https://download.pytorch.org/whl/cu126",
    ]
    res = subprocess.run(cmd)
    return res.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="檢查 GPU 與硬體運算環境")
    parser.add_argument("--fix", action="store_true", help="若實體具備 NVIDIA GPU 但 PyTorch 缺少 CUDA，自動重新安裝 CUDA 版 PyTorch")
    args = parser.parse_args()

    use_gpu, device_type, gpu_info = detect_compute_device(verbose=True)
    has_hw, hw_name = check_nvidia_hardware()

    if use_gpu:
        print("\n[檢查結果] GPU 硬體環境健全，將獲得最佳執行效能。")
    elif has_hw:
        print(f"\n[檢查結果] 警告：偵測到實體顯卡 ({hw_name})，但 PyTorch 目前缺少 CUDA 支援！")
        if args.fix:
            if fix_cuda_torch():
                print("\n[修復完成] 重新驗證中：")
                detect_compute_device(verbose=True)
            else:
                print("\n[修復失敗] 請手動執行修復指令。")
        else:
            print("提示：可加上 --fix 參數自動修復： python scripts/check_gpu.py --fix")
    else:
        print("\n[檢查結果] 未偵測到可用 GPU，系統將在 CPU 模式下相容執行。")

