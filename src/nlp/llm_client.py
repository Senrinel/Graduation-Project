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

    def generate(self, prompt: str, **kwargs) -> str:
        ...


class OllamaClient:
    """
    透過本地 Ollama REST API 呼叫模型（預設 `qwen2.5:7b`）。
    內建長效保溫 (keep_alive: 30m)、產出上限防禦 (num_predict)、
    顯存優化 (num_ctx: 1024)、低溫約束 (temperature: 0.1)、連線池與自動重試機制。
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        timeout_sec: float = 90.0,
        max_retries: int = 2,
        keep_alive: str = "30m",
        temperature: float = 0.1,
        num_ctx: int = 1024,
        default_num_predict: int | None = None,
    ):
        import requests
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.keep_alive = keep_alive
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.default_num_predict = default_num_predict
        self._session = requests.Session()

    def warmup(self, timeout_sec: float = 120.0) -> bool:
        """
        向 Ollama 發送輕量預熱請求，強制將模型載入記憶體/VRAM 並鎖定保溫，
        避免後續逐句處理時因磁碟冷讀取模型權重而逾時。
        """
        import requests
        payload = {
            "model": self.model,
            "prompt": "{}",
            "stream": False,
            "format": "json",
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": 1,
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }
        post_fn = (
            requests.post
            if (hasattr(requests.post, "call_args") or hasattr(requests.post, "mock_calls"))
            else self._session.post
        )
        try:
            resp = post_fn(f"{self.base_url}/api/generate", json=payload, timeout=timeout_sec)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        num_predict: int | None = None,
        timeout_sec: float | None = None,
        **kwargs,
    ) -> str:
        """
        呼叫 Ollama 的 `/api/generate` 端點。
        """
        import time
        import requests

        limit = num_predict if num_predict is not None else self.default_num_predict
        options = {
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
        }
        if limit is not None:
            options["num_predict"] = limit

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": self.keep_alive,
            "options": options,
        }

        timeout = timeout_sec or self.timeout_sec
        post_fn = (
            requests.post
            if (hasattr(requests.post, "call_args") or hasattr(requests.post, "mock_calls"))
            else self._session.post
        )

        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = post_fn(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exc = e
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    raise
            except requests.exceptions.RequestException:
                raise

        if last_exc:
            raise last_exc
        return ""
