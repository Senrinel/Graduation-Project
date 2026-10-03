"""
LLM 呼叫抽象介面 (Phase 5 Channel 2 / 3 共用)
==================================================
定義 Channel 2（本地 LLM 修正/標註）與 Channel 3（LLM fallback 推測原詞）
共用的 LLM 呼叫介面。目前提供本地 Ollama 實作；未來若要改接外部 LLM API
（如 Anthropic／OpenAI），只需新增一個實作同一介面的類別，呼叫端程式碼
（`src/nlp/llm_annotator.py`、Channel 2/3 runner）完全不需要修改。

決策紀錄（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 3 節，2026-07-25 確認）：
- 推薦模型：`qwen2.5:7b`（4.7GB，官方 Ollama 庫可直接 `ollama pull`，
  已於使用者本機驗證可正確輸出韓文，見 LOCAL_TESTING.md）。
- 透過 Ollama 本地 REST API（預設 `http://localhost:11434/api/generate`）
  呼叫，`stream=False` 取得完整回應、`format="json"` 要求 Ollama 盡量
  輸出合法 JSON（實際是否為合法 JSON 仍需呼叫端自行解析驗證，見
  `llm_annotator.py`）。
"""

from __future__ import annotations

from typing import Protocol

import requests


class LLMClient(Protocol):
    """LLM 呼叫的抽象介面：傳入 prompt，回傳模型產生的原始文字回應。"""

    def generate(self, prompt: str) -> str:
        ...


class OllamaClient:
    """透過本地 Ollama REST API 呼叫模型（預設 `qwen2.5:7b`）。"""

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        timeout_sec: float = 60.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def generate(self, prompt: str) -> str:
        """
        呼叫 Ollama 的 `/api/generate` 端點。

        Args:
            prompt: 完整的提示詞文字。

        Returns:
            模型產生的原始文字回應（`response` 欄位）。

        Raises:
            requests.exceptions.RequestException: 連線失敗、逾時、或
                Ollama 回傳非 2xx 狀態碼（例如伺服器未啟動、模型未下載）。
        """
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
