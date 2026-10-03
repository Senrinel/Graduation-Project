"""
OCR 結果 CSV 讀寫工具
========================
Phase 5 三通道共用：讀取 Phase 3（`scripts/run_phase3.py`）輸出的
`ocr_results.csv`，還原成標準化的 `OCRResult` 列表。抽成獨立模組，
避免 Channel 1/2/3 的 runner 各自重複實作同一段 CSV 解析邏輯。
"""

from __future__ import annotations

import ast
import csv
from typing import List

from src.schemas import OCRResult


def load_ocr_results(csv_path: str) -> List[OCRResult]:
    """
    讀取 `ocr_results.csv`，依 timestamp_sec 遞增排序回傳。

    Args:
        csv_path: `run_phase3.py` 輸出的 CSV 路徑（欄位：frame_id,
            timestamp_sec, text, bbox, confidence）。

    Returns:
        依時間排序的 `OCRResult` 列表。
    """
    results = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(OCRResult(
                frame_id=int(row["frame_id"]),
                timestamp_sec=float(row["timestamp_sec"]),
                text=row["text"],
                bbox=ast.literal_eval(row["bbox"]),
                confidence=float(row["confidence"]),
            ))
    results.sort(key=lambda r: r.timestamp_sec)
    return results
