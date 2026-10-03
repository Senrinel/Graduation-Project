"""
Phase 1 執行入口：本地影片匯入與影格採樣 (Step 1-2)
======================================================
串接 src/video_io/loader.py（Step 1）與 src/frame_sampler/sampler.py（Step 2），
將指定影片依採樣率擷取影格，寫出：
  1. 影格圖片（供人工檢視 / 後續 Step 3 前處理開發用）
  2. manifest.csv（標準化清單：frame_id, timestamp_sec, filename）

本腳本只負責「輸入輸出串接」，不包含任何影像處理或 OCR 邏輯，
符合模組化原則——之後 Step 3 以後的模組皆可直接讀取本腳本產出的影格與 manifest。

用法：
    python scripts/run_phase1.py --video raw/001.mkv --sample-rate 1.0
    python scripts/run_phase1.py --video raw/001.mkv --out-dir data/output/001 --max-frames 20
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from config.settings import SAMPLING
from src.frame_sampler.sampler import sample_frames
from src.video_io.loader import load_video


def run(video_path: str, out_dir: str, sample_rate: float, max_frames: int | None) -> Path:
    """
    執行 Step 1-2：載入影片並依採樣率輸出影格 + manifest。

    Args:
        video_path: 本地影片檔案路徑。
        out_dir: 輸出目錄（影格圖片與 manifest.csv 存放位置）。
        sample_rate: 採樣率（FPS）。
        max_frames: 最多輸出影格數（None 表示不限制，處理整支影片）。

    Returns:
        manifest.csv 的路徑。
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    t_start = time.time()

    cap, meta = load_video(video_path)
    print(f"[Step 1] 載入影片: {video_path}")
    print(f"         fps={meta.fps:.3f}  frame_count={meta.frame_count}  "
          f"resolution={meta.width}x{meta.height}  duration={meta.duration_sec:.1f}s")

    manifest_rows = []
    count = 0
    print(f"[Step 2] 依採樣率 {sample_rate} FPS 擷取影格...")
    for frame in sample_frames(cap, meta.fps, sample_rate=sample_rate):
        filename = f"frame_{frame.frame_id:06d}.jpg"
        cv2.imwrite(str(out_path / filename), frame.image)
        manifest_rows.append({
            "frame_id": frame.frame_id,
            "timestamp_sec": round(frame.timestamp_sec, 3),
            "filename": filename,
        })
        count += 1
        if max_frames is not None and count >= max_frames:
            break

    cap.release()

    manifest_path = out_path / "manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_id", "timestamp_sec", "filename"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    elapsed = time.time() - t_start
    print(f"[完成] 共輸出 {count} 張影格，耗時 {elapsed:.2f}s（{elapsed / max(count, 1) * 1000:.1f} ms/影格）"
          f"，manifest -> {manifest_path}")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1：本地影片匯入與影格採樣")
    parser.add_argument("--video", required=True, help="影片檔案路徑")
    parser.add_argument("--out-dir", default=None, help="輸出目錄，預設 data/output/<影片檔名>/frames")
    parser.add_argument("--sample-rate", type=float, default=SAMPLING["rate_fps"], help="採樣率 (FPS)")
    parser.add_argument("--max-frames", type=int, default=None, help="最多輸出影格數（測試用，預設不限制）")
    args = parser.parse_args()

    video_stem = Path(args.video).stem
    out_dir = args.out_dir or f"data/output/{video_stem}/frames"

    run(args.video, out_dir, args.sample_rate, args.max_frames)


if __name__ == "__main__":
    main()
