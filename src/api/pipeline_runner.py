"""
Phase 6：背景工作管線（Upload -> Phase 1-3 -> Channel 1/2/3）
================================================================
使用者決策紀錄（2026-07-26）：`POST /api/upload` 要「真正支援任意影片上傳，
並觸發後續完整流程」，而不只是包裝既有的 10 支測試影片。本模組即是該
「完整流程」在 API 情境下的背景執行版本。

刻意不重用已經過時的 `src/pipeline.py`（其呼叫的 `src/nlp/analyzer.py` /
`translator.py` / `segmenter.py` 三個 Step 6 舊介面仍是刻意留白的
`NotImplementedError` stub，Phase 5 已改用三通道架構取代，`pipeline.py`
本身從未更新，屬於死碼，見 PROJECT_NOTES.md 第 15 節），而是仿照
`scripts/_pipeline_smoke_test.py` 已驗證過的串接順序與例外處理方式
（`SystemExit` 代表 GPU 檢查未通過、其餘例外個別捕捉、單一階段失敗不
中斷其餘獨立階段），差異在於：
  - 執行結果寫入 `JobStore`（SQLite）而非彙整 CSV，供 API 即時查詢。
  - 每支影片對應的 `video_id` 直接使用 `job_id`（見 `main.py` 的
    `/api/upload`），避免與既有 `raw/001`~`raw/010` 手動測試資料衝突。
  - 三個必要前置階段（phase1/phase2/phase3，含 GPU 檢查）任一失敗就
    視為整個工作失敗、不再往下跑；Channel 1（4 引擎）/2/3 彼此獨立，
    个别失败不影响其他 channel 继续尝试（與批次驗收腳本邏輯一致）。

**重要限制（沿用專案一貫的沙盒/本機分工原則）**：本模組在沙盒中只能用
`stage_functions` 參數注入假的 Phase 1-3/Channel 1-3 函式驗證「控制流程」
是否正確（見 tests/test_pipeline_runner.py）；沙盒沒有 GPU 也沒有 Ollama，
無法驗證真實影片的辨識/翻譯品質與真實耗時，需要使用者在本機（RTX 4060 +
Ollama）以真實上傳實際跑一次才算數。

Phase 7 擴充（2026-07-26，使用者決策紀錄，見 PROJECT_NOTES.md 第 16 節）：
新增以下「測試期間方便操作」參數，成品完成後使用者會要求移除／簡化：
  - denoise：是否執行去雜訊（原本寫死只跑 denoise_on）。
  - include_channel1 / channel1_engines：是否執行 Channel 1、要跑哪幾個
    子引擎（原本寫死一律跑滿 4 個）。
  - include_channel3：是否執行 Channel 3（原本寫死一定執行）。
  - config_overrides：暫時覆寫 `config/settings.py` 裡的
    min_confidence（OCR 信心值）／dedup_max_gap_sec（去重時間間隔）／
    clahe_clip_limit（對比強化強度）／denoise_strength（去雜訊強度）。
    這幾個參數目前分散在 preprocessing/pipeline.py、ocr/recognizer.py、
    dedup/deduplicator.py 內部直接讀取全域設定字典，並非函式參數，因此
    改用「執行前暫時覆寫、執行後還原」的方式實作（見
    `_temporary_settings_override`），而不去重構這幾個底層模組的介面
    ——這樣風險最小，且完全符合「測試期間功能、之後會被移除」的定位。
    **已知限制**：這個暫時覆寫是對整個行程共用的設定物件生效，若同時有
    兩個工作平行執行、且都指定了不同的 config_overrides，會互相干擾；
    本專案是單一使用者的本機工具，正常使用情境下不會有這個問題，但這裡
    仍明確記錄下來，之後移除本功能時這個限制也會一併消失。
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Callable, List, Optional

from src.api.job_store import JobStore

# Phase 2 前處理輸出的目錄命名慣例，與既有 10 支測試影片一致
# （`processed/denoise_on` 或 `processed/denoise_off`、`ocr_on`）。
_OCR_DIRNAME = "ocr_on"

CHANNEL1_ENGINES = ["okt", "komoran", "kkma", "mecab"]

# Phase 7 config_overrides 支援的鍵 -> 對應到 config/settings.py 哪個字典的哪個欄位。
_CONFIG_OVERRIDE_TARGETS = {
    "min_confidence": ("OCR_CONFIG", "min_confidence"),
    "dedup_max_gap_sec": ("DEDUP_CONFIG", "max_gap_sec"),
    "clahe_clip_limit": ("PREPROCESS_PARAMS", "clahe_clip_limit"),
    "denoise_strength": ("PREPROCESS_PARAMS", "denoise_strength"),
}


@contextlib.contextmanager
def _temporary_settings_override(overrides: Optional[dict]):
    """
    暫時覆寫 `config/settings.py` 裡的全域設定字典，區塊結束後（含例外時）
    一律還原成原始值。見模組說明「Phase 7 擴充」段落的設計理由與已知限制。
    """
    if not overrides:
        yield
        return

    from config import settings as settings_module

    saved: dict[str, object] = {}
    try:
        for key, value in overrides.items():
            if value is None or key not in _CONFIG_OVERRIDE_TARGETS:
                continue
            dict_name, field_name = _CONFIG_OVERRIDE_TARGETS[key]
            target_dict = getattr(settings_module, dict_name)
            saved[key] = target_dict[field_name]
            target_dict[field_name] = value
        yield
    finally:
        for key, value in saved.items():
            dict_name, field_name = _CONFIG_OVERRIDE_TARGETS[key]
            target_dict = getattr(settings_module, dict_name)
            target_dict[field_name] = value


def _count_manifest_rows(manifest_path: Path) -> int:
    """
    計算 Phase 1 輸出的 `frames/manifest.csv` 有幾張影格（扣掉標題列）。

    用途：2026-07-27 真實使用時發現，某些影片編碼格式（例如 AV1）目前的
    cv2/ffmpeg 建置無法解碼，會導致 Phase 1「執行成功但擷取到 0 張影格」，
    後續 Phase 2/3/Channel 1-3 一路產生 0 筆結果，一直到最後
    `GET /api/jobs/{id}/results` 讀取空白 CSV 時才在 API 層炸開一個不好懂
    的 500 錯誤。加上這個檢查後，能在 Phase 1 剛結束時就明確攔截、提早
    告知使用者原因，不用等整條流程空跑一輪才發現（見
    PROJECT_NOTES.md 第 17 節）。
    """
    if not manifest_path.exists():
        return 0
    with open(manifest_path, encoding="utf-8-sig") as f:
        return max(sum(1 for _ in f) - 1, 0)  # 扣掉標題列


def _run_stage(
    job_store: JobStore, job_id: str, stage_name: str, fn: Callable, *args, **kwargs
) -> tuple[bool, str]:
    """執行單一階段，捕捉例外（含 GPU 檢查用的 SystemExit），寫入 JobStore。"""
    job_store.update_job(job_id, current_stage=stage_name)
    t0 = time.time()
    try:
        fn(*args, **kwargs)
        elapsed = round(time.time() - t0, 2)
        job_store.record_stage(job_id, stage_name, ok=True, elapsed_sec=elapsed)
        return True, ""
    except SystemExit as e:
        elapsed = round(time.time() - t0, 2)
        error = f"SystemExit(code={e.code})：通常代表 GPU 檢查未通過"
        job_store.record_stage(job_id, stage_name, ok=False, elapsed_sec=elapsed, error=error)
        return False, error
    except Exception as e:  # noqa: BLE001 - 刻意捕捉所有例外，讓單一階段失敗不會讓整個背景工作崩潰、狀態卡死
        elapsed = round(time.time() - t0, 2)
        error = f"{type(e).__name__}: {e}"
        job_store.record_stage(job_id, stage_name, ok=False, elapsed_sec=elapsed, error=error)
        return False, error


def _default_stage_functions() -> dict:
    """延後匯入真正的 Phase/Channel 函式（避免沙盒/測試環境需要 torch、easyocr 等重依賴）。"""
    from scripts.run_phase1 import run as phase1
    from scripts.run_phase2 import run as phase2
    from scripts.run_phase3 import run as phase3
    from scripts.run_channel1 import run as channel1
    from scripts.run_channel2 import run as channel2
    from scripts.run_channel3 import run as channel3
    from src.ocr.gpu_check import get_gpu_info

    return {
        "phase1": phase1, "phase2": phase2, "phase3": phase3,
        "channel1": channel1, "channel2": channel2, "channel3": channel3,
        "gpu_check": get_gpu_info,
    }


def run_full_pipeline(
    job_id: str,
    video_path: str,
    job_store: JobStore,
    include_channel1: bool = True,
    channel1_engines: Optional[List[str]] = None,
    include_channel2: bool = True,
    include_channel3: bool = True,
    denoise: bool = True,
    sample_rate_fps: float = 1.0,
    max_frames: Optional[int] = None,
    dict_db: Optional[str] = None,
    model: str = "qwen2.5:7b",
    base_url: str = "http://localhost:11434",
    data_output_root: str = "data/output",
    config_overrides: Optional[dict] = None,
    stage_functions: Optional[dict] = None,
) -> None:
    """
    背景執行完整流程：Phase 1 -> Phase 2 -> GPU 檢查 -> Phase 3 -> Channel 1(x?)/2/3。

    Args:
        job_id: 對應 `JobStore` 的工作代號，同時直接作為 `video_id` 使用
            （見模組說明，避免與既有手動測試影片的 video_id 衝突）。
        video_path: 已儲存到本機磁碟的影片檔案路徑（`main.py` 的
            `/api/upload` 負責把上傳內容先存檔到 `API_CONFIG["upload_dir"]`
            底下，再呼叫本函式）。
        job_store: 供寫入狀態/階段紀錄的 `JobStore` 實例。
        include_channel1: 是否執行 Channel 1（Phase 7 新增，測試用；預設 True）。
        channel1_engines: Channel 1 要執行哪幾個子引擎，預設 None 表示全部
            四個（`CHANNEL1_ENGINES`）；只有 `include_channel1=True` 時才有意義。
        include_channel2: 是否納入 Channel 2（本地 LLM，單支影片可能耗時
            近 1 小時），預設 True（符合使用者「真正接入完整工作流程」的
            決策）；呼叫端可視情況關閉。
        include_channel3: 是否執行 Channel 3（Phase 7 新增，測試用；預設 True）。
        denoise: Phase 2 前處理是否執行去雜訊（Phase 7 新增，測試用；預設 True）。
        config_overrides: 暫時覆寫全域設定（見模組說明），支援的鍵：
            `min_confidence` / `dedup_max_gap_sec` / `clahe_clip_limit` /
            `denoise_strength`；未提供的鍵維持 `config/settings.py` 原值。
        stage_functions: 測試/沙盒用，注入假的階段函式（見模組說明的沙盒
            限制），預設 None 時才會真正匯入 Phase 1-3/Channel 1-3 模組。

    安全網（2026-07-26，模擬驗證後新增）：本函式的實際邏輯在 `_run_full_pipeline_impl`，
    這裡外面再包一層 try/except。原因：`_run_full_pipeline_impl` 一開始的
    `_default_stage_functions()`（匯入六個 Phase/Channel 模組）以及
    `job_store.update_job(job_id, status="running")` 這兩步都發生在任何
    `_run_stage()` 保護之前——模擬測試時發現，只要這兩步之中任何一步拋出
    未預期例外（例如某個模組所需的套件在執行環境中不存在），整個背景工作
    會直接崩潰、`job_store` 內的狀態永遠停在 `queued`，前端呼叫
    `/api/jobs/{id}/status` 會看到工作卡住、卻查不到任何錯誤原因。加上這層
    安全網後，任何未被內層個別階段捕捉到的例外，都會讓工作明確轉為
    `status="failed"` 並寫入錯誤訊息，確保前端一定看得到結果（成功或失敗），
    不會有「永遠查不到怎麼了」的狀態。
    """
    try:
        _run_full_pipeline_impl(
            job_id=job_id, video_path=video_path, job_store=job_store,
            include_channel1=include_channel1, channel1_engines=channel1_engines,
            include_channel2=include_channel2, include_channel3=include_channel3,
            denoise=denoise, sample_rate_fps=sample_rate_fps,
            max_frames=max_frames, dict_db=dict_db, model=model, base_url=base_url,
            data_output_root=data_output_root, config_overrides=config_overrides,
            stage_functions=stage_functions,
        )
    except Exception as e:  # noqa: BLE001 - 最外層安全網，見上方 docstring 說明
        error = f"[未預期例外，非個別階段內的錯誤] {type(e).__name__}: {e}"
        try:
            job_store.update_job(job_id, status="failed", current_stage="pipeline_setup", error=error)
        except Exception:
            # 連 job_store 本身都寫不進去的極端情況：這裡已經無能為力，
            # 但至少不會讓整個背景工作在完全無聲的狀態下消失。
            pass


def _run_full_pipeline_impl(
    job_id: str,
    video_path: str,
    job_store: JobStore,
    include_channel1: bool,
    channel1_engines: Optional[List[str]],
    include_channel2: bool,
    include_channel3: bool,
    denoise: bool,
    sample_rate_fps: float,
    max_frames: Optional[int],
    dict_db: Optional[str],
    model: str,
    base_url: str,
    data_output_root: str,
    config_overrides: Optional[dict],
    stage_functions: Optional[dict],
) -> None:
    """`run_full_pipeline` 的實際邏輯（見該函式 docstring 說明外層安全網的設計原因）。"""
    video_id = job_id
    required_keys = ("phase1", "phase2", "phase3", "channel1", "channel2", "channel3", "gpu_check")
    if stage_functions is None:
        fns = _default_stage_functions()
    elif any(k not in stage_functions for k in required_keys):
        # 測試/沙盒用：允許只覆寫部分階段，其餘缺少的仍延後匯入真實實作。
        fns = {**_default_stage_functions(), **stage_functions}
    else:
        fns = dict(stage_functions)

    engines_to_run = [e for e in (channel1_engines or CHANNEL1_ENGINES) if e in CHANNEL1_ENGINES]

    job_store.update_job(job_id, status="running")

    root = Path(data_output_root) / video_id
    frames_dir = root / "frames"
    processed_dir = root / "processed"
    denoise_tag = "denoise_on" if denoise else "denoise_off"
    ocr_dir = root / _OCR_DIRNAME
    ocr_csv = ocr_dir / "ocr_results.csv"

    with _temporary_settings_override(config_overrides):
        # ---- Phase 1：影片匯入 / 影格採樣 ----
        ok, err = _run_stage(
            job_store, job_id, "phase1", fns["phase1"],
            video_path, str(frames_dir), sample_rate_fps, max_frames,
        )
        if not ok:
            job_store.update_job(job_id, status="failed", current_stage="phase1", error=err)
            return

        # ---- Phase 1 額外檢查：擷取到的影格數是否為 0（見 _count_manifest_rows 說明）----
        frame_count = _count_manifest_rows(frames_dir / "manifest.csv")
        if frame_count == 0:
            msg = (
                "Phase 1 執行沒有拋出例外，但擷取到 0 張影格，通常代表這支影片的編碼格式"
                "目前 OpenCV/ffmpeg 的建置無法解碼（例如 AV1），而不是程式邏輯錯誤。"
                "建議改用 H.264/H.265 編碼的影片測試，或確認本機 ffmpeg 是否已安裝對應解碼器。"
            )
            job_store.record_stage(job_id, "phase1_frame_check", ok=False, elapsed_sec=0.0, error=msg)
            job_store.update_job(job_id, status="failed", current_stage="phase1_frame_check", error=msg)
            return

        # ---- Phase 2：前處理（denoise 開關見 Phase 7 擴充說明）----
        ok, err = _run_stage(
            job_store, job_id, "phase2", fns["phase2"],
            str(frames_dir), str(processed_dir), None, ("on" if denoise else "off"),
        )
        if not ok:
            job_store.update_job(job_id, status="failed", current_stage="phase2", error=err)
            return

        # ---- GPU 檢查（不終止程式的版本，供 API 情境使用）----
        job_store.update_job(job_id, current_stage="gpu_check")
        t0 = time.time()
        try:
            gpu_info = fns["gpu_check"]()
            gpu_ok = bool(gpu_info)
            gpu_err = "" if gpu_ok else "未偵測到可用 GPU，本專案要求 OCR 必須使用 GPU 執行，工作終止。"
        except Exception as e:  # noqa: BLE001
            gpu_ok, gpu_err = False, f"{type(e).__name__}: {e}"
        job_store.record_stage(
            job_id, "gpu_check", ok=gpu_ok, elapsed_sec=round(time.time() - t0, 2), error=gpu_err,
        )
        if not gpu_ok:
            job_store.update_job(job_id, status="failed", current_stage="gpu_check", error=gpu_err)
            return

        # ---- Phase 3：OCR（需要 GPU，已於上一步確認可用）----
        ok, err = _run_stage(
            job_store, job_id, "phase3", fns["phase3"],
            str(processed_dir / denoise_tag), str(ocr_dir),
        )
        if not ok:
            job_store.update_job(job_id, status="failed", current_stage="phase3", error=err)
            return

        # ---- Channel 1：子引擎彼此獨立，個別失敗不影響其他子通道（Phase 7：可整體關閉／選子引擎）----
        if include_channel1:
            for engine in engines_to_run:
                _run_stage(
                    job_store, job_id, f"channel1_{engine}", fns["channel1"],
                    video_id, engine, str(ocr_csv), str(root / f"channel1_{engine}"), dict_db,
                )

        # ---- Channel 2：本地 LLM（可選；耗時最長）----
        if include_channel2:
            _run_stage(
                job_store, job_id, "channel2", fns["channel2"],
                video_id, str(ocr_csv), str(root / "channel2"), model, base_url,
            )

        # ---- Channel 3：混合通道（Phase 7：可整體關閉）----
        if include_channel3:
            _run_stage(
                job_store, job_id, "channel3", fns["channel3"],
                video_id, str(ocr_csv), str(root / "channel3"), dict_db, model, base_url,
            )

    # 只要 phase1/2/3 都成功，即視為工作整體完成——即使某些 channel 失敗
    # （例如 Channel 2/3 需要的 Ollama 未啟動），其餘 channel 的結果仍可
    # 透過 /api/jobs/{id}/results?channel=... 個別查詢，因此不視為整體失敗。
    job_store.update_job(job_id, status="done", current_stage="finished")
