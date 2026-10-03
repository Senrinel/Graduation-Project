"""
Phase 5 Channel 1 執行入口：本地套件通道（多引擎子通道）
================================================================
串接「OCR 原始文字 -> Regex 清理 -> 跨影格去重 -> 斷詞（依 --engine 切換
Okt/Komoran/Kkma/Mecab-ko）-> 字典查詢 -> 結構化輸出」，並記錄執行報告
（RunReport）供之後跨通道／跨引擎比較（見 PHASE5_MULTI_CHANNEL_PLAN.md
第 2、5 節）。

Hannanum 已於 2026-07-26 正式排除（見 PROJECT_NOTES.md 13.6 節），
--engine 不提供該選項。

字典查無結果的處理方式（本通道內部的簡化重試，非 Channel 3 的 LLM
fallback）：先用「還原辭典形」（見 src/nlp/tokenizer.py，例如語幹「좋」
補回「다」變成「좋다」）查詢，查無結果再退回斷詞原始文字查一次；兩次都
查無結果則不輸出該詞的候選列（但仍計入 word_count_total，反映在
dict_hit_rate 上）。

用法：
    python scripts/run_channel1.py --video-id 001 --engine okt \\
        --ocr-results data/output/001/ocr_on/ocr_results.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schemas import ExportRecord  # noqa: E402
from src.dedup.deduplicator import deduplicate  # noqa: E402
from src.nlp.text_cleaner import clean_ocr_text  # noqa: E402
from src.nlp.tokenizer import get_tokenizer  # noqa: E402
from src.nlp.dictionary import DictionaryIndex  # noqa: E402
from src.nlp.stats import RunReportBuilder  # noqa: E402
from src.export.csv_exporter import export_csv  # noqa: E402
from src.ocr.results_io import load_ocr_results  # noqa: E402


SUPPORTED_ENGINES = ["okt", "komoran", "kkma", "mecab"]


def run(video_id: str, engine: str, ocr_results_path: str, out_dir: str, dict_db: str = None) -> None:
    if engine not in SUPPORTED_ENGINES:
        raise ValueError(f"不支援的引擎：{engine}（可用：{SUPPORTED_ENGINES}）")

    channel_name = f"channel1_{engine}"
    builder = RunReportBuilder(channel=channel_name, video_id=video_id)

    print(f"[Channel 1 / {engine}] 讀取 OCR 結果：{ocr_results_path}")
    with builder.time_module("load"):
        raw_results = load_ocr_results(ocr_results_path)
    print(f"  共 {len(raw_results)} 筆 OCR 原始辨識結果")

    empty_after_clean = 0
    with builder.time_module("clean"):
        cleaned_results = []
        for r in raw_results:
            cleaned_text = clean_ocr_text(r.text)
            if not cleaned_text:
                empty_after_clean += 1
                continue
            cleaned_results.append(r.model_copy(update={"text": cleaned_text}))
    print(f"  Regex 清理後保留 {len(cleaned_results)} 筆（{empty_after_clean} 筆清理後為空白，已略過）")

    with builder.time_module("dedup"):
        subtitles = deduplicate(cleaned_results)
    print(f"  跨影格去重後剩 {len(subtitles)} 句字幕")

    print(f"  載入斷詞引擎：{engine} ...")
    with builder.time_module("tokenizer_init"):
        tokenizer = get_tokenizer(engine)

    export_records: List[ExportRecord] = []
    with DictionaryIndex(dict_db) as dictionary:
        for subtitle in subtitles:
            with builder.time_module("tokenize"):
                tokens = tokenizer.tokenize(subtitle.text)

            for token in tokens:
                with builder.time_module("dict_lookup"):
                    candidates = dictionary.lookup(token.dictionary_form)
                    if not candidates and token.dictionary_form != token.word:
                        candidates = dictionary.lookup(token.word)

                builder.record_word(dict_hit=bool(candidates))

                for candidate in candidates:
                    note = (
                        f"引擎={engine}｜詞性={token.pos}｜"
                        f"同形詞{candidate.homonym_number}‧詞義{candidate.sense_num}｜"
                        f"字幕 {subtitle.start_time:.1f}s-{subtitle.end_time:.1f}s"
                    )
                    export_records.append(ExportRecord(
                        原文=candidate.written_form,
                        中文=candidate.translation,
                        詞性=candidate.part_of_speech,
                        例句=candidate.example,
                        備註=note,
                    ))

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    export_path = out_path / "export.csv"
    with builder.time_module("write_output"):
        export_csv(export_records, export_path)

    report = builder.build()
    stats_path = out_path.parent / "stats" / f"{channel_name}_report.csv"
    RunReportBuilder.write_csv(report, str(stats_path))

    print()
    print(f"[完成] {channel_name}")
    print(f"  總耗時: {report.total_time_sec:.2f}s")
    print(f"  處理詞彙數: {report.word_count_total}，字典命中: {report.dict_hit_count}"
          f"（命中率 {report.dict_hit_rate:.1%}）")
    print(f"  輸出候選列數: {len(export_records)}")
    print(f"  匯出 -> {export_path}")
    print(f"  執行報告 -> {stats_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 Channel 1：本地套件通道（多引擎子通道）")
    parser.add_argument("--video-id", required=True, help="影片代號（對應 data/output/<video-id>/）")
    parser.add_argument("--engine", required=True, choices=SUPPORTED_ENGINES, help="斷詞引擎")
    parser.add_argument("--ocr-results", required=True, help="Phase 3 輸出的 ocr_results.csv 路徑")
    parser.add_argument(
        "--out-dir", default=None,
        help="輸出目錄，預設 data/output/<video-id>/channel1_<engine>/",
    )
    parser.add_argument(
        "--dict-db", default=None,
        help="字典索引檔路徑，預設讀取 config/settings.py 的 DICTIONARY_CONFIG 設定",
    )
    args = parser.parse_args()

    out_dir = args.out_dir or f"data/output/{args.video_id}/channel1_{args.engine}"
    run(args.video_id, args.engine, args.ocr_results, out_dir, dict_db=args.dict_db)


if __name__ == "__main__":
    main()
