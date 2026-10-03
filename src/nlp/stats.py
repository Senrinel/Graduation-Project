"""
Phase 5 執行報告 (RunReport) 標準化 schema 與寫檔工具
=======================================================
定義三通道（Channel 1/2/3）共用的統計欄位格式，並提供一個簡單的
累加器 `RunReportBuilder`，方便在通道執行過程中即時記錄各模塊耗時與
計數，執行結束後統一寫成 CSV，供 Phase 5 尾聲的通道/模組比較分析使用。

決策紀錄（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 1、5 節，2026-07-26 確認）：
- 準確度先以「字典命中率」（dict_hit_rate）作為代理指標。
- 輸出格式：CSV（規劃路徑 `data/output/<video>/stats/<channel>_report.csv`），
  跟現有 Phase 1-3 的 manifest.csv／ocr_results.csv 風格一致，方便直接用
  pandas 或 Excel 開啟比較。

用法：
    builder = RunReportBuilder(channel="channel1_okt", video_id="001")
    with builder.time_module("clean"):
        cleaned = clean_ocr_text(raw_text)
    with builder.time_module("dict_lookup"):
        candidates = dictionary.lookup(word)
    builder.record_word(dict_hit=bool(candidates))
    report = builder.build()
    RunReportBuilder.write_csv(report, "data/output/001/stats/channel1_okt_report.csv")
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field


class RunReport(BaseModel):
    """三通道共用的標準化執行報告欄位（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 5 節）。"""

    channel: str = Field(
        ...,
        description=(
            "channel1_okt / channel1_komoran / channel1_kkma / channel1_mecab / "
            "channel2 / channel3"
        ),
    )
    video_id: str
    run_timestamp: str

    total_time_sec: float = 0.0
    module_times: Dict[str, float] = Field(
        default_factory=dict, description="各模塊耗時明細，例如 clean/dedup/tokenize/dict_lookup/llm_call/write_output"
    )

    word_count_total: int = 0
    dict_hit_count: int = 0
    dict_hit_rate: float = 0.0

    llm_call_count: int = 0
    llm_fallback_success_count: int = 0
    llm_fallback_fail_count: int = 0

    error_count: int = 0

    def to_flat_dict(self) -> dict:
        """把巢狀的 module_times 攤平成單層欄位（module_time_<name>），方便寫入 CSV。"""
        flat = self.model_dump(exclude={"module_times"})
        for module_name, elapsed in self.module_times.items():
            flat[f"module_time_{module_name}"] = elapsed
        return flat


class _ModuleTimer:
    """`RunReportBuilder.time_module()` 回傳的 context manager，內部使用，不直接建立。"""

    def __init__(self, builder: "RunReportBuilder", module_name: str):
        self._builder = builder
        self._module_name = module_name
        self._t0 = 0.0

    def __enter__(self) -> "_ModuleTimer":
        self._t0 = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = time.time() - self._t0
        existing = self._builder._module_times.get(self._module_name, 0.0)
        self._builder._module_times[self._module_name] = existing + elapsed


class RunReportBuilder:
    """
    在通道執行期間累加計時與計數，結束後產生 `RunReport` 並可寫成 CSV。

    同一個 module_name 若在一次執行中被計時多次（例如「dict_lookup」對每個
    詞彙都會執行一次），耗時會累加加總，而不是互相覆蓋。
    """

    def __init__(self, channel: str, video_id: str):
        self.channel = channel
        self.video_id = video_id
        self._start_time = time.time()
        self._module_times: Dict[str, float] = {}
        self._word_count_total = 0
        self._dict_hit_count = 0
        self._llm_call_count = 0
        self._llm_fallback_success_count = 0
        self._llm_fallback_fail_count = 0
        self._error_count = 0

    def time_module(self, module_name: str) -> _ModuleTimer:
        """回傳一個 context manager，離開 with 區塊時自動記錄該模塊耗時（可重複呼叫累加）。"""
        return _ModuleTimer(self, module_name)

    def record_word(self, dict_hit: bool) -> None:
        """記錄一個詞彙的處理結果：是否命中字典。"""
        self._word_count_total += 1
        if dict_hit:
            self._dict_hit_count += 1

    def record_llm_call(self, fallback_success: Optional[bool] = None) -> None:
        """
        記錄一次 LLM 呼叫（Channel 2 的主要處理，或 Channel 3 的 fallback）。

        Args:
            fallback_success: Channel 3 fallback 專用；None 表示這不是一次
                fallback 呼叫（例如 Channel 2 的一般呼叫），True/False 則
                分別記為 fallback 成功/失敗次數。
        """
        self._llm_call_count += 1
        if fallback_success is True:
            self._llm_fallback_success_count += 1
        elif fallback_success is False:
            self._llm_fallback_fail_count += 1

    def record_error(self) -> None:
        self._error_count += 1

    def build(self) -> RunReport:
        """結算目前累加的統計數據，產生一份 RunReport（可重複呼叫，total_time_sec 會持續累加到呼叫當下）。"""
        total_time_sec = time.time() - self._start_time
        dict_hit_rate = (
            self._dict_hit_count / self._word_count_total if self._word_count_total else 0.0
        )
        return RunReport(
            channel=self.channel,
            video_id=self.video_id,
            run_timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            total_time_sec=total_time_sec,
            module_times=dict(self._module_times),
            word_count_total=self._word_count_total,
            dict_hit_count=self._dict_hit_count,
            dict_hit_rate=dict_hit_rate,
            llm_call_count=self._llm_call_count,
            llm_fallback_success_count=self._llm_fallback_success_count,
            llm_fallback_fail_count=self._llm_fallback_fail_count,
            error_count=self._error_count,
        )

    @staticmethod
    def write_csv(report: RunReport, output_path: str) -> None:
        """將 RunReport 寫成單列 CSV（含表頭），輸出目錄不存在時自動建立。"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        flat = report.to_flat_dict()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(flat.keys()))
            writer.writeheader()
            writer.writerow(flat)
