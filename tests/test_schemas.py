"""Schemas 模組的基本驗證測試，作為環境建置後的 smoke test。"""

import numpy as np
from src.schemas import ExportRecord, Frame


def test_frame_schema():
    frame = Frame(frame_id=0, timestamp_sec=0.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    assert frame.frame_id == 0


def test_export_record_schema():
    record = ExportRecord(原文="오늘", 中文="今天", 詞性="名詞")
    assert record.備註 == ""
