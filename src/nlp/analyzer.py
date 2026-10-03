"""
Step 6：多語意解析 (Semantic Analysis) — 整合層
==================================================
串接 translator 與 segmenter，將單一 DedupedSubtitle 轉換為完整 SemanticResult。
"""

from __future__ import annotations
from src.schemas import DedupedSubtitle, SemanticResult
from src.nlp.translator import translate
from src.nlp.segmenter import segment


def analyze(subtitle: DedupedSubtitle) -> SemanticResult:
    """
    對單一去重後字幕執行完整語意解析（翻譯 + 斷詞 + 釋義）。

    Args:
        subtitle: 去重後的字幕片段。

    Returns:
        SemanticResult: 完整語意解析結果。
    """
    translation = translate(subtitle.text)
    tokens = segment(subtitle.text)
    return SemanticResult(
        original_text=subtitle.text,
        translation=translation,
        tokens=tokens,
        start_time=subtitle.start_time,
        end_time=subtitle.end_time,
    )
