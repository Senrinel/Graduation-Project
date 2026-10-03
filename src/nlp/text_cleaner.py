"""
OCR 原始文字清理 (Regex 僅保留韓文字元)
==========================================
Phase 5 三通道共用的第一道處理步驟：對 OCR 原始辨識文字做正規化清理，
移除非韓文字元雜訊（英數字、標點符號、其他語言字元等），只留下韓文
字元與空白，交給後續模組（跨影格去重、斷詞、字典查詢）處理。

決策紀錄（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 1、13.1 節，2026-07-26 確認）：
- 作用範圍：OCR 原始輸出（`OCRResult.text`），清理完才進入後續流程
  （去重、斷詞、查字典），兩者不衝突。
- 只保留韓文字元（Hangul 音節、字母區塊）與空白；空白對後續斷詞的
  詞界判斷仍有幫助，故保留（多個連續空白會收斂成一個）。標點符號、
  數字、英文字母、其他語言文字一律移除（即使可能連帶移除句子邊界，
  仍以「僅保留韓文字元」為優先）。
"""

from __future__ import annotations

import re

# Hangul 相關 Unicode 區塊：
#   AC00-D7A3   Hangul Syllables（現代韓文音節，絕大多數文字落在這裡）
#   1100-11FF   Hangul Jamo（古典/組合用字母）
#   3130-318F   Hangul Compatibility Jamo（相容字母）
#   A960-A97F   Hangul Jamo Extended-A
#   D7B0-D7FF   Hangul Jamo Extended-B
_NON_HANGUL_OR_SPACE_RE = re.compile(
    "[^ᄀ-ᇿ㄰-㆏가-힣ꥠ-꥿ힰ-퟿\\s]"
)
_WHITESPACE_RE = re.compile(r"\s+")


def clean_ocr_text(raw_text: str) -> str:
    """
    清理 OCR 原始辨識文字：只保留韓文字元與空白，其餘字元移除，
    並將連續空白收斂成單一空白、去除前後空白。

    Args:
        raw_text: OCR 原始辨識文字（`OCRResult.text`）。

    Returns:
        清理後的文字；輸入為空字串或全為非韓文字元時，回傳空字串。
    """
    if not raw_text:
        return ""
    hangul_and_space_only = _NON_HANGUL_OR_SPACE_RE.sub("", raw_text)
    return _WHITESPACE_RE.sub(" ", hangul_and_space_only).strip()
