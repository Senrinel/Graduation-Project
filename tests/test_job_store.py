"""測試 src/api/job_store.py（Phase 6 工作狀態持久化，SQLite）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.job_store import JobStore  # noqa: E402


def test_create_and_get_job(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job1", video_id="job1", original_filename="a.mkv", include_channel2=True)

    job = store.get_job("job1")
    assert job is not None
    assert job["video_id"] == "job1"
    assert job["original_filename"] == "a.mkv"
    assert job["status"] == "queued"
    assert job["current_stage"] is None
    assert job["include_channel2"] == 1


def test_get_job_missing_returns_none(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    assert store.get_job("does-not-exist") is None


def test_update_job_partial_fields(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job1", "job1", "a.mkv")

    store.update_job("job1", status="running", current_stage="phase1")
    job = store.get_job("job1")
    assert job["status"] == "running"
    assert job["current_stage"] == "phase1"
    assert job["error"] is None

    store.update_job("job1", status="failed", error="boom")
    job = store.get_job("job1")
    assert job["status"] == "failed"
    assert job["error"] == "boom"
    # current_stage 沒有在這次 update 中指定，應保留先前的值
    assert job["current_stage"] == "phase1"


def test_record_and_list_stages_in_order(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job1", "job1", "a.mkv")

    store.record_stage("job1", "phase1", ok=True, elapsed_sec=1.5)
    store.record_stage("job1", "phase2", ok=True, elapsed_sec=2.5)
    store.record_stage("job1", "phase3", ok=False, elapsed_sec=0.1, error="no gpu")

    stages = store.list_stages("job1")
    assert [s["stage"] for s in stages] == ["phase1", "phase2", "phase3"]
    assert stages[0]["ok"] == 1
    assert stages[2]["ok"] == 0
    assert stages[2]["error"] == "no gpu"


def test_get_job_with_stages_combines_both(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job1", "job1", "a.mkv")
    store.record_stage("job1", "phase1", ok=True, elapsed_sec=1.0)

    job = store.get_job_with_stages("job1")
    assert job["job_id"] == "job1"
    assert len(job["stages"]) == 1
    assert job["stages"][0]["stage"] == "phase1"


def test_get_job_with_stages_missing_returns_none(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    assert store.get_job_with_stages("nope") is None


def test_store_persists_across_new_instances(tmp_path):
    """模擬伺服器重啟：重新用同一個 db 檔案建立新的 JobStore 實例，資料應仍在。"""
    db_path = tmp_path / "jobs.sqlite3"
    store1 = JobStore(db_path)
    store1.create_job("job1", "job1", "a.mkv")
    store1.record_stage("job1", "phase1", ok=True, elapsed_sec=1.0)

    store2 = JobStore(db_path)
    job = store2.get_job_with_stages("job1")
    assert job is not None
    assert job["status"] == "queued"
    assert len(job["stages"]) == 1


def test_job_logs_recording_and_listing(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_log_test", "job_log_test", "video.mp4")

    store.record_log("job_log_test", "Line 1: started")
    store.record_log("job_log_test", "Line 2: processing")
    store.record_log("job_log_test", "Line 3: done")

    all_logs = store.list_logs("job_log_test")
    assert len(all_logs) == 3
    assert all_logs[0]["message"] == "Line 1: started"
    assert all_logs[2]["message"] == "Line 3: done"

    # 增量輪詢（after_id）
    first_id = all_logs[0]["id"]
    new_logs = store.list_logs("job_log_test", after_id=first_id)
    assert len(new_logs) == 2
    assert new_logs[0]["message"] == "Line 2: processing"

    # 清除日誌
    store.clear_logs("job_log_test")
    assert store.list_logs("job_log_test") == []


def test_cancelled_status_supported(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_cancel_test", "job_cancel_test", "v.mkv")
    store.update_job("job_cancel_test", status="cancelled", error="使用者手動中斷")
    job = store.get_job("job_cancel_test")
    assert job["status"] == "cancelled"
    assert job["error"] == "使用者手動中斷"

