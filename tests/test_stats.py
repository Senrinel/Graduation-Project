"""測試 src/nlp/stats.py（RunReport / RunReportBuilder）"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nlp.stats import RunReport, RunReportBuilder  # noqa: E402


def test_dict_hit_rate_computed_correctly():
    builder = RunReportBuilder(channel="channel1_okt", video_id="001")
    builder.record_word(dict_hit=True)
    builder.record_word(dict_hit=True)
    builder.record_word(dict_hit=False)
    builder.record_word(dict_hit=False)

    report = builder.build()
    assert report.word_count_total == 4
    assert report.dict_hit_count == 2
    assert report.dict_hit_rate == 0.5


def test_dict_hit_rate_zero_when_no_words():
    builder = RunReportBuilder(channel="channel1_okt", video_id="001")
    report = builder.build()
    assert report.word_count_total == 0
    assert report.dict_hit_rate == 0.0


def test_module_timer_accumulates_across_repeated_calls():
    builder = RunReportBuilder(channel="channel1_mecab", video_id="001")
    with builder.time_module("dict_lookup"):
        time.sleep(0.01)
    with builder.time_module("dict_lookup"):
        time.sleep(0.01)

    report = builder.build()
    assert "dict_lookup" in report.module_times
    # 兩次 with 區塊耗時應該累加，而不是後面覆蓋前面
    assert report.module_times["dict_lookup"] >= 0.02


def test_llm_fallback_counts():
    builder = RunReportBuilder(channel="channel3", video_id="001")
    builder.record_llm_call(fallback_success=True)
    builder.record_llm_call(fallback_success=True)
    builder.record_llm_call(fallback_success=False)
    builder.record_llm_call()  # Channel 2 一般呼叫，不算 fallback 成功或失敗

    report = builder.build()
    assert report.llm_call_count == 4
    assert report.llm_fallback_success_count == 2
    assert report.llm_fallback_fail_count == 1


def test_error_count():
    builder = RunReportBuilder(channel="channel1_okt", video_id="001")
    builder.record_error()
    builder.record_error()
    report = builder.build()
    assert report.error_count == 2


def test_write_csv_flattens_module_times(tmp_path):
    builder = RunReportBuilder(channel="channel1_okt", video_id="001")
    with builder.time_module("clean"):
        pass
    with builder.time_module("dedup"):
        pass
    builder.record_word(dict_hit=True)
    report = builder.build()

    output_path = tmp_path / "stats" / "channel1_okt_report.csv"
    RunReportBuilder.write_csv(report, str(output_path))

    assert output_path.exists()
    with open(output_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    row = rows[0]
    assert row["channel"] == "channel1_okt"
    assert "module_time_clean" in row
    assert "module_time_dedup" in row
    assert "module_times" not in row  # 巢狀欄位不應該原樣出現在 CSV 裡


def test_run_report_direct_construction():
    # RunReport 也可以不透過 builder 直接建立（例如讀取既有 CSV 後重建物件）
    report = RunReport(
        channel="channel2", video_id="002", run_timestamp="2026-07-26T00:00:00",
        total_time_sec=1.23, word_count_total=10, dict_hit_count=5, dict_hit_rate=0.5,
    )
    assert report.channel == "channel2"
    assert report.module_times == {}
