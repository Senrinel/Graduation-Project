"""測試 src/nlp/text_cleaner.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.nlp.text_cleaner import clean_ocr_text  # noqa: E402


def test_removes_digits_and_latin_letters():
    assert clean_ocr_text("안녕하세요 123 Hello!") == "안녕하세요"


def test_removes_punctuation():
    assert clean_ocr_text("오늘 날씨가 정말 좋네요.") == "오늘 날씨가 정말 좋네요"
    assert clean_ocr_text("...!!!???") == ""


def test_removes_other_scripts():
    assert clean_ocr_text("こんにちは 안녕 world") == "안녕"


def test_collapses_and_strips_whitespace():
    assert clean_ocr_text("  가   나   다  ") == "가 나 다"


def test_empty_and_none_like_input():
    assert clean_ocr_text("") == ""


def test_pure_korean_text_unchanged_besides_whitespace():
    assert clean_ocr_text("오늘 날씨가 정말 좋네요") == "오늘 날씨가 정말 좋네요"


def test_keeps_hangul_jamo_and_compatibility_blocks():
    # 相容字母區塊（例如注音式輸入殘留的字母）與古典字母也應保留，不被當成雜訊移除
    jamo_text = "ㄱㄴ"  # ㄱㄴ (Hangul Compatibility Jamo)
    assert clean_ocr_text(jamo_text) == jamo_text
