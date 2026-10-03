"""
Pipeline 總覽 (Orchestrator)
=============================
串接 Step 1-6, 8 全流程。每個 Step 皆為獨立可測試模組，
本檔案僅負責「呼叫順序」，不包含任何演算法邏輯。

    影片檔案
      -> video_io.load_video            (Step 1)
      -> frame_sampler.sample_frames    (Step 2)
      -> preprocessing.preprocess       (Step 3)  [每影格]
      -> ocr.recognize                  (Step 4)  [每影格]
      -> dedup.deduplicate              (Step 5)  [全體結果]
      -> nlp.analyzer.analyze           (Step 6)  [每筆去重後字幕]
      -> export.csv_exporter/anki_exporter (Step 8) [使用者選定後]
"""

from __future__ import annotations
from pathlib import Path
from typing import List

from src.video_io.loader import load_video
from src.frame_sampler.sampler import sample_frames
from src.preprocessing.pipeline import preprocess
from src.ocr.recognizer import recognize
from src.dedup.deduplicator import deduplicate
from src.nlp.analyzer import analyze
from src.schemas import OCRResult, SemanticResult
from config.settings import SAMPLING


def run_pipeline(video_path: str | Path) -> List[SemanticResult]:
    """
    執行完整 pipeline（不含匯出，Step 8 由呼叫端依需求另行呼叫 export 模組）。

    Args:
        video_path: 本地影片檔案路徑。

    Returns:
        list[SemanticResult]: 完整語意解析結果列表，可供前端渲染或匯出。
    """
    cap, meta = load_video(video_path)

    all_ocr_results: List[OCRResult] = []
    for frame in sample_frames(cap, meta.fps, sample_rate=SAMPLING["rate_fps"]):
        pframe = preprocess(frame)
        all_ocr_results.extend(recognize(pframe))

    subtitles = deduplicate(all_ocr_results)
    return [analyze(s) for s in subtitles]
