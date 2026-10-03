"""
Step 2：影格採樣 (Frame Sampling)
==================================
依指定採樣率（預設 1 FPS）自 VideoCapture 擷取影格，輸出標準化 Frame 物件序列。
"""

from __future__ import annotations
from typing import Iterator
import cv2

from src.schemas import Frame


def sample_frames(cap: cv2.VideoCapture, source_fps: float, sample_rate: float = 1.0) -> Iterator[Frame]:
    """
    以固定間隔自影片擷取影格。

    Args:
        cap: 已開啟的 VideoCapture 物件（見 video_io.loader.load_video）。
        source_fps: 原始影片 fps（由 VideoMeta 提供）。
        sample_rate: 目標採樣率，單位 FPS，預設 1（每秒 1 幀）。

    Yields:
        Frame: 標準化影格物件，依序遞增 frame_id。
    """
    if source_fps <= 0:
        raise ValueError("source_fps 必須為正數")

    step = max(int(round(source_fps / sample_rate)), 1)
    frame_id = 0
    src_index = 0

    while True:
        ok, image = cap.read()
        if not ok:
            break
        if src_index % step == 0:
            timestamp_sec = src_index / source_fps
            yield Frame(frame_id=frame_id, timestamp_sec=timestamp_sec, image=image)
            frame_id += 1
        src_index += 1
