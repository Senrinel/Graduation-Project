"""
Phase 6：工作狀態持久化 (Job Store)
=====================================
使用者決策紀錄（2026-07-26）：Channel 2 單支影片耗時可達近 1 小時，若 API
伺服器在工作進行中重啟，工作狀態不應直接消失——因此採用「輕量持久化」：
用 SQLite 記錄每個上傳工作的狀態與每個階段的執行結果，伺服器重啟後仍可
透過 `GET /api/jobs/{job_id}/status` 查詢先前工作的進度。

設計原則：
- 每次呼叫都開新的 sqlite3 連線並在結束後關閉（而非長期持有一個連線跨
  執行緒共用），避免 Phase 6 的背景執行緒（跑真正的 pipeline，耗時可達
  數十分鐘）與主執行緒（處理 API 請求）之間對同一個連線物件產生執行緒
  安全疑慮；SQLite 檔案本身的 lock 機制足以應付這裡「單一本機使用者、
  同時工作數量很少」的實際使用情境。
- 資料表刻意設計成兩張：`jobs`（一個工作一列，記錄目前狀態）與
  `job_stages`（一個工作可有多列，記錄每個階段的成功/失敗/耗時），
  後者的欄位設計刻意比照 `scripts/_pipeline_smoke_test.py` 的
  `_run_stage()` 回傳格式（stage/ok/elapsed_sec/error），讓「單支影片
  批次驗收」與「API 觸發的單一工作」共用同一套階段記錄語意。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional


_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    original_filename TEXT,
    status TEXT NOT NULL,
    current_stage TEXT,
    error TEXT,
    include_channel2 INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_STAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    ok INTEGER NOT NULL,
    elapsed_sec REAL NOT NULL,
    error TEXT,
    recorded_at TEXT NOT NULL
);
"""

_LOGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    message TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_logs_job_id_id ON job_logs (job_id, id);
"""

# 工作狀態允許的值，供路由層驗證/文件參考用。
JOB_STATUSES = ("queued", "running", "done", "failed", "cancelled")


class JobStore:
    """SQLite backed 工作狀態儲存。可跨行程/跨執行緒安全使用（見模組說明）。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_JOBS_SCHEMA)
            conn.execute(_STAGES_SCHEMA)
            conn.executescript(_LOGS_SCHEMA)

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    def create_job(
        self, job_id: str, video_id: str, original_filename: str, include_channel2: bool = True,
    ) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs "
                "(job_id, video_id, original_filename, status, current_stage, error, "
                " include_channel2, created_at, updated_at) "
                "VALUES (?, ?, ?, 'queued', NULL, NULL, ?, ?, ?)",
                (job_id, video_id, original_filename, int(include_channel2), now, now),
            )

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        current_stage: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        fields, values = [], []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if current_stage is not None:
            fields.append("current_stage = ?")
            values.append(current_stage)
        if error is not None:
            fields.append("error = ?")
            values.append(error)
        fields.append("updated_at = ?")
        values.append(self._now())
        values.append(job_id)

        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?", values)

    def record_stage(self, job_id: str, stage: str, ok: bool, elapsed_sec: float, error: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO job_stages (job_id, stage, ok, elapsed_sec, error, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, stage, int(ok), elapsed_sec, error, self._now()),
            )

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def list_stages(self, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT stage, ok, elapsed_sec, error, recorded_at FROM job_stages "
                "WHERE job_id = ? ORDER BY id ASC",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_job_with_stages(self, job_id: str) -> Optional[dict]:
        job = self.get_job(job_id)
        if job is None:
            return None
        job["stages"] = self.list_stages(job_id)
        return job

    def record_log(self, job_id: str, message: str) -> None:
        """寫入一筆即時執行日誌。"""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO job_logs (job_id, message, recorded_at) VALUES (?, ?, ?)",
                (job_id, message, self._now()),
            )

    def list_logs(self, job_id: str, after_id: int = 0, limit: int = 300) -> list[dict]:
        """讀取指定工作大於 after_id 的日誌清單，支援增量輪詢。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, message, recorded_at FROM job_logs "
                "WHERE job_id = ? AND id > ? ORDER BY id ASC LIMIT ?",
                (job_id, after_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_logs(self, job_id: str) -> None:
        """清空指定工作的日誌。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM job_logs WHERE job_id = ?", (job_id,))

