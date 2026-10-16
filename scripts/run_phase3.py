"""
Phase 3 執行入口：文字辨識 (Step 4 OCR)
==========================================
讀取 Phase 2（scripts/run_phase2.py）輸出的前處理影像目錄
（processed/denoise_on 或 processed/denoise_off + manifest.csv），
以 EasyOCR 執行文字辨識，輸出標準化 OCRResult 清單（CSV）。

運算調度策略（GPU 優先，CPU 降級相容）：
- 執行前呼叫 `detect_compute_device()` 偵測可用硬體。
- 優先使用 NVIDIA GPU (CUDA)；若無可用 GPU 則無縫降級相容使用 CPU。
- 控制台即時輸出硬體裝置選用狀態。

用法：
    python scripts/run_phase3.py --processed-dir data/output/001/processed/denoise_off
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 先偵測硬體環境並輸出日誌，再匯入後續重依賴模組。
from src.ocr.gpu_check import detect_compute_device  # noqa: E402


def run(processed_dir: str, out_dir: str) -> Path:
    """
    執行 Step 4：對 Phase 2 輸出的前處理影像逐一執行 OCR。

    Args:
        processed_dir: Phase 2 輸出目錄（內含前處理影像與 manifest.csv）。
        out_dir: 輸出目錄（OCR 結果 CSV 存放位置）。

    Returns:
        ocr_results.csv 的路徑。
    """
    import cv2

    from src.ocr.recognizer import get_reader, recognize
    from src.schemas import PreprocessedFrame

    in_path = Path(processed_dir)
    manifest_in = in_path / "manifest.csv"
    if not manifest_in.exists():
        raise FileNotFoundError(f"找不到 Phase 2 manifest: {manifest_in}")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[Step 4] 讀取 Phase 2 前處理影像: {in_path}")

    # 將「Reader 初始化（含模型載入／下載）」與「逐影格辨識」分開計時，
    # 避免第一次執行下載模型的時間被誤算進每影格辨識耗時，
    # 但仍會在最後加總成「完整耗時」（貼近使用者實際感受到的等待時間）。
    t_init_start = time.time()
    get_reader()
    t_init = time.time() - t_init_start

    all_rows = []
    t_loop_start = time.time()
    n_frames = 0
    with open(manifest_in, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    total_frames = len(rows)

    for idx, row in enumerate(rows, 1):
        image = cv2.imread(str(in_path / row["filename"]), cv2.IMREAD_UNCHANGED)
        if image is None:
            print(f"[警告] 無法讀取影像: {row['filename']}，已略過", flush=True)
            continue

        pframe = PreprocessedFrame(
            frame_id=int(row["frame_id"]),
            timestamp_sec=float(row["timestamp_sec"]),
            roi_image=image,
        )
        print(
            f"[Step 4 進度] EasyOCR 辨識中: 影格 {idx}/{total_frames} (時間戳: {pframe.timestamp_sec:.1f}s)...",
            flush=True,
        )
        results = recognize(pframe)
        for r in results:
            all_rows.append(r.model_dump())
        n_frames += 1
    t_loop = time.time() - t_loop_start
    t_total = t_init + t_loop

    manifest_out = out_path / "ocr_results.csv"
    fieldnames = ["frame_id", "timestamp_sec", "text", "bbox", "confidence"]
    with open(manifest_out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"[完成] 共辨識出 {len(all_rows)} 筆文字（{n_frames} 張影格）")
    print(f"       Reader 初始化耗時: {t_init:.2f}s（含模型載入／下載，僅第一次執行較久）")
    print(f"       逐影格辨識耗時: {t_loop:.2f}s（{t_loop / max(n_frames, 1) * 1000:.1f} ms/影格）")
    print(f"       Step 4 總耗時: {t_total:.2f}s")
    print(f"       輸出 -> {manifest_out}")
    return manifest_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3：文字辨識 (Step 4 OCR，優先使用 GPU，無則降級 CPU)")
    parser.add_argument("--processed-dir", required=True, help="Phase 2 輸出的前處理影像目錄")
    parser.add_argument("--out-dir", default=None, help="輸出目錄，預設 <processed-dir>/../ocr")
    args = parser.parse_args()

    # 硬體偵測（優先 GPU，無則降級 CPU，皆輸出標準日誌）
    detect_compute_device(verbose=True)

    out_dir = args.out_dir or str(Path(args.processed_dir).parent.parent / "ocr")
    run(args.processed_dir, out_dir)


if __name__ == "__main__":
    main()
