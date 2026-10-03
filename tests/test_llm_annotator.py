"""
測試 src/nlp/llm_annotator.py

用 FakeLLMClient 回傳固定的字串（模擬 LLM 回應），驗證 prompt 組裝與
JSON 解析／容錯邏輯，不需要真的呼叫 Ollama。真實模型輸出品質的驗證
只能在使用者本機（已安裝 Ollama + qwen2.5:7b）進行。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nlp.llm_annotator import annotate_subtitle, PROMPT_TEMPLATE  # noqa: E402


class FakeLLMClient:
    """回傳預先設定好的固定回應，不做任何真正的推論。"""

    def __init__(self, fixed_response: str):
        self.fixed_response = fixed_response
        self.last_prompt = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.fixed_response


VALID_JSON_RESPONSE = (
    '{"corrected_sentence": "오늘 날씨가 정말 좋네요", '
    '"words": ['
    '{"word": "오늘", "pos": "명사", "translation": "今天", "example": "오늘은 날씨가 좋다."}, '
    '{"word": "날씨", "pos": "명사", "translation": "天气", "example": "날씨가 춥다."}'
    ']}'
)


def test_prompt_includes_ocr_text():
    client = FakeLLMClient(VALID_JSON_RESPONSE)
    annotate_subtitle(client, "오늘날씨가정말좋네요")
    assert "오늘날씨가정말좋네요" in client.last_prompt
    assert "corrected_sentence" in PROMPT_TEMPLATE  # prompt 範本本身有要求的 JSON 格式說明


def test_parses_valid_json_response():
    client = FakeLLMClient(VALID_JSON_RESPONSE)
    result = annotate_subtitle(client, "오늘날씨가정말좋네요")

    assert result is not None
    assert result.corrected_sentence == "오늘 날씨가 정말 좋네요"
    assert len(result.words) == 2
    assert result.words[0].word == "오늘"
    assert result.words[0].translation == "今天"


def test_parses_json_wrapped_in_markdown_code_fence():
    wrapped_response = f"```json\n{VALID_JSON_RESPONSE}\n```"
    client = FakeLLMClient(wrapped_response)
    result = annotate_subtitle(client, "오늘날씨가정말좋네요")

    assert result is not None
    assert len(result.words) == 2


def test_returns_none_on_invalid_json():
    client = FakeLLMClient("這不是 JSON，模型亂回答了")
    result = annotate_subtitle(client, "테스트")
    assert result is None


def test_returns_none_when_required_field_has_wrong_type():
    # words 應該是 list，這裡故意給錯的型別，驗證 pydantic 驗證失敗時回傳 None 而不是拋例外
    bad_response = '{"corrected_sentence": "테스트", "words": "not-a-list"}'
    client = FakeLLMClient(bad_response)
    result = annotate_subtitle(client, "테스트")
    assert result is None


def test_missing_optional_fields_default_to_empty():
    minimal_response = '{"corrected_sentence": "가", "words": [{"word": "가"}]}'
    client = FakeLLMClient(minimal_response)
    result = annotate_subtitle(client, "가")

    assert result is not None
    assert result.words[0].pos == ""
    assert result.words[0].translation == ""
    assert result.words[0].example == ""
