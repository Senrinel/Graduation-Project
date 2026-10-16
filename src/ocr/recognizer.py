"""
Step 4：文字辨識 (OCR Inference)
==================================
以 EasyOCR 對前處理後的影像進行文字辨識。

硬體調度策略（GPU 優先，CPU 降級相容）：
- 系統初始化時自動偵測硬體運算裝置（`detect_compute_device()`）。
- 優先使用 NVIDIA GPU (CUDA) 加速；若無可用 GPU 則無縫降級相容使用 CPU。
- 不論使用何種運算裝置，皆會於標準輸出顯示詳細硬體資訊與辨識進度。

注意事項：
- EasyOCR 首次執行會下載語言模型（約數百 MB），需網路連線。
- reader 物件初始化成本高，在服務啟動時建立一次並重複使用。
"""

from __future__ import annotations

import easyocr

from config.settings import OCR_CONFIG
from src.ocr.gpu_check import detect_compute_device
from src.schemas import OCRResult, PreprocessedFrame

_reader: "easyocr.Reader | None" = None
_device_checked = False
_use_gpu = False


def get_reader() -> "easyocr.Reader":
    """
    取得（並快取）EasyOCR Reader 單例。

    每個行程在首次呼叫時自動偵測硬體裝置：
    - 優先啟用 GPU 加速（CUDA）。
    - 若無可用 GPU 則自動降級為 CPU 相容運算。
    - 依專案標準於日誌中顯示所採用的運算裝置。
    """
    global _reader, _device_checked, _use_gpu

    if not _device_checked:
        _use_gpu, device_type, _ = detect_compute_device(verbose=True)
        _device_checked = True

    if _reader is None:
        device_name = "GPU (CUDA)" if _use_gpu else "CPU (降級相容模式)"
        print(f"[OCR 引擎] 初始化 EasyOCR Reader（語言: {OCR_CONFIG['languages']}，運算裝置: {device_name}）...")
        _reader = easyocr.Reader(OCR_CONFIG["languages"], gpu=_use_gpu)
        print(f"[OCR 引擎] EasyOCR Reader 初始化完成（運算裝置: {device_name}）。")
    return _reader


def recognize(pframe: PreprocessedFrame) -> list[OCRResult]:
    """
    對單一前處理影格執行 OCR。

    Args:
        pframe: 前處理後之影格。

    Returns:
        list[OCRResult]: 該影格中所有偵測到的文字區塊（可能為 0 筆或多筆）。
    """
    reader = get_reader()
    raw_results = reader.readtext(pframe.roi_image)

    results = []
    for bbox, text, confidence in raw_results:
        if confidence < OCR_CONFIG["min_confidence"]:
            continue
        results.append(OCRResult(
            frame_id=pframe.frame_id,
            timestamp_sec=pframe.timestamp_sec,
            text=text,
            bbox=[list(point) for point in bbox],
            confidence=confidence,
        ))
    return results
