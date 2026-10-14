"""
Phase 5 Channel 3 執行入口：混合通道（Channel 1 架構 + LLM Fallback）
========================================================================
以 Channel 1 的架構為基礎，**固定使用 Mecab-ko**（速度最快的引擎，見
PHASE5_MULTI_CHANNEL_PLAN.md 第 8 節「Channel 3 選型」，2026-07-25 確認），
流程為：OCR 原文 -> Regex 清理 -> 跨影格去重 -> Mecab-ko 斷詞 -> 字典查詢
-> **查無結果時，交給本地 LLM 依上下文推測正確辭典詞彙** -> 猜到就用
推測結果重新查一次字典、回到原流程；猜不到就跳過該詞（記一筆
`llm_fallback_fail`）-> 結構化輸出。

跟 Channel 1 的差異：Channel 1 查無結果只會退回「斷詞原始文字」再查一次
（見 `run_channel1.py`），純本地、不呼叫 LLM；Channel 3 在「兩次本地查詢
都失敗」後才會呼叫 LLM 做語意層級的推測，是本通道存在的核心價值。

需要本機已安裝並啟動 Ollama、且已 `ollama pull qwen2.5:7b`（同 Channel 2，
見 LOCAL_TESTING.md「Phase 5 環境建制」C 節）。

用法：
    python scripts/run_channel3.py --video-id 001 \\
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
from src.nlp.llm_client import OllamaClient  # noqa: E402
from src.nlp.llm_fallback import guess_word  # noqa: E402
from src.nlp.stats import RunReportBuilder  # noqa: E402
from src.export.csv_exporter import export_csv  # noqa: E402
from src.ocr.results_io import load_ocr_results  # noqa: E402


CHANNEL_NAME = "channel3"
ENGINE_NAME = "mecab"  # Channel 3 固定使用最快的引擎，不像 Channel 1 有 --engine 參數


def run(
    video_id: str,
    ocr_results_path: str,
    out_dir: str,
    dict_db: str = None,
    model: str = "qwen2.5:7b",
    base_url: str = "http://localhost:11434",
    llm_client=None,
) -> None:
    """
    Args:
        llm_client: 可選，注入自訂的 LLM client（需實作 `generate(prompt) -> str`）。
            預設為 None 時會建立真正的 `OllamaClient`；測試時可傳入假的
            client，不需要真正啟動 Ollama 伺服器。
    """
    builder = RunReportBuilder(channel=CHANNEL_NAME, video_id=video_id)

    print(f"[Channel 3] 讀取 OCR 結果：{ocr_results_path}")
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

    print(f"  載入斷詞引擎：{ENGINE_NAME}（Channel 3 預設選型）...")
    with builder.time_module("tokenizer_init"):
        try:
            tokenizer = get_tokenizer(ENGINE_NAME)
        except (RuntimeError, ValueError, ImportError) as e:
            print(f"  [提示] 引擎 {ENGINE_NAME} 不可用（{e}），Channel 3 自動平穩切換至最佳推薦引擎 Komoran...")
            tokenizer = get_tokenizer("komoran")

    client = llm_client if llm_client is not None else OllamaClient(model=model, base_url=base_url)

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

                used_fallback = False
                if not candidates:
                    used_fallback = True
                    with builder.time_module("llm_fallback"):
                        guessed = guess_word(client, subtitle.text, token.word)

                    if guessed:
                        with builder.time_module("dict_lookup"):
                            candidates = dictionary.lookup(guessed)
                        builder.record_llm_call(fallback_success=bool(candidates))
                    else:
                        builder.record_llm_call(fallback_success=False)

                builder.record_word(dict_hit=bool(candidates))

                for candidate in candidates:
                    note = (
                        f"通道=channel3｜引擎={ENGINE_NAME}｜詞性={token.pos}｜"
                        + ("LLM fallback 命中｜" if used_fallback else "")
                        + f"同形詞{candidate.homonym_number}‧詞義{candidate.sense_num}｜"
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
    stats_path = out_path.parent / "stats" / f"{CHANNEL_NAME}_report.csv"
    RunReportBuilder.write_csv(report, str(stats_path))

    print()
    print(f"[完成] {CHANNEL_NAME}")
    print(f"  總耗時: {report.total_time_sec:.2f}s")
    print(f"  處理詞彙數: {report.word_count_total}，字典命中: {report.dict_hit_count}"
          f"（命中率 {report.dict_hit_rate:.1%}）")
    print(f"  LLM fallback 呼叫次數: {report.llm_call_count}"
          f"（成功挽回 {report.llm_fallback_success_count}，仍失敗 {report.llm_fallback_fail_count}）")
    print(f"  輸出候選列數: {len(export_records)}")
    print(f"  匯出 -> {export_path}")
    print(f"  執行報告 -> {stats_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 Channel 3：混合通道（Channel 1 + LLM Fallback）")
    parser.add_argument("--video-id", required=True, help="影片代號（對應 data/output/<video-id>/）")
    parser.add_argument("--ocr-results", required=True, help="Phase 3 輸出的 ocr_results.csv 路徑")
    parser.add_argument(
        "--out-dir", default=None,
        help="輸出目錄，預設 data/output/<video-id>/channel3/",
    )
    parser.add_argument(
        "--dict-db", default=None,
        help="字典索引檔路徑，預設讀取 config/settings.py 的 DICTIONARY_CONFIG 設定",
    )
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama 模型名稱")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama 伺服器位址")
    args = parser.parse_args()

    out_dir = args.out_dir or f"data/output/{args.video_id}/channel3"
    run(args.video_id, args.ocr_results, out_dir, dict_db=args.dict_db, model=args.model, base_url=args.base_url)


if __name__ == "__main__":
    main()
