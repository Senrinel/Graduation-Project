"""
Step 8a：CSV 匯出
===================
將 ExportRecord 列表寫出為標準 CSV 檔案。
欄位固定為：原文、中文、詞性、例句、備註（對應規格書 3. 資料持久化格式）。
"""

from __future__ import annotations
from pathlib import Path
from typing import List
import pandas as pd

from src.schemas import ExportRecord

# 與 ExportRecord 欄位順序一致。刻意固定寫在這裡（而非只靠
# `pd.DataFrame([r.model_dump() for r in records])` 動態推斷），是因為
# 2026-07-27 真實使用時發現：當 `records` 是空列表（例如影片因編碼格式不
# 支援導致 OCR 完全沒有辨識出任何文字，見 PROJECT_NOTES.md 第 17 節），
# `pd.DataFrame([])` 會產生「連欄位名稱都沒有」的 DataFrame，寫出來的 CSV
# 檔案內容形同空白，之後 `results_reader.py` 用 `pd.read_csv()` 讀取時會
# 直接丟出 `pandas.errors.EmptyDataError`，變成 API 的 500 錯誤——即使這支
# 影片本身沒有真正的程式錯誤，只是單純沒有任何字幕內容。固定欄位名稱可
# 確保「有效但是 0 筆資料」與「檔案本身壞掉/不存在」是兩種明確不同、且
# 都能被正常處理的情況。
EXPORT_COLUMNS = ["原文", "中文", "詞性", "例句", "備註"]


def export_csv(records: List[ExportRecord], output_path: str | Path) -> Path:
    """
    將匯出紀錄寫入 CSV 檔案（UTF-8 with BOM，確保 Excel 開啟不亂碼）。

    Args:
        records: 待匯出的紀錄列表（可以是空列表——例如整支影片沒有辨識出
            任何文字時——仍會寫出一個「只有標題列、0 筆資料」的合法 CSV，
            而不是完全空白的檔案，見上方模組層級註解）。
        output_path: 輸出檔案路徑。

    Returns:
        實際寫入的檔案路徑。
    """
    output_path = Path(output_path)
    if records:
        df = pd.DataFrame([r.model_dump() for r in records])
    else:
        df = pd.DataFrame(columns=EXPORT_COLUMNS)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path
