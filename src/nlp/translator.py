"""
Step 6a：全句翻譯 (Sentence Translation)
==========================================
翻譯引擎待 Phase 5 決定（線上 API vs 本地模型），此處僅定義標準介面，
確保未來替換引擎時，上層呼叫端完全不受影響。

候選方案：
1. 線上 API（如 Google Translate / DeepL）：品質穩定，但需網路、有用量成本、
   使用者影片內容會傳送至第三方，需留意隱私。
2. 本地翻譯模型（如 MarianMT / NLLB）：離線可用、無隱私疑慮，但需下載模型、
   翻譯品質可能較弱、推論速度較慢（尤其 CPU）。
"""

from __future__ import annotations


def translate(text: str, source_lang: str = "ko", target_lang: str = "zh-TW") -> str:
    """
    將原文翻譯為目標語言。

    Args:
        text: 原文（韓文句子）。
        source_lang: 來源語言代碼。
        target_lang: 目標語言代碼。

    Returns:
        翻譯後文字。
    """
    raise NotImplementedError("翻譯引擎待 Phase 5 選定後實作")
