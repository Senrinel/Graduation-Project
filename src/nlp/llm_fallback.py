"""
LLM Fallback 推測 (Phase 5 Channel 3)
==========================================
當 Channel 3（固定使用 Mecab-ko，見 PHASE5_MULTI_CHANNEL_PLAN.md 第 8 節
「Channel 3 選型」）斷詞後的某個詞彙查無字典結果時，把該詞彙連同所在
句子的上下文交給本地 LLM，請它依上下文推測最可能對應的正確韓文辭典
詞彙；推測成功後，呼叫端會用推測結果重新查一次字典、回到原本的流程。

觸發條件（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 4 節，2026-07-25 確認）：
KoNLPy(Mecab-ko) 斷出破碎或誤判的文字片段，導致字典查無此寫法。

跟 `src/nlp/llm_annotator.py`（Channel 2 用，一次分析整句、輸出多個詞彙）
是不同的 prompt／回應格式：本模組只針對「單一查無結果的詞彙」請 LLM
推測「一個」最可能的辭典詞彙，範圍更小、更聚焦，容錯策略沿用同一套
「JSON 解析失敗就回傳 None，不中斷流程」原則。
"""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel

from src.nlp.llm_client import LLMClient


FALLBACK_PROMPT_TEMPLATE = """以下是一句韓文字幕（可能包含 OCR 辨識或斷詞造成的錯誤）：
"{sentence}"

其中斷詞後的片段「{fragment}」在韓中字典中查無這個寫法，可能是斷詞錯誤
或 OCR 辨識錯誤造成的破碎文字。

請根據上下文推測「{fragment}」最可能對應的正確韓文辭典詞彙（原形動詞／
形容詞需以「다」結尾，名詞請用基本形）。若你無法合理推測出對應詞彙，
guessed_word 請回傳空字串，不要亂猜。

請「只」回傳以下 JSON 格式，不要加入任何其他說明文字或 markdown 標記：
{{"guessed_word": "推測的辭典詞彙"}}
"""


class LLMFallbackResult(BaseModel):
    guessed_word: str = ""


_JSON_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(raw_response: str) -> str:
    match = _JSON_CODE_FENCE_RE.search(raw_response)
    return match.group(1) if match else raw_response


_FALLBACK_CACHE: dict[str, Optional[str]] = {}


def clear_fallback_cache() -> None:
    """清空 fallback 推測快取。"""
    _FALLBACK_CACHE.clear()


def guess_word(client: LLMClient, sentence: str, fragment: str) -> Optional[str]:
    """
    請 LLM 依句子上下文推測「fragment」最可能對應的正確辭典詞彙。

    內建多重防護機制：
    1. 詞彙級推測快取：相同上下文或片段直接命中快取，大幅縮減重複 LLM 呼叫。
    2. Token 產出上限 (num_predict=50)：防止小型模型無限重複生成造成逾時。
    3. 例外隔離：遭遇網路逾時或連線異常時自動降級略過，絕不崩潰管線程序。

    Args:
        client: 實作 `LLMClient` 介面的物件（例如 `OllamaClient`）。
        sentence: 該詞彙所在的完整字幕句子（提供上下文）。
        fragment: 斷詞後查無字典結果的詞彙原文。

    Returns:
        推測出的詞彙字串；猜不到、格式不符或超時異常時一律回傳 `None`。
    """
    cache_key = f"{sentence.strip()}::{fragment.strip()}"
    if cache_key in _FALLBACK_CACHE:
        return _FALLBACK_CACHE[cache_key]

    prompt = FALLBACK_PROMPT_TEMPLATE.format(sentence=sentence, fragment=fragment)
    try:
        try:
            raw_response = client.generate(prompt, num_predict=50)
        except TypeError:
            raw_response = client.generate(prompt)
    except Exception as e:
        print(f"  [提示] LLM 辭典推測超時或連線異常 (片段='{fragment}'): {e}，自動跳過此詞推測...", flush=True)
        _FALLBACK_CACHE[cache_key] = None
        return None

    json_text = _extract_json_text(raw_response)
    try:
        data = json.loads(json_text)
        result = LLMFallbackResult(**data)
        guessed = result.guessed_word.strip() or None
        _FALLBACK_CACHE[cache_key] = guessed
        return guessed
    except (json.JSONDecodeError, TypeError, ValueError):
        _FALLBACK_CACHE[cache_key] = None
        return None
