"""
Phase 2 執行入口：影像前處理 (Step 3)
======================================
讀取 Phase 1（scripts/run_phase1.py）輸出的影格目錄（frames + manifest.csv），
對每張影格套用 src/preprocessing/pipeline.py 的 preprocess()，輸出：
  1. 前處理後影像（灰階 + CLAHE 對比強化，未二值化）
  2. manifest.csv（沿用 Phase 1 格式：frame_id, timestamp_sec, filename）

本腳本只負責「讀取 Phase 1 產出 -> 呼叫 Step 3 -> 寫出標準化結果」，
不包含任何影像演算法邏輯（邏輯都在 src/preprocessing/pipeline.py），
符合模組化與標準化輸入輸出原則。

去雜訊 (denoise) 比較模式：
實測全畫面去雜訊每影格約 447ms、關閉約 4ms（差約 100 倍）。使用者決議
（2026-07-25）：專案測試期間兩種都做，待 Step 4 OCR 接上後比對辨識率，
若去雜訊帶來的辨識率提升低於 15%，之後就預設關閉。
因此本腳本預設 --denoise both：分別輸出 processed_denoise_on/ 與
processed_denoise_off/ 兩份結果 + 各自耗時，供之後 Phase 4 比較用。

用法：
    python scripts/run_phase2.py --frames-dir data/output/001/frames
    python scripts/run_phase2.py --frames-dir data/output/001/frames --denoise on
    python scripts/run_phase2.py --frames-dir data/output/001/frames --roi-override 001
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from config.settings import ROI_OVERRIDES
from src.preprocessing.pipeline import preprocess
from src.schemas import Frame


def _process_one_pass(frames_dir: Path, out_dir: Path, roi: dict | None, denoise: bool) -> tuple[Path, float]:
    """對一整批影格執行單一種去雜訊設定的前處理，回傳 manifest 路徑與總耗時（秒）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_in = frames_dir / "manifest.csv"

    manifest_rows = []
    t0 = time.time()
    with open(manifest_in, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image = cv2.imread(str(frames_dir / row["filename"]))
            if image is None:
                print(f"[警告] 無法讀取影格: {row['filename']}，已略過")
                continue

            frame = Frame(
                frame_id=int(row["frame_id"]),
                timestamp_sec=float(row["timestamp_sec"]),
                image=image,
            )
            pframe = preprocess(frame, roi=roi, denoise=denoise)

            filename = f"processed_{pframe.frame_id:06d}.jpg"
            cv2.imwrite(str(out_dir / filename), pframe.roi_image)
            manifest_rows.append({
                "frame_id": pframe.frame_id,
                "timestamp_sec": round(pframe.timestamp_sec, 3),
                "filename": filename,
            })
    elapsed = time.time() - t0

    manifest_out = out_dir / "manifest.csv"
    with open(manifest_out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_id", "timestamp_sec", "filename"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    return manifest_out, elapsed


def run(frames_dir: str, out_dir: str, roi_override_key: str | None, denoise_mode: str) -> list[Path]:
    """
    執行 Step 3：讀取 Phase 1 影格 + manifest，套用前處理後輸出。

    Args:
        frames_dir: Phase 1 輸出目錄（內含影格圖片與 manifest.csv）。
        out_dir: 輸出根目錄。
        roi_override_key: 若指定，會從 config.ROI_OVERRIDES 查找對應之
            手動裁切設定；預設為 None（不裁切，全畫面前處理）。
        denoise_mode: "both"（預設，測試期間兩種都輸出）、"on"、"off"。

    Returns:
        產生的 manifest.csv 路徑列表。
    """
    in_path = Path(frames_dir)
    manifest_in = in_path / "manifest.csv"
    if not manifest_in.exists():
        raise FileNotFoundError(f"找不到 Phase 1 manifest: {manifest_in}")

    roi = ROI_OVERRIDES.get(roi_override_key) if roi_override_key else None
    if roi_override_key and roi is None:
        print(f"[警告] config.ROI_OVERRIDES 中找不到 key='{roi_override_key}'，將以全畫面處理")

    out_root = Path(out_dir)
    print(f"[Step 3] 讀取 Phase 1 影格: {in_path}")
    print(f"         ROI 設定: {'全畫面（不裁切）' if roi is None else roi}")

    passes = {"both": [True, False], "on": [True], "off": [False]}[denoise_mode]

    results = []
    for denoise in passes:
        tag = "denoise_on" if denoise else "denoise_off"
        manifest_out, elapsed = _process_one_pass(in_path, out_root / tag, roi, denoise)
        n = sum(1 for _ in open(manifest_out, encoding="utf-8-sig")) - 1
        print(f"[{tag}] 共處理 {n} 張影格，耗時 {elapsed:.2f}s（{elapsed / max(n, 1) * 1000:.1f} ms/影格）"
              f" -> {manifest_out}")
        results.append(manifest_out)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2：影像前處理 (Step 3)")
    parser.add_argument("--frames-dir", required=True, help="Phase 1 輸出的影格目錄")
    parser.add_argument("--out-dir", default=None, help="輸出根目錄，預設 <frames-dir>/../processed")
    parser.add_argument("--roi-override", default=None,
                         help="config.ROI_OVERRIDES 中的 key（預設不使用，全畫面處理）")
    parser.add_argument("--denoise", choices=["both", "on", "off"], default="both",
                         help="去雜訊模式，測試期間預設 both（同時輸出兩種供比較）")
    args = parser.parse_args()

    out_dir = args.out_dir or str(Path(args.frames_dir).parent / "processed")
    run(args.frames_dir, out_dir, args.roi_override, args.denoise)


if __name__ == "__main__":
    main()
