"""
[臨時測試工具，非 Phase 5 正式交付模組]
Phase 0-5 全流程驗收腳本
================================================
對 `raw/` 目錄底下所有影片，依序執行：

    Phase 1（影片匯入/影格採樣）-> Phase 2（前處理）-> Phase 3（OCR，需 GPU）
    -> Channel 1（Okt/Komoran/Kkma/Mecab-ko 四個子通道）
    -> Channel 2（本地 LLM）-> Channel 3（混合 fallback）

並將每支影片、每個階段的成功/失敗、耗時、錯誤訊息彙整成一份總表
（預設 `data/output/_pipeline_smoke_test_summary.csv`），做為「Phase 0-5
是否都能正常運作」的驗收依據。

**重要限制**：
- Phase 3（OCR）與其後的所有步驟都需要真正的 GPU（`torch.cuda` 可用）。
  沙盒環境沒有安裝 torch/GPU，執行到這裡會被 `src/ocr/gpu_check.py`
  的強制檢查擋下（這是設計行為，不是 bug）；本腳本會針對每個階段
  各自捕捉例外，即使某階段失敗，仍會完整記錄並繼續處理下一支影片，
  最後產出完整報告，而不是讓整個程式崩潰、什麼結果都拿不到。
- Channel 2/3 需要本機已啟動的 Ollama（`qwen2.5:7b`），未啟動時該階段
  會記錄連線失敗，不影響其他階段的驗證結果。
- 本腳本刻意只跑 `denoise_on` 一種前處理版本（denoise 開關的最終決定
  留到專案尾聲，見 PROJECT_NOTES.md 第 12 節），避免驗收時间加倍。

用法（建議在已具備 GPU + Ollama 的本機環境執行，才能拿到 Phase 3-5 的
完整結果）：
    python scripts/_pipeline_smoke_test.py
    python scripts/_pipeline_smoke_test.py --limit 2              # 先測試前 2 支影片
    python scripts/_pipeline_smoke_test.py --max-frames 20        # 每支影片只取 20 張影格（快速驗證用）
    python scripts/_pipeline_smoke_test.py --skip-channel2 --skip-channel3   # 只測 Channel 1
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _run_stage(stage_name: str, fn: Callable, *args, **kwargs) -> dict:
    """執行單一階段，捕捉所有例外（含 GPU 檢查用的 SystemExit），回傳結果紀錄。"""
    t0 = time.time()
    try:
        fn(*args, **kwargs)
        return {"stage": stage_name, "ok": True, "elapsed_sec": round(time.time() - t0, 2), "error": ""}
    except SystemExit as e:
        return {
            "stage": stage_name, "ok": False, "elapsed_sec": round(time.time() - t0, 2),
            "error": f"SystemExit(code={e.code})：通常代表 GPU 檢查未通過",
        }
    except Exception as e:  # noqa: BLE001 - 驗收腳本刻意捕捉所有例外，逐階段記錄不中斷整體流程
        return {
            "stage": stage_name, "ok": False, "elapsed_sec": round(time.time() - t0, 2),
            "error": f"{type(e).__name__}: {e}",
        }


def _check_gpu_available() -> tuple[bool, str]:
    """檢查 GPU 是否可用，不會像 ensure_gpu_available() 一樣直接終止程式。"""
    try:
        from src.ocr.gpu_check import get_gpu_info
        return (bool(get_gpu_info()), "")
    except ImportError as e:
        return False, f"ImportError: {e}（torch 未安裝，沙盒無 GPU 環境的預期情況）"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def process_video(
    video_path: Path,
    max_frames: Optional[int],
    run_channel2: bool,
    run_channel3: bool,
    dict_db: Optional[str],
) -> list[dict]:
    video_id = video_path.stem
    rows: list[dict] = []

    def record(stage_result: dict) -> dict:
        row = {"video_id": video_id, **stage_result}
        rows.append(row)
        return row

    # ---- Phase 1：影片匯入 / 影格採樣 ----
    from scripts.run_phase1 import run as run_phase1
    r = record(_run_stage(
        "phase1", run_phase1, str(video_path), f"data/output/{video_id}/frames", 1.0, max_frames,
    ))
    if not r["ok"]:
        return rows

    # ---- Phase 2：前處理（只跑 denoise_on，見模組 docstring 說明）----
    from scripts.run_phase2 import run as run_phase2
    r = record(_run_stage(
        "phase2", run_phase2, f"data/output/{video_id}/frames",
        f"data/output/{video_id}/processed", None, "on",
    ))
    if not r["ok"]:
        return rows

    # ---- Phase 3：OCR（需要 GPU）----
    gpu_available, gpu_error = _check_gpu_available()
    if not gpu_available:
        record({"stage": "phase3_onward", "ok": False, "elapsed_sec": 0.0,
                "error": f"無可用 GPU，Phase 3 (OCR) 及後續 Channel 1/2/3 無法在此環境驗證。{gpu_error}"})
        return rows

    from scripts.run_phase3 import run as run_phase3
    r = record(_run_stage(
        "phase3", run_phase3, f"data/output/{video_id}/processed/denoise_on",
        f"data/output/{video_id}/ocr_on",
    ))
    if not r["ok"]:
        return rows

    ocr_csv = f"data/output/{video_id}/ocr_on/ocr_results.csv"

    # ---- Channel 1：四個子通道 ----
    from scripts.run_channel1 import run as run_channel1
    for engine in ["okt", "komoran", "kkma", "mecab"]:
        record(_run_stage(
            f"channel1_{engine}", run_channel1, video_id, engine, ocr_csv,
            f"data/output/{video_id}/channel1_{engine}", dict_db,
        ))

    # ---- Channel 2：本地 LLM ----
    if run_channel2:
        from scripts.run_channel2 import run as run_channel2_fn
        record(_run_stage(
            "channel2", run_channel2_fn, video_id, ocr_csv,
            f"data/output/{video_id}/channel2", "qwen2.5:7b", "http://localhost:11434",
        ))

    # ---- Channel 3：混合通道 ----
    if run_channel3:
        from scripts.run_channel3 import run as run_channel3_fn
        record(_run_stage(
            "channel3", run_channel3_fn, video_id, ocr_csv, f"data/output/{video_id}/channel3", dict_db,
        ))

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="[臨時] Phase 0-5 全流程驗收腳本")
    parser.add_argument("--raw-dir", default="raw", help="原始影片目錄")
    parser.add_argument("--limit", type=int, default=None, help="只處理前 N 支影片（測試用）")
    parser.add_argument("--max-frames", type=int, default=None, help="每支影片最多擷取影格數（測試用，預設不限制）")
    parser.add_argument("--skip-channel2", action="store_true", help="跳過 Channel 2（需要本機 Ollama）")
    parser.add_argument("--skip-channel3", action="store_true", help="跳過 Channel 3（需要本機 Ollama）")
    parser.add_argument("--dict-db", default=None, help="字典索引檔路徑，預設讀取 config/settings.py 設定")
    parser.add_argument("--summary-out", default="data/output/_pipeline_smoke_test_summary.csv")
    args = parser.parse_args()

    videos = sorted(Path(args.raw_dir).glob("*.mkv"))
    if args.limit:
        videos = videos[: args.limit]

    if not videos:
        print(f"[錯誤] 在 {args.raw_dir} 找不到任何 .mkv 影片")
        sys.exit(1)

    print(f"共 {len(videos)} 支影片待測試：{[v.name for v in videos]}")

    all_rows: list[dict] = []
    for video_path in videos:
        print(f"\n{'=' * 60}\n處理影片：{video_path.name}\n{'=' * 60}")
        rows = process_video(
            video_path,
            max_frames=args.max_frames,
            run_channel2=not args.skip_channel2,
            run_channel3=not args.skip_channel3,
            dict_db=args.dict_db,
        )
        all_rows.extend(rows)
        for r in rows:
            status = "OK" if r["ok"] else "FAIL"
            suffix = f" - {r['error']}" if not r["ok"] else ""
            print(f"  [{status}] {r['stage']}（{r['elapsed_sec']:.1f}s）{suffix}")

    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "stage", "ok", "elapsed_sec", "error"])
        writer.writeheader()
        writer.writerows(all_rows)

    total = len(all_rows)
    failed = [r for r in all_rows if not r["ok"]]
    print(f"\n{'=' * 60}")
    print(f"總結：共 {total} 個階段紀錄，{len(failed)} 個失敗")
    print(f"詳細結果 -> {summary_path}")
    if failed:
        print("失敗階段一覽：")
        for r in failed:
            print(f"  - {r['video_id']} / {r['stage']}：{r['error']}")


if __name__ == "__main__":
    main()
