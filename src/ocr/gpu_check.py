"""
硬體運算裝置偵測與相容性管理 (Hardware Compute Device Detection & Management)
=============================================================================
運算策略：
1. 優先偵測並使用 NVIDIA GPU (CUDA) 加速 OCR 深度學習推論。
2. 若系統無可用 GPU（或環境無 CUDA/torch），自動無縫降級相容使用 CPU 運算。
3. 不論採用 GPU 或是 CPU 運算，均遵循專案標準於控制台輸出清楚明確之規格日誌。
"""

from __future__ import annotations

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    _TORCH_AVAILABLE = False


def get_gpu_info() -> list[dict]:
    """
    讀取目前系統可用的 GPU 資訊。

    Returns:
        list[dict]: 每個 GPU 一筆，欄位為 index / name / total_memory_gb / capability。
                    若無可用 GPU 或無 torch，回傳空列表。
    """
    if not _TORCH_AVAILABLE or not torch.cuda.is_available():
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


def check_nvidia_hardware() -> tuple[bool, str]:
    """
    檢查作業系統中是否實體存在 NVIDIA 顯示卡硬體（透過 nvidia-smi 查詢）。
    """
    import shutil
    import subprocess

    cmd = shutil.which("nvidia-smi")
    if not cmd:
        return False, "未偵測到 nvidia-smi 工具"
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return True, proc.stdout.strip().replace("\r", "").split("\n")[0]
    except Exception as e:
        return False, str(e)
    return False, "nvidia-smi 查無可用 GPU 裝置"


def detect_compute_device(verbose: bool = True) -> tuple[bool, str, list[dict]]:
    """
    偵測可用的硬體運算裝置。

    優先檢查 GPU 是否可用；若不可用則自動降級為 CPU。
    若系統實體具備 NVIDIA GPU 但 PyTorch 缺少 CUDA 支援，主動輸出修復指引。

    Args:
        verbose: 是否於標準輸出印出詳細硬體資訊。

    Returns:
        tuple[bool, str, list[dict]]:
            - use_gpu (bool): 是否啟用 GPU
            - device_type (str): "cuda" 或 "cpu"
            - gpu_info (list[dict]): 偵測到的 GPU 清單（若為 CPU 則為空列表）
    """
    gpu_info = get_gpu_info()
    use_gpu = len(gpu_info) > 0

    if use_gpu:
        device_type = "cuda"
        if verbose:
            print("=" * 60)
            print(f"[硬體運算裝置] 偵測到 {len(gpu_info)} 張可用 GPU，優先啟用 GPU 加速運算：")
            for info in gpu_info:
                print(
                    f"  - GPU {info['index']}: {info['name']}，"
                    f"顯示記憶體 {info['total_memory_gb']} GB，CUDA capability {info['capability']}"
                )
            print("=" * 60)
    else:
        device_type = "cpu"
        has_hw, hw_name = check_nvidia_hardware()
        if verbose:
            print("=" * 60)
            if has_hw:
                print(f"[硬體運算警示] 偵測到本機具有實體 NVIDIA 顯示卡 ({hw_name})！")
                print("但目前環境中的 PyTorch 為 CPU 版本（缺少 CUDA 支援），無法發揮 GPU 效能。")
                print("修復建議：可執行 .\\deploy.ps1 進行自動修復，或手動執行：")
                print("pip install --force-reinstall --no-deps torch torchvision --index-url https://download.pytorch.org/whl/cu126")
            else:
                print("[硬體運算裝置] 未偵測到可用 GPU（torch.cuda.is_available() == False）。")
                print("系統自動降級相容：改用 CPU 進行運算（注意：逐影格 OCR 辨識耗時可能較長）。")
            print("=" * 60)

    return use_gpu, device_type, gpu_info


def ensure_gpu_available() -> list[dict]:
    """
    向後相容函式：偵測硬體裝置並輸出日誌，回傳 GPU 資訊列表。
    （改為降級相容機制，無 GPU 時降級 CPU 運算而不強制終止程式）
    """
    _, _, gpu_info = detect_compute_device(verbose=True)
    return gpu_info
