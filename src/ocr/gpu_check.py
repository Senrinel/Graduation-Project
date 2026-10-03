"""
GPU 偵測與強制檢查 (GPU Detection & Enforcement)
===================================================
使用者需求（2026-07-25，明確指示）：Step 4 OCR 必須使用 GPU 執行；
若偵測不到可用 GPU，程式必須直接終止，**禁止靜默改用 CPU**。

本模組獨立於 recognizer.py，職責單一：
1. `get_gpu_info()`：透過 torch.cuda API 正確讀取目前可用 GPU 資訊
   （裝置數量、名稱、顯示記憶體、CUDA capability）。
2. `ensure_gpu_available()`：作為每次啟動 OCR 前的強制檢查點，
   檢查失敗時印出清楚錯誤訊息並以 `sys.exit(1)` 終止程式。

刻意將 GPU 檢查獨立成模組（而非寫在 recognizer.py 內部），是為了：
- 可在 CLI 入口（scripts/run_phase3.py）一開始就先做檢查，
  避免程式先花時間匯入 easyocr / 讀取影格後才發現沒有 GPU。
- 可用 monkeypatch 對 torch.cuda 做單元測試，不需要真的有 GPU 硬體
  也能驗證「偵測不到 GPU 時是否正確終止」的邏輯（見 tests/test_gpu_check.py）。
"""

from __future__ import annotations

import sys

import torch


def get_gpu_info() -> list[dict]:
    """
    讀取目前系統可用的 GPU 資訊。

    Returns:
        list[dict]: 每個 GPU 一筆，欄位為 index / name / total_memory_gb / capability。
                    若無可用 GPU，回傳空列表。
    """
    if not torch.cuda.is_available():
        return []

    infos = []
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        infos.append({
            "index": i,
            "name": props.name,
            "total_memory_gb": round(props.total_memory / (1024 ** 3), 2),
            "capability": f"{props.major}.{props.minor}",
        })
    return infos


def ensure_gpu_available() -> list[dict]:
    """
    強制檢查 GPU 是否可用；不可用時直接終止程式。

    依使用者需求，這裡刻意不提供任何「fallback 用 CPU」的分支——
    偵測失敗就是 `sys.exit(1)`，不讓程式繼續往下執行。

    Returns:
        list[dict]: 偵測到的 GPU 資訊列表（保證至少一筆，否則已終止程式）。
    """
    gpu_info = get_gpu_info()

    if not gpu_info:
        print("=" * 60)
        print("[錯誤] 未偵測到可用的 GPU（torch.cuda.is_available() == False）。")
        print("本專案要求 Step 4 OCR 必須使用 GPU 執行，禁止靜默改用 CPU，程式終止。")
        print("請確認：")
        print("  1) 已安裝 NVIDIA GPU 並安裝對應驅動")
        print("  2) 已安裝支援 CUDA 的 torch 版本（而非 CPU-only 版本）")
        print("  3) CUDA_VISIBLE_DEVICES 環境變數未被設為空值或錯誤裝置編號")
        print("=" * 60)
        sys.exit(1)

    print(f"[GPU 檢查通過] 偵測到 {len(gpu_info)} 張可用 GPU：")
    for info in gpu_info:
        print(f"  - GPU {info['index']}: {info['name']}，"
              f"顯示記憶體 {info['total_memory_gb']} GB，CUDA capability {info['capability']}")
    return gpu_info
