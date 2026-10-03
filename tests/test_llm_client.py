"""
測試 src/nlp/llm_client.py（OllamaClient）

用 unittest.mock 模擬 `requests.post`，驗證請求組裝與回應解析邏輯是否
正確，不需要真的啟動 Ollama 伺服器。真實連線行為（伺服器未啟動、模型
未下載等）只能在使用者本機（已安裝 Ollama + qwen2.5:7b）驗證。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nlp.llm_client import OllamaClient  # noqa: E402


def test_generate_sends_expected_request_payload():
    client = OllamaClient(model="qwen2.5:7b", base_url="http://localhost:11434")

    fake_response = MagicMock()
    fake_response.json.return_value = {"response": "안녕하세요"}
    fake_response.raise_for_status.return_value = None

    with patch("src.nlp.llm_client.requests.post", return_value=fake_response) as mock_post:
        result = client.generate("테스트 prompt")

    assert result == "안녕하세요"
    mock_post.assert_called_once()
    call_args, call_kwargs = mock_post.call_args
    assert call_args[0] == "http://localhost:11434/api/generate"
    assert call_kwargs["json"]["model"] == "qwen2.5:7b"
    assert call_kwargs["json"]["prompt"] == "테스트 prompt"
    assert call_kwargs["json"]["stream"] is False


def test_base_url_trailing_slash_is_normalized():
    client = OllamaClient(base_url="http://localhost:11434/")

    fake_response = MagicMock()
    fake_response.json.return_value = {"response": "ok"}
    fake_response.raise_for_status.return_value = None

    with patch("src.nlp.llm_client.requests.post", return_value=fake_response) as mock_post:
        client.generate("x")

    call_args, _ = mock_post.call_args
    assert call_args[0] == "http://localhost:11434/api/generate"


def test_missing_response_field_returns_empty_string():
    client = OllamaClient()
    fake_response = MagicMock()
    fake_response.json.return_value = {}  # 沒有 "response" 欄位
    fake_response.raise_for_status.return_value = None

    with patch("src.nlp.llm_client.requests.post", return_value=fake_response):
        result = client.generate("x")

    assert result == ""


def test_http_error_propagates():
    import requests

    client = OllamaClient()
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 error")

    with patch("src.nlp.llm_client.requests.post", return_value=fake_response):
        try:
            client.generate("x")
            assert False, "應該要拋出 HTTPError"
        except requests.exceptions.HTTPError:
            pass
