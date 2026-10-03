"""測試 src/nlp/llm_fallback.py（Channel 3 的 LLM fallback 推測邏輯）"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nlp.llm_fallback import guess_word  # noqa: E402


class FakeLLMClient:
    def __init__(self, fixed_response: str):
        self.fixed_response = fixed_response
        self.last_prompt = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.fixed_response


def test_prompt_includes_sentence_and_fragment():
    client = FakeLLMClient('{"guessed_word": "좋다"}')
    guess_word(client, "오늘 날씨가 정말 좋", "좋")
    assert "오늘 날씨가 정말 좋" in client.last_prompt
    assert "좋" in client.last_prompt


def test_returns_guessed_word_on_success():
    client = FakeLLMClient('{"guessed_word": "좋다"}')
    result = guess_word(client, "오늘 날씨가 정말 좋", "좋")
    assert result == "좋다"


def test_returns_none_when_llm_explicitly_gives_up():
    client = FakeLLMClient('{"guessed_word": ""}')
    result = guess_word(client, "asdf 잘 안 보임", "asdf")
    assert result is None


def test_returns_none_on_invalid_json():
    client = FakeLLMClient("모델이 이상한 답을 했어요")
    result = guess_word(client, "테스트 문장", "테스트")
    assert result is None


def test_handles_markdown_code_fence_wrapped_response():
    client = FakeLLMClient('```json\n{"guessed_word": "학교"}\n```')
    result = guess_word(client, "학교에 갔다", "학교")
    assert result == "학교"
