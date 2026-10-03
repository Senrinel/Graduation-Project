"""
Step 3（影像前處理）單元測試
==============================
驗證兩項使用者確認之設計決策：
1. 預設不裁切，全畫面前處理（輸出影像尺寸應與輸入相同，除非指定 roi）。
2. 輸出為灰階＋對比強化，不做非黑即白的二值化（輸出應保留多階灰階，
   而非僅有 0/255 兩種數值）。
"""

from __future__ import annotations

import numpy as np

from src.preprocessing.pipeline import preprocess
from src.schemas import Frame


def _make_gradient_frame(width: int = 200, height: int = 100) -> Frame:
    """建立一張有灰階漸層的合成影格（避免全單一數值，才能驗證未被二值化）。"""
    gradient = np.tile(np.linspace(0, 255, width, dtype=np.uint8), (height, 1))
    image = np.stack([gradient] * 3, axis=-1)  # 轉為 3 channel BGR
    return Frame(frame_id=0, timestamp_sec=0.0, image=image)


def test_default_no_crop_full_frame():
    frame = _make_gradient_frame(width=200, height=100)
    pframe = preprocess(frame)

    # 預設不裁切：輸出尺寸應與輸入畫面相同（灰階後少了 channel 維度）
    assert pframe.roi_image.shape == (100, 200)


def test_output_is_not_hard_binarized():
    frame = _make_gradient_frame(width=200, height=100)
    pframe = preprocess(frame)

    unique_values = np.unique(pframe.roi_image)
    # 若被二值化，輸出只會有 0 和 255 兩種值；灰階強化後應保留多階灰階
    assert len(unique_values) > 2


def test_roi_override_crops_by_fraction():
    frame = _make_gradient_frame(width=200, height=100)
    roi = {"x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0}  # 左半邊
    pframe = preprocess(frame, roi=roi)

    assert pframe.roi_image.shape == (100, 100)


def test_frame_id_and_timestamp_preserved():
    frame = Frame(frame_id=7, timestamp_sec=12.34, image=np.zeros((50, 50, 3), dtype=np.uint8))
    pframe = preprocess(frame)

    assert pframe.frame_id == 7
    assert pframe.timestamp_sec == 12.34
