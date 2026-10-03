"""
Phase 1 (Step 1-2) 整合測試
=============================
使用合成影片（非真實素材）驗證 video_io.load_video + frame_sampler.sample_frames
的串接是否正確，確保測試可離線、可重現執行，不依賴 raw/ 底下的真實測試影片。
"""

from __future__ import annotations

import cv2
import numpy as np

from src.frame_sampler.sampler import sample_frames
from src.video_io.loader import load_video


def _make_synthetic_video(path: str, num_frames: int = 30, fps: float = 10.0) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (200, 100))
    for i in range(num_frames):
        img = np.full((100, 200, 3), (i * 5) % 255, dtype=np.uint8)
        writer.write(img)
    writer.release()


def test_load_video_metadata(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    _make_synthetic_video(str(video_path))

    cap, meta = load_video(video_path)
    assert meta.fps == 10.0
    assert meta.frame_count == 30
    assert meta.width == 200
    assert meta.height == 100
    cap.release()


def test_sample_frames_rate(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    _make_synthetic_video(str(video_path), num_frames=30, fps=10.0)

    cap, meta = load_video(video_path)
    frames = list(sample_frames(cap, meta.fps, sample_rate=2.0))
    cap.release()

    # 3 秒影片，每秒採樣 2 張 -> 預期約 6 張
    assert len(frames) == 6
    assert frames[0].frame_id == 0
    assert frames[-1].frame_id == len(frames) - 1
    # 時間戳應遞增
    timestamps = [f.timestamp_sec for f in frames]
    assert timestamps == sorted(timestamps)
