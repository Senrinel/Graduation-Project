"""
Step 1：視訊源載入 (Video Source Loading)
==========================================
負責將本地影片檔案讀取為 OpenCV VideoCapture 物件。
輸入：影片檔案路徑
輸出：VideoCapture 物件 + 基本 metadata（fps, 總影格數, 解析度, 時長）

未來擴充：YouTube 網址解析（下載後轉為本地檔案，走相同介面，
上層呼叫端不受影響）。
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2


@dataclass
class VideoMeta:
    fps: float
    frame_count: int
    width: int
    height: int
    duration_sec: float


def load_video(path: str | Path) -> tuple[cv2.VideoCapture, VideoMeta]:
    """
    載入本地影片檔案。

    Args:
        path: 影片檔案路徑。

    Returns:
        (VideoCapture 物件, VideoMeta 影片基本資訊)

    Raises:
        FileNotFoundError: 檔案不存在。
        IOError: OpenCV 無法開啟該檔案（格式不支援或損毀）。
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"影片檔案不存在: {path}")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise IOError(f"無法開啟影片檔案: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_sec = frame_count / fps if fps else 0.0

    meta = VideoMeta(fps=fps, frame_count=frame_count, width=width, height=height, duration_sec=duration_sec)
    return cap, meta
