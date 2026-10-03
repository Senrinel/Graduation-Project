"""
測試 scripts/run_channel3.py（Channel 3：Channel 1 架構 + LLM Fallback）

用小型合成字典索引（沿用 test_build_dictionary_index.py 的 SAMPLE_XML）
+ 真實 Mecab-ko 斷詞（沙盒已驗證可用，非 mock）+ FakeLLMClient（可控制
回應內容，不需要真正啟動 Ollama），驗證「fallback 觸發 -> 成功挽回」
與「fallback 觸發 -> 確實猜不到」兩種情況下的統計數據與輸出行為是否正確。
"""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("mecab")

from scripts.build_dictionary_index import build_index  # noqa: E402
from scripts.run_channel3 import run  # noqa: E402
from tests.test_build_dictionary_index import SAMPLE_XML, NO_EQUIVALENT_MARKER  # noqa: E402


class FakeLLMClient:
    """每次 fallback 呼叫都回傳同一個固定猜測結果的假 LLM client。"""

    def __init__(self, fixed_guess: str):
        self.fixed_guess = fixed_guess
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return f'{{"guessed_word": "{self.fixed_guess}"}}'


def _make_dict_index(tmp_path) -> str:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "sample.xml").write_text(SAMPLE_XML, encoding="utf-8")
    db_path = tmp_path / "index.sqlite3"
    build_index(xml_dir, db_path, NO_EQUIVALENT_MARKER)
    return str(db_path)


def _make_ocr_csv(tmp_path, text: str) -> str:
    csv_path = tmp_path / "ocr_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_id", "timestamp_sec", "text", "bbox", "confidence"])
        writer.writeheader()
        writer.writerow({
            "frame_id": 0, "timestamp_sec": 0.0, "text": text,
            "bbox": "[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]", "confidence": 0.9,
        })
    return str(csv_path)


# SAMPLE_XML 只包含「가」（兩個同形詞）與「다른단어」，這句話斷詞後的
# 詞彙理論上全都查不到（不含這兩個字），確保一定會觸發 fallback。
UNKNOWN_SENTENCE = "완전히 새로운 문장입니다"


def test_fallback_success_recovers_dict_hit(tmp_path):
    dict_db = _make_dict_index(tmp_path)
    ocr_csv = _make_ocr_csv(tmp_path, UNKNOWN_SENTENCE)
    out_dir = tmp_path / "out"

    fake_client = FakeLLMClient(fixed_guess="다른단어")  # 猜的詞在小字典中存在
    run("test_video", ocr_csv, str(out_dir), dict_db=dict_db, llm_client=fake_client)

    stats_csv = out_dir.parent / "stats" / "channel3_report.csv"
    with open(stats_csv, encoding="utf-8") as f:
        row = next(csv.DictReader(f))

    assert int(row["llm_call_count"]) > 0
    assert fake_client.call_count == int(row["llm_call_count"])
    assert int(row["llm_fallback_success_count"]) == int(row["llm_call_count"])
    assert int(row["llm_fallback_fail_count"]) == 0
    # fallback 全部成功挽回，dict_hit_count 應等於 word_count_total
    assert row["dict_hit_count"] == row["word_count_total"]

    export_csv_path = out_dir / "export.csv"
    with open(export_csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0
    assert all(r["原文"] == "다른단어" for r in rows)
    assert all("LLM fallback 命中" in r["備註"] for r in rows)


def test_fallback_failure_skips_word(tmp_path):
    dict_db = _make_dict_index(tmp_path)
    ocr_csv = _make_ocr_csv(tmp_path, UNKNOWN_SENTENCE)
    out_dir = tmp_path / "out"

    fake_client = FakeLLMClient(fixed_guess="")  # LLM 每次都明確表示猜不到
    run("test_video", ocr_csv, str(out_dir), dict_db=dict_db, llm_client=fake_client)

    stats_csv = out_dir.parent / "stats" / "channel3_report.csv"
    with open(stats_csv, encoding="utf-8") as f:
        row = next(csv.DictReader(f))

    assert int(row["llm_call_count"]) > 0
    assert int(row["llm_fallback_success_count"]) == 0
    assert int(row["llm_fallback_fail_count"]) == int(row["llm_call_count"])
    assert row["dict_hit_count"] == "0"

    export_csv_path = out_dir / "export.csv"
    with open(export_csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 0  # 全部 fallback 失敗，沒有任何候選列輸出


def test_no_fallback_needed_when_dictionary_already_hits(tmp_path):
    """字典本身就查得到的詞（「가」），不應該觸發任何 LLM 呼叫。"""
    dict_db = _make_dict_index(tmp_path)
    ocr_csv = _make_ocr_csv(tmp_path, "가")
    out_dir = tmp_path / "out"

    fake_client = FakeLLMClient(fixed_guess="不應該被呼叫")
    run("test_video", ocr_csv, str(out_dir), dict_db=dict_db, llm_client=fake_client)

    assert fake_client.call_count == 0

    stats_csv = out_dir.parent / "stats" / "channel3_report.csv"
    with open(stats_csv, encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert int(row["llm_call_count"]) == 0
    assert row["dict_hit_count"] == row["word_count_total"]
