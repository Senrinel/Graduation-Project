"""
GPU 偵測與 CPU 降級相容邏輯測試
===============================
本測試環境使用假 torch 模組模擬各種硬體情境：
1. 無 GPU 環境：`detect_compute_device()` 必須正確識別無 GPU 並自動降級相容為 CPU（不拋出終止例外）。
2. 有單張/多張 GPU 環境：`detect_compute_device()` 與 `get_gpu_info()` 必須正確識別裝置數量與規格。
"""

from __future__ import annotations

import importlib
import sys
import types


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

    import src.ocr.gpu_check as gpu_check
    importlib.reload(gpu_check)
    return gpu_check


def test_no_gpu_returns_empty_info(monkeypatch):
    gpu_check = _install_fake_torch(monkeypatch, available=False)
    assert gpu_check.get_gpu_info() == []


def test_no_gpu_falls_back_to_cpu(monkeypatch):
    gpu_check = _install_fake_torch(monkeypatch, available=False)
    use_gpu, device_type, info = gpu_check.detect_compute_device(verbose=False)
    assert use_gpu is False
    assert device_type == "cpu"
    assert info == []


def test_no_gpu_does_not_terminate_program(monkeypatch):
    gpu_check = _install_fake_torch(monkeypatch, available=False)
    # 確保降級模式下不以 SystemExit 終止程式
    res = gpu_check.ensure_gpu_available()
    assert res == []


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


def test_gpu_available_selects_cuda(monkeypatch):
    fake_device = {"name": "Fake GPU", "total_memory": 8 * 1024 ** 3, "major": 7, "minor": 5}
    gpu_check = _install_fake_torch(monkeypatch, available=True, devices=[fake_device])

    use_gpu, device_type, info = gpu_check.detect_compute_device(verbose=False)
    assert use_gpu is True
    assert device_type == "cuda"
    assert len(info) == 1
    assert info[0]["name"] == "Fake GPU"


def test_multiple_gpus_all_reported(monkeypatch):
    devices = [
        {"name": "GPU-0", "total_memory": 8 * 1024 ** 3, "major": 7, "minor": 5},
        {"name": "GPU-1", "total_memory": 16 * 1024 ** 3, "major": 8, "minor": 6},
    ]
    gpu_check = _install_fake_torch(monkeypatch, available=True, devices=devices)

    info = gpu_check.get_gpu_info()
    assert [d["name"] for d in info] == ["GPU-0", "GPU-1"]
    assert [d["index"] for d in info] == [0, 1]
