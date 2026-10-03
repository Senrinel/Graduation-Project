"""
測試 src/export/csv_exporter.py。

2026-07-27 真實使用時發現的問題（見 PROJECT_NOTES.md 第 17 節）：使用者
上傳一支 AV1 編碼的影片，cv2/ffmpeg 無法解碼，Phase 1 擷取到 0 張影格，
整條流程一路產生 0 筆結果，`export_csv([], ...)` 寫出的 CSV 完全沒有欄位
名稱，導致 `results_reader.py` 用 `pd.read_csv()` 讀取時丟出
`pandas.errors.EmptyDataError`，變成 API 的 500 錯誤。這裡驗證修好之後，
即使是 0 筆資料也能寫出「有標題列、可以被 pandas 正常讀回」的合法 CSV。
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.export.csv_exporter import EXPORT_COLUMNS, export_csv  # noqa: E402
from src.schemas import ExportRecord  # noqa: E402


def test_export_csv_with_records_round_trips(tmp_path):
    records = [
        ExportRecord(原文="집", 中文="家", 詞性="명사", 例句="집에 가다", 備註="note1"),
        ExportRecord(原文="학교", 中文="学校", 詞性="명사", 例句="", 備註=""),
    ]
    out_path = export_csv(records, tmp_path / "export.csv")

    df = pd.read_csv(out_path, encoding="utf-8-sig")
    assert list(df.columns) == EXPORT_COLUMNS
    assert len(df) == 2
    assert df.iloc[0]["原文"] == "집"


def test_export_csv_with_zero_records_still_has_header_and_is_readable(tmp_path):
    """核心修復驗證：0 筆資料時，寫出的 CSV 仍必須是 pandas 可以正常讀回的合法檔案。"""
    out_path = export_csv([], tmp_path / "empty_export.csv")

    # 修復前：pd.read_csv() 在這裡會丟出 pandas.errors.EmptyDataError
    df = pd.read_csv(out_path, encoding="utf-8-sig")
    assert list(df.columns) == EXPORT_COLUMNS
    assert len(df) == 0


def test_export_csv_zero_records_file_content_has_header_line(tmp_path):
    out_path = export_csv([], tmp_path / "empty_export.csv")
    content = out_path.read_text(encoding="utf-8-sig").strip()
    assert content == ",".join(EXPORT_COLUMNS)
