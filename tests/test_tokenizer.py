"""
測試 src/nlp/tokenizer.py

需要真實安裝 KoNLPy（Java 引擎）與 python-mecab-ko 才能執行，跟
scripts/check_konlpy_engines.py 的環境需求一致。若目前環境缺少任一引擎，
對應測試會用 pytest.importorskip 自動略過（例如在沒有 JDK/JPype 的機器
上執行 pytest 時，這些測試不會讓整個測試套件失敗）。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nlp.tokenizer import get_tokenizer  # noqa: E402

TEST_SENTENCE = "오늘 날씨가 정말 좋네요"


def test_unknown_engine_raises_value_error():
    with pytest.raises(ValueError, match="okt / komoran / kkma / mecab"):
        get_tokenizer("hannanum")
    with pytest.raises(ValueError):
        get_tokenizer("not-a-real-engine")


@pytest.mark.parametrize("engine", ["okt", "komoran", "kkma", "mecab"])
def test_engine_tokenizes_real_sentence(engine):
    pytest.importorskip("konlpy" if engine != "mecab" else "mecab")
    tokenizer = get_tokenizer(engine)
    tokens = tokenizer.tokenize(TEST_SENTENCE)

    assert len(tokens) > 0
    # 斷詞後重新組合（去除空白比較）應該仍包含原句大部分文字內容
    joined = "".join(t.word for t in tokens)
    assert "오늘" in joined
    assert "날씨" in joined


@pytest.mark.parametrize("engine", ["komoran", "kkma", "mecab"])
def test_predicate_stem_reconstructs_dictionary_form(engine):
    """Komoran/Kkma/Mecab-ko 都會把「좋네요」拆成語幹「좋」+ 語尾，
    語幹應該被還原成辭典形「좋다」。"""
    pytest.importorskip("konlpy" if engine != "mecab" else "mecab")
    tokenizer = get_tokenizer(engine)
    tokens = tokenizer.tokenize(TEST_SENTENCE)

    stem_tokens = [t for t in tokens if t.word == "좋"]
    assert len(stem_tokens) == 1
    assert stem_tokens[0].dictionary_form == "좋다"
