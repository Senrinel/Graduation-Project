"""
測試 src/nlp/dictionary.py（DictionaryIndex 查詢介面）

用 scripts/build_dictionary_index.py 對一份小型合成 XML 建立臨時索引，
再透過 DictionaryIndex 驗證查詢行為，不依賴真實的 5.6 萬詞條字典檔
（真實資料的完整驗證見使用者本機執行紀錄，PHASE5_MULTI_CHANNEL_PLAN.md）。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_dictionary_index import build_index  # noqa: E402
from src.nlp.dictionary import DictionaryIndex  # noqa: E402
from tests.test_build_dictionary_index import SAMPLE_XML, NO_EQUIVALENT_MARKER  # noqa: E402


@pytest.fixture()
def sample_index_path(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "sample.xml").write_text(SAMPLE_XML, encoding="utf-8")
    db_path = tmp_path / "index.sqlite3"
    build_index(xml_dir, db_path, NO_EQUIVALENT_MARKER)
    return db_path


def test_lookup_returns_all_homonym_candidates(sample_index_path):
    with DictionaryIndex(str(sample_index_path)) as dictionary:
        candidates = dictionary.lookup("가")

    # SAMPLE_XML 裡「가」有兩個同形詞（homonym_number 1 和 2），各一個詞義
    assert len(candidates) == 2
    homonym_numbers = sorted(c.homonym_number for c in candidates)
    assert homonym_numbers == ["1", "2"]


def test_lookup_prefers_sentence_example_over_phrase(sample_index_path):
    with DictionaryIndex(str(sample_index_path)) as dictionary:
        candidates = dictionary.lookup("가")

    noun_candidate = next(c for c in candidates if c.homonym_number == "1")
    # 該詞義同時有 구/문장/대화 三種例句，依 example_type_priority
    # （문장 > 구 > 대화）應該選到完整句子，而不是詞組或對話
    assert noun_candidate.example == "sentence-example"


def test_lookup_blank_translation_when_no_equivalent(sample_index_path):
    with DictionaryIndex(str(sample_index_path)) as dictionary:
        candidates = dictionary.lookup("가")

    particle_candidate = next(c for c in candidates if c.homonym_number == "2")
    # 原始資料是 "(无对应词汇)" 佔位字串，查詢結果應該是空字串，不是原始佔位文字
    assert particle_candidate.translation == ""

    noun_candidate = next(c for c in candidates if c.homonym_number == "1")
    assert noun_candidate.translation == "中文翻譯"


def test_lookup_unknown_word_returns_empty_list(sample_index_path):
    with DictionaryIndex(str(sample_index_path)) as dictionary:
        candidates = dictionary.lookup("這個詞不存在於字典中")

    assert candidates == []


def test_missing_index_file_raises_clear_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.sqlite3"
    with pytest.raises(FileNotFoundError, match="build_dictionary_index.py"):
        DictionaryIndex(str(missing_path))
