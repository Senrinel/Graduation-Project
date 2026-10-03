"""
Step 4：文字辨識 (OCR Inference)
==================================
以 EasyOCR 對前處理後的影像進行文字辨識。

決策紀錄（2026-07-25，使用者明確要求）：
- 本模組**強制要求使用 GPU**，Reader 初始化前一律先呼叫
  `src.ocr.gpu_check.ensure_gpu_available()`；若偵測不到可用 GPU，
  該函式會直接終止程式，**禁止任何靜默改用 CPU 的 fallback**。
- GPU 資訊需正確讀取並在終端機顯示（裝置名稱、顯示記憶體、CUDA capability），
  而非只是布林值判斷，方便使用者確認實際用的是哪張 GPU。

其他注意事項：
- EasyOCR 首次執行會下載語言模型（約數百 MB），需網路連線。
- reader 物件初始化成本高，應在服務啟動時建立一次並重複使用，
  不應每次呼叫 recognize() 都重新建立。
"""

from __future__ import annotations

import easyocr

from config.settings import OCR_CONFIG
from src.ocr.gpu_check import ensure_gpu_available
from src.schemas import OCRResult, PreprocessedFrame

_reader: "easyocr.Reader | None" = None
_gpu_checked = False


def get_reader() -> "easyocr.Reader":
    """
    取得（並快取）EasyOCR Reader 單例。

    每個行程只會在第一次呼叫時執行一次 GPU 強制檢查
    （`ensure_gpu_available()`）；若無可用 GPU，該檢查會直接終止程式，
    不會執行到下面建立 Reader 的程式碼。
    """
    global _reader, _gpu_checked

    if not _gpu_checked:
        ensure_gpu_available()
        _gpu_checked = True

    if _reader is None:
        # GPU 已在上方確認可用，這裡固定傳入 gpu=True，不提供 CPU 選項。
        _reader = easyocr.Reader(OCR_CONFIG["languages"], gpu=True)
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
