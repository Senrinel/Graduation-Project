"""
LLM 標註/修正邏輯 (Phase 5 Channel 2)
==========================================
串接 `src/nlp/llm_client.py`，將 OCR 原文（已經過 `text_cleaner` 清理與
`deduplicator` 跨影格去重）送給本地 LLM，請它一次完成「錯字修正」＋
「詞彙拆解」＋「詞性／例句／翻譯標註」，回傳結構化結果。

決策紀錄（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 3 節，2026-07-25 確認）：
- 要求 LLM 回傳 JSON（見 `PROMPT_TEMPLATE`）；本模組負責解析與容錯——
  LLM 即使被要求「只回傳 JSON」，仍可能習慣性地用 ```json ... ``` 包住
  回應，或偶爾漏欄位／格式不完全正確，這些情況都不應讓整個 Channel 2
  流程中斷，而是回傳 None 讓呼叫端記一筆 error_count、跳過該句繼續。
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from src.nlp.llm_client import LLMClient


PROMPT_TEMPLATE = """你是韓文教學助手。以下是從影片畫面用 OCR 辨識出來的韓文字幕，過程中可能產生辨識錯誤（多餘字元、缺漏字元、誤判成形似的其他字）。

請完成以下工作：
1. 推測並修正這段文字最可能的原始正確韓文句子（corrected_sentence）。
2. 將修正後的句子拆解成有意義的詞彙（虛詞／助詞可依你的判斷決定是否列出）。
3. 針對每個詞彙，提供：詞性（用韓文詞性名稱，例如 명사/동사/형용사/부사）、
   繁體中文翻譯（若無法確定翻譯可留空字串）、一句韓文例句（可以是你自己造的句子）。

OCR 原始文字：
{ocr_text}

請「只」回傳以下 JSON 格式的內容，不要加入任何其他說明文字或 markdown 標記：
{{"corrected_sentence": "修正後的句子", "words": [{{"word": "詞彙", "pos": "詞性", "translation": "中文翻譯", "example": "韓文例句"}}]}}
"""


class LLMWordAnnotation(BaseModel):
    """LLM 針對單一詞彙回傳的標註結果。"""
    word: str
    pos: str = ""
    translation: str = ""
    example: str = ""


class LLMAnnotationResult(BaseModel):
    """LLM 針對一句字幕回傳的完整標註結果。"""
    corrected_sentence: str = ""
    words: List[LLMWordAnnotation] = Field(default_factory=list)


_JSON_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(raw_response: str) -> str:
    """
    LLM 有時會把 JSON 包在 ```json ... ``` 裡（即使 prompt 已要求不要這樣做），
    先嘗試抽取 code fence 內容；抽不到就直接使用原始回應本身。
    """
    match = _JSON_CODE_FENCE_RE.search(raw_response)
    return match.group(1) if match else raw_response


def annotate_subtitle(client: LLMClient, cleaned_text: str) -> Optional[LLMAnnotationResult]:
    """
    呼叫 LLM 對一句已清理過的字幕文字進行修正與標註。

    內建防護機制：
    1. Token 產出上限 (num_predict=350)：避免小模型生成冗長廢話或迴圈。
    2. 例外隔離：連線中斷或逾時自動轉為 None 並計入 error_count，不中斷整體管線。

    Args:
        client: 實作 `LLMClient` 介面的物件（例如 `OllamaClient`）。
        cleaned_text: 已經過 `clean_ocr_text` 與跨影格去重的字幕文字。

    Returns:
        解析成功回傳 `LLMAnnotationResult`；LLM 回應不是合法 JSON、
        欄位不符或呼叫超時時回傳 `None`（呼叫端計入 error_count，跳過該句繼續）。
    """
    prompt = PROMPT_TEMPLATE.format(ocr_text=cleaned_text)
    try:
        try:
            raw_response = client.generate(prompt, num_predict=350)
        except TypeError:
            raw_response = client.generate(prompt)
    except Exception as e:
        print(f"  [警告] LLM 字幕標註超時或連線異常 (字幕='{cleaned_text}'): {e}，自動跳過該句標註...", flush=True)
        return None

    json_text = _extract_json_text(raw_response)
    try:
        data = json.loads(json_text)
        return LLMAnnotationResult(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
