"""
測試 src/api/pipeline_runner.py（Phase 6 背景工作管線的控制流程）。

沙盒沒有真正的 GPU/Ollama，因此全部改用注入的假階段函式
（`stage_functions` 參數）驗證：
  - 成功路徑：全部階段依序執行、job 狀態最終變成 done。
  - phase1/phase2/gpu_check/phase3 任一失敗 -> 視為整體失敗、後續階段
    （包含 GPU 檢查後的 Channel 1/2/3）不會再被呼叫。
  - Channel 1 四引擎／Channel 2／Channel 3 彼此獨立：其中一個失敗，
    其餘仍會被嘗試，整體工作仍算 done（見模組 docstring 的設計理由）。
  - 階段函式丟出 `SystemExit`（對應真實 GPU 檢查失敗的情境）會被正確
    捕捉為該階段失敗，不會讓整個背景工作直接崩潰。
  - Phase 1 擷取到 0 張影格時（2026-07-27 真實使用時發現，AV1 編碼影片
    cv2/ffmpeg 無法解碼會造成這個情況，見 PROJECT_NOTES.md 第 17 節）會被
    提早攔截為失敗，不會浪費時間空跑完整條流程。
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.job_store import JobStore  # noqa: E402
from src.api.pipeline_runner import CHANNEL1_ENGINES, run_full_pipeline  # noqa: E402


def _ok(*args, **kwargs):
    return None


def _fail(*args, **kwargs):
    raise RuntimeError("boom")


def _system_exit(*args, **kwargs):
    raise SystemExit(1)


def _ok_phase1_with_one_frame(video_path, frames_dir, sample_rate_fps, max_frames):
    """
    預設的假 phase1：模擬真實 `scripts/run_phase1.run()` 的關鍵副作用——
    在 `frames_dir` 寫出 `manifest.csv`——並且寫入剛好 1 張影格，讓
    `pipeline_runner._count_manifest_rows()` 的 0 張影格檢查能自然通過，
    這樣其餘測試（驗證後續階段是否被正確呼叫）才不會被這項新檢查誤擋下來。
    需要特別測試「0 張影格」情境時，改用不寫檔案的 `_ok` 即可觸發。
    """
    Path(frames_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(frames_dir) / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_id", "timestamp_sec", "filename"])
        writer.writeheader()
        writer.writerow({"frame_id": 0, "timestamp_sec": 0.0, "filename": "frame_000000.jpg"})


def _make_store(tmp_path) -> JobStore:
    return JobStore(tmp_path / "jobs.sqlite3")


def _base_fns(**overrides):
    fns = {
        "phase1": _ok_phase1_with_one_frame, "phase2": _ok, "phase3": _ok,
        "channel1": _ok, "channel2": _ok, "channel3": _ok,
        "gpu_check": lambda: [{"index": 0, "name": "fake-gpu"}],
    }
    fns.update(overrides)
    return fns


def test_success_path_all_stages_recorded(tmp_path):
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv", include_channel2=True)

    run_full_pipeline(
        "job1", "video.mkv", store, include_channel2=True,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "done"
    stage_names = [s["stage"] for s in job["stages"]]
    expected = (
        ["phase1", "phase2", "gpu_check", "phase3"]
        + [f"channel1_{e}" for e in CHANNEL1_ENGINES]
        + ["channel2", "channel3"]
    )
    assert stage_names == expected
    assert all(s["ok"] == 1 for s in job["stages"])


def test_success_path_without_channel2(tmp_path):
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv", include_channel2=False)

    run_full_pipeline(
        "job1", "video.mkv", store, include_channel2=False,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "done"
    stage_names = [s["stage"] for s in job["stages"]]
    assert "channel2" not in stage_names
    assert "channel3" in stage_names


def test_phase1_failure_stops_everything(tmp_path):
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")

    run_full_pipeline(
        "job1", "video.mkv", store,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(phase1=_fail),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "failed"
    assert job["current_stage"] == "phase1"
    assert "boom" in job["error"]
    assert [s["stage"] for s in job["stages"]] == ["phase1"]


def test_gpu_unavailable_stops_before_phase3(tmp_path):
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")

    run_full_pipeline(
        "job1", "video.mkv", store,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(gpu_check=lambda: []),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "failed"
    assert job["current_stage"] == "gpu_check"
    stage_names = [s["stage"] for s in job["stages"]]
    assert stage_names == ["phase1", "phase2", "gpu_check"]
    assert "GPU" in job["error"]


def test_phase3_systemexit_is_caught_not_crashed(tmp_path):
    """SystemExit 對應真實 ensure_gpu_available() 失敗的情境，不應該讓整個背景工作直接崩潰。"""
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")

    run_full_pipeline(
        "job1", "video.mkv", store,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(phase3=_system_exit),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "failed"
    assert job["current_stage"] == "phase3"
    assert "SystemExit" in job["error"]


def test_channel_failures_are_independent_and_job_still_done(tmp_path):
    """Channel 1 其中一個引擎失敗、Channel 2 失敗，不應該影響 Channel 3 被嘗試，整體仍算 done。"""
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv", include_channel2=True)

    calls = []

    def channel1_fails_for_kkma(video_id, engine, *args, **kwargs):
        calls.append(("channel1", engine))
        if engine == "kkma":
            raise RuntimeError("kkma exploded")

    def channel2_fails(*args, **kwargs):
        calls.append(("channel2",))
        raise RuntimeError("ollama not running")

    def channel3_ok(*args, **kwargs):
        calls.append(("channel3",))

    run_full_pipeline(
        "job1", "video.mkv", store, include_channel2=True,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(
            channel1=channel1_fails_for_kkma, channel2=channel2_fails, channel3=channel3_ok,
        ),
    )

    job = store.get_job_with_stages("job1")
    # phase1/2/3 都成功時，即使部分 channel 失敗，整體仍視為 done（見 pipeline_runner.py 設計理由）
    assert job["status"] == "done"

    stage_map = {s["stage"]: s for s in job["stages"]}
    assert stage_map["channel1_okt"]["ok"] == 1
    assert stage_map["channel1_kkma"]["ok"] == 0
    assert "kkma exploded" in stage_map["channel1_kkma"]["error"]
    assert stage_map["channel2"]["ok"] == 0
    assert stage_map["channel3"]["ok"] == 1
    # 確認全部四個引擎跟 channel3 都真的被嘗試過，channel1 的失敗沒有中斷後續
    assert ("channel3",) in calls
    assert len([c for c in calls if c[0] == "channel1"]) == len(CHANNEL1_ENGINES)


def test_zero_frames_extracted_stops_pipeline_with_clear_error(tmp_path):
    """
    2026-07-27 真實使用時發現的問題：AV1 編碼影片讓 cv2/ffmpeg 解碼失敗，
    Phase 1 沒有拋出例外、但寫出的 manifest.csv 是 0 張影格，若不攔截，
    後續 Phase 2/3/Channel 1-3 會一路空跑到底、最後才在 API 讀取結果時
    炸開一個難懂的錯誤。這裡驗證新增的檢查會在 Phase 1 剛結束時就攔截。
    """
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")
    calls = []

    def phase1_zero_frames(video_path, frames_dir, sample_rate_fps, max_frames):
        # 模擬真實情況：manifest.csv 有寫出來，但裡面 0 張影格（只有標題列）。
        Path(frames_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(frames_dir) / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["frame_id", "timestamp_sec", "filename"])
            writer.writeheader()

    run_full_pipeline(
        "job1", "video.mkv", store,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(
            phase1=phase1_zero_frames,
            phase2=lambda *a, **k: calls.append("phase2"),
            channel1=lambda *a, **k: calls.append("channel1"),
        ),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "failed"
    assert job["current_stage"] == "phase1_frame_check"
    assert "0 張影格" in job["error"]
    stage_names = [s["stage"] for s in job["stages"]]
    assert stage_names == ["phase1", "phase1_frame_check"]
    # phase2/channel1 完全不應該被呼叫到——提早攔截，不空跑後續階段
    assert calls == []


def test_zero_frames_check_ignores_missing_manifest_gracefully(tmp_path):
    """phase1 若連 manifest.csv 都沒寫出來（理論上不該發生），也要能被同一個檢查攔截，而不是拋出未預期例外。"""
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")

    run_full_pipeline(
        "job1", "video.mkv", store,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(phase1=_ok),  # _ok 完全不寫任何檔案
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "failed"
    assert job["current_stage"] == "phase1_frame_check"


def test_denoise_off_passes_correct_mode_and_processed_dir(tmp_path):
    """Phase 7：denoise=False 時，phase2 應收到 denoise 模式 "off"，phase3 應讀取 processed/denoise_off。"""
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")
    calls = {}

    def phase2_spy(frames_dir, out_dir, roi, denoise_mode):
        calls["phase2_denoise_mode"] = denoise_mode

    def phase3_spy(processed_dir, out_dir):
        calls["phase3_processed_dir"] = processed_dir

    run_full_pipeline(
        "job1", "video.mkv", store, denoise=False,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(phase2=phase2_spy, phase3=phase3_spy),
    )

    assert calls["phase2_denoise_mode"] == "off"
    assert calls["phase3_processed_dir"].endswith("processed/denoise_off") or \
        calls["phase3_processed_dir"].endswith("processed\\denoise_off")


def test_include_channel1_false_skips_all_four_engines(tmp_path):
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv", include_channel2=False)
    calls = []

    run_full_pipeline(
        "job1", "video.mkv", store, include_channel1=False, include_channel2=False,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(channel1=lambda *a, **k: calls.append(a)),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "done"
    stage_names = [s["stage"] for s in job["stages"]]
    assert not any(name.startswith("channel1_") for name in stage_names)
    assert calls == []


def test_channel1_engines_subset_only_runs_selected_engines(tmp_path):
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv", include_channel2=False)
    called_engines = []

    def channel1_spy(video_id, engine, *args, **kwargs):
        called_engines.append(engine)

    run_full_pipeline(
        "job1", "video.mkv", store, include_channel2=False,
        channel1_engines=["okt", "mecab"],
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(channel1=channel1_spy),
    )

    job = store.get_job_with_stages("job1")
    stage_names = [s["stage"] for s in job["stages"]]
    assert set(called_engines) == {"okt", "mecab"}
    assert "channel1_okt" in stage_names
    assert "channel1_mecab" in stage_names
    assert "channel1_komoran" not in stage_names
    assert "channel1_kkma" not in stage_names


def test_include_channel3_false_skips_channel3(tmp_path):
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv", include_channel2=False)
    calls = []

    run_full_pipeline(
        "job1", "video.mkv", store, include_channel2=False, include_channel3=False,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(channel3=lambda *a, **k: calls.append(a)),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "done"
    stage_names = [s["stage"] for s in job["stages"]]
    assert "channel3" not in stage_names
    assert calls == []


def test_config_overrides_applied_during_run_and_restored_after(tmp_path):
    """
    Phase 7：config_overrides 應該在管線執行期間真的把 config/settings.py
    的全域值改掉（讓 preprocessing/recognizer/deduplicator 等直接讀取全域
    設定的模組能看到新值），並在管線結束後（即使中途失敗）還原成原始值。
    """
    from config import settings as settings_module

    original_clip_limit = settings_module.PREPROCESS_PARAMS["clahe_clip_limit"]
    original_min_confidence = settings_module.OCR_CONFIG["min_confidence"]
    seen_during_run = {}

    def phase2_spy(*args, **kwargs):
        seen_during_run["clahe_clip_limit"] = settings_module.PREPROCESS_PARAMS["clahe_clip_limit"]

    def phase3_spy(*args, **kwargs):
        seen_during_run["min_confidence"] = settings_module.OCR_CONFIG["min_confidence"]

    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv", include_channel2=False)

    run_full_pipeline(
        "job1", "video.mkv", store, include_channel2=False, include_channel3=False,
        data_output_root=str(tmp_path / "output"),
        config_overrides={"clahe_clip_limit": 9.5, "min_confidence": 0.9},
        stage_functions=_base_fns(phase2=phase2_spy, phase3=phase3_spy),
    )

    assert seen_during_run["clahe_clip_limit"] == 9.5
    assert seen_during_run["min_confidence"] == 0.9
    # 執行結束後必須還原，不能讓下一個工作或其他測試被污染
    assert settings_module.PREPROCESS_PARAMS["clahe_clip_limit"] == original_clip_limit
    assert settings_module.OCR_CONFIG["min_confidence"] == original_min_confidence


def test_config_overrides_restored_even_when_a_stage_fails(tmp_path):
    """安全網交互測試：即使 phase1 失敗提早 return，config_overrides 仍必須被還原。"""
    from config import settings as settings_module

    original = settings_module.DEDUP_CONFIG["max_gap_sec"]
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")

    run_full_pipeline(
        "job1", "video.mkv", store,
        data_output_root=str(tmp_path / "output"),
        config_overrides={"dedup_max_gap_sec": 42.0},
        stage_functions=_base_fns(phase1=_fail),
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "failed"
    assert settings_module.DEDUP_CONFIG["max_gap_sec"] == original


def test_unexpected_exception_before_running_status_is_caught_by_safety_net(tmp_path, monkeypatch):
    """
    安全網測試（2026-07-26，模擬驗證後新增）：模擬「_default_stage_functions()
    匯入真實模組時就先炸掉」的情境（例如某個模組所需的套件在執行環境中不存在，
    這在沙盒模擬 Phase 6 時真的發生過一次，見 PROJECT_NOTES.md）。

    這種例外發生在任何 `_run_stage()` 保護、以及 `status="running"` 被寫入
    之前，若沒有最外層安全網，job 會永遠卡在 "queued"、`job_stages` 完全
    是空的，前端呼叫 status API 會查不到任何失敗原因。加上安全網後，這裡
    應該明確看到 status="failed"，且錯誤訊息包含原始例外內容。
    """
    store = _make_store(tmp_path)
    store.create_job("job1", "job1", "a.mkv")

    import src.api.pipeline_runner as pipeline_runner_module

    def _boom_setup():
        raise ModuleNotFoundError("No module named 'torch'（模擬）")

    monkeypatch.setattr(pipeline_runner_module, "_default_stage_functions", _boom_setup)

    run_full_pipeline(
        "job1", "video.mkv", store,
        data_output_root=str(tmp_path / "output"),
        stage_functions=None,  # 刻意不注入，才會真的走到 _default_stage_functions()
    )

    job = store.get_job_with_stages("job1")
    assert job["status"] == "failed"
    assert job["current_stage"] == "pipeline_setup"
    assert "torch" in job["error"]
    assert "ModuleNotFoundError" in job["error"]
    # 確認沒有任何階段被誤記為成功——安全網是在所有階段之前就攔截住的
    assert job["stages"] == []


def test_video_id_defaults_to_job_id(tmp_path):
    """video_id 直接使用 job_id（見模組說明），確認輸出路徑確實落在 <root>/<job_id>/ 底下。"""
    store = _make_store(tmp_path)
    store.create_job("my-job-42", "my-job-42", "a.mkv")

    received_video_ids = []

    def record_video_id(video_id, engine, ocr_csv, out_dir, dict_db):
        received_video_ids.append(video_id)

    run_full_pipeline(
        "my-job-42", "video.mkv", store, include_channel2=False,
        data_output_root=str(tmp_path / "output"),
        stage_functions=_base_fns(channel1=record_video_id),
    )

    assert all(v == "my-job-42" for v in received_video_ids)
