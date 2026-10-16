"""
Phase 5 Channel 2 執行入口：本地 LLM 通道
================================================
串接「OCR 原始文字 -> Regex 清理 -> 跨影格去重 -> LLM 一次完成錯字修正
＋ 詞彙拆解 ＋ 詞性／例句／翻譯標註 -> 結構化輸出」，並記錄執行報告
（RunReport）供之後跨通道比較（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 3、5 節）。

與 Channel 1 共用「Regex 清理」與「跨影格去重」兩個前處理步驟（見
PHASE5_MULTI_CHANNEL_PLAN.md 第 1 節共用元件表），差異在於 Channel 2
不做斷詞／查字典，而是把整句已清理過的字幕直接交給本地 LLM
（預設 `qwen2.5:7b`，透過 Ollama）一次處理。

需要本機已安裝並啟動 Ollama、且已 `ollama pull qwen2.5:7b`（見
LOCAL_TESTING.md「Phase 5 環境建制」C 節）。若 Ollama 未啟動或連線
失敗，本腳本會直接因例外終止（不會靜默略過，方便及早發現環境問題）。

用法：
    python scripts/run_channel2.py --video-id 001 \\
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
from src.nlp.llm_client import OllamaClient  # noqa: E402
from src.nlp.llm_annotator import annotate_subtitle  # noqa: E402
from src.nlp.stats import RunReportBuilder  # noqa: E402
from src.export.csv_exporter import export_csv  # noqa: E402
from src.ocr.results_io import load_ocr_results  # noqa: E402


def run(video_id: str, ocr_results_path: str, out_dir: str, model: str, base_url: str) -> None:
    channel_name = "channel2"
    builder = RunReportBuilder(channel=channel_name, video_id=video_id)

    print(f"[Channel 2] 讀取 OCR 結果：{ocr_results_path}")
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

    print(f"  LLM：{model} @ {base_url}")
    client = OllamaClient(model=model, base_url=base_url, default_num_predict=350)
    if hasattr(client, "warmup"):
        print(f"  正在預熱並確認 LLM 模型 ({model}) 載入狀態...", flush=True)
        w_ok = client.warmup()
        if w_ok:
            print(f"  [就緒] LLM 模型 ({model}) 已載入至記憶體/VRAM。", flush=True)
        else:
            print(f"  [提示] LLM 預熱略過或服務未響應，將於後續處理時嘗試連線。", flush=True)

    export_records: List[ExportRecord] = []
    total_subs = len(subtitles)
    for idx, subtitle in enumerate(subtitles, 1):
        if total_subs <= 20 or idx % max(1, total_subs // 10) == 0 or idx == 1 or idx == total_subs:
            print(f"  [Channel 2 進度] 正在標註字幕 {idx}/{total_subs}: {subtitle.text[:20]}...", flush=True)
        with builder.time_module("llm_call"):
            result = annotate_subtitle(client, subtitle.text)

        if result is None:
            builder.record_error()
            continue

        builder.record_llm_call()
        for w in result.words:
            # Channel 1 用「字典命中」，Channel 2 沒有字典比對這一步，
            # 這裡用「LLM 有無給出翻譯」近似同一個「有沒有得到有效結果」
            # 的概念，方便跨通道用同一個 dict_hit_rate 欄位比較。
            builder.record_word(dict_hit=bool(w.translation))
            note = (
                f"通道=channel2｜原始字幕={subtitle.text}｜"
                f"LLM修正後={result.corrected_sentence}｜"
                f"字幕 {subtitle.start_time:.1f}s-{subtitle.end_time:.1f}s"
            )
            export_records.append(ExportRecord(
                原文=w.word, 中文=w.translation, 詞性=w.pos, 例句=w.example, 備註=note,
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
    print(f"  LLM 呼叫次數: {report.llm_call_count}，解析失敗（略過）: {report.error_count}")
    print(f"  處理詞彙數: {report.word_count_total}，有翻譯: {report.dict_hit_count}"
          f"（比例 {report.dict_hit_rate:.1%}）")
    print(f"  輸出候選列數: {len(export_records)}")
    print(f"  匯出 -> {export_path}")
    print(f"  執行報告 -> {stats_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 Channel 2：本地 LLM 通道")
    parser.add_argument("--video-id", required=True, help="影片代號（對應 data/output/<video-id>/）")
    parser.add_argument("--ocr-results", required=True, help="Phase 3 輸出的 ocr_results.csv 路徑")
    parser.add_argument(
        "--out-dir", default=None,
        help="輸出目錄，預設 data/output/<video-id>/channel2/",
    )
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama 模型名稱")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama 伺服器位址")
    args = parser.parse_args()

    out_dir = args.out_dir or f"data/output/{args.video_id}/channel2"
    run(args.video_id, args.ocr_results, out_dir, args.model, args.base_url)


if __name__ == "__main__":
    main()
