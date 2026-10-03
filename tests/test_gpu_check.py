"""
GPU 強制檢查邏輯測試
======================
本測試環境（沙盒）沒有安裝真正的 torch（無法連線至 CUDA wheel
索引，且完整 PyPI torch 套件含 CUDA 動態庫，體積達 GB 等級，不適合
在此環境安裝）。

為了不需要真的裝 torch 或真的有 GPU 硬體，也能驗證
`src.ocr.gpu_check` 的判斷邏輯是否正確，這裡改用
`sys.modules["torch"]` 注入一個假的 torch 模組（只實作
`torch.cuda.is_available` / `device_count` / `get_device_properties`
三個 gpu_check.py 實際會呼叫到的介面）。

測試涵蓋兩種分支：
1. 無 GPU：`ensure_gpu_available()` 必須以 SystemExit 終止程式
   （對應使用者需求「若程式使用的是 CPU 則終止」）。
2. 有 GPU：`get_gpu_info()` 必須正確回傳裝置資訊，
   `ensure_gpu_available()` 不應終止程式。

真正在有 GPU 的機器上，torch.cuda 是否正確識別實體 GPU 屬於
PyTorch/CUDA 驅動本身的責任，不在本專案測試範圍內；本測試只驗證
「gpu_check.py 拿到 torch 回報的資訊後，判斷與終止邏輯是否正確」。
"""

from __future__ import annotations

import importlib
import sys
import types

import pytest


def _install_fake_torch(monkeypatch, available: bool, devices: list[dict] | None = None):
    """在 sys.modules 注入假的 torch 模組，模擬 torch.cuda 的行為。"""
    devices = devices or []
    device_props = [types.SimpleNamespace(**d) for d in devices]

    fake_cuda = types.SimpleNamespace(
        is_available=lambda: available,
        device_count=lambda: len(device_props),
        get_device_properties=lambda i: device_props[i],
    )
    fake_torch = types.SimpleNamespace(cuda=fake_cuda)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    # gpu_check 可能已被前一個測試 import 過（並綁定到舊的 torch），
    # 用 reload 確保它重新綁定到這次注入的假 torch。
    import src.ocr.gpu_check as gpu_check
    importlib.reload(gpu_check)
    return gpu_check


def test_no_gpu_returns_empty_info(monkeypatch):
    gpu_check = _install_fake_torch(monkeypatch, available=False)
    assert gpu_check.get_gpu_info() == []


def test_no_gpu_terminates_program(monkeypatch):
    gpu_check = _install_fake_torch(monkeypatch, available=False)
    with pytest.raises(SystemExit) as exc_info:
        gpu_check.ensure_gpu_available()
    assert exc_info.value.code == 1


def test_gpu_available_returns_correct_info(monkeypatch):
    fake_device = {
        "name": "NVIDIA GeForce RTX 4090",
        "total_memory": 24 * 1024 ** 3,
        "major": 8,
        "minor": 9,
    }
    gpu_check = _install_fake_torch(monkeypatch, available=True, devices=[fake_device])

    info = gpu_check.get_gpu_info()
    assert len(info) == 1
    assert info[0]["name"] == "NVIDIA GeForce RTX 4090"
    assert info[0]["total_memory_gb"] == 24.0
    assert info[0]["capability"] == "8.9"


def test_gpu_available_does_not_terminate(monkeypatch):
    fake_device = {"name": "Fake GPU", "total_memory": 8 * 1024 ** 3, "major": 7, "minor": 5}
    gpu_check = _install_fake_torch(monkeypatch, available=True, devices=[fake_device])

    result = gpu_check.ensure_gpu_available()
    assert len(result) == 1
    assert result[0]["name"] == "Fake GPU"


def test_multiple_gpus_all_reported(monkeypatch):
    devices = [
        {"name": "GPU-0", "total_memory": 8 * 1024 ** 3, "major": 7, "minor": 5},
        {"name": "GPU-1", "total_memory": 16 * 1024 ** 3, "major": 8, "minor": 6},
    ]
    gpu_check = _install_fake_torch(monkeypatch, available=True, devices=devices)

    info = gpu_check.get_gpu_info()
    assert [d["name"] for d in info] == ["GPU-0", "GPU-1"]
    assert [d["index"] for d in info] == [0, 1]
