"""
測試 scripts/build_dictionary_index.py

使用小型合成 XML（非真實 5.6 萬詞條檔案），涵蓋真實資料中已知的特殊情況：
- 同一 written_form 底下有多個同形詞（homonym_number 不同）
- 同一 Sense 底下有多筆例句、涵蓋不同 type（구／문장／대화）
- Equivalent 含正常中文翻譯，以及「無對應詞彙」佔位字串
- 非法 XML 控制字元（\x08），驗證讀檔時會被清理，不會讓解析失敗
- 同一個 entry_id 被兩個完全不同的 written_form 共用（真實資料已知的
  資料品質問題），驗證 entries 表不會因此遺失資料
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_dictionary_index import (  # noqa: E402
    build_index,
    parse_entry,
    _read_sanitized_xml_text,
)
import xml.etree.ElementTree as ET  # noqa: E402


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LexicalResource dtdVersion="16">
\t<Lexicon>
\t\t<feat att="language" val="kor" />
\t\t<LexicalEntry att="id" val="100">
\t\t\t<feat att="homonym_number" val="1" />
\t\t\t<feat att="partOfSpeech" val="명사" />
\t\t\t<Lemma><feat att="writtenForm" val="가" /></Lemma>
\t\t\t<WordForm><feat att="pronunciation" val="가ː" /></WordForm>
\t\t\t<feat att="vocabularyLevel" val="고급" />
\t\t\t<Sense att="id" val="1">
\t\t\t\t<feat att="definition" val="def-1" />
\t\t\t\t<SenseExample>
\t\t\t\t\t<feat att="type" val="구" />
\t\t\t\t\t<feat att="example" val="phrase-example" />
\t\t\t\t</SenseExample>
\t\t\t\t<SenseExample>
\t\t\t\t\t<feat att="type" val="문장" />
\t\t\t\t\t<feat att="example" val="sentence-example" />
\t\t\t\t</SenseExample>
\t\t\t\t<SenseExample>
\t\t\t\t\t<feat att="type" val="대화" />
\t\t\t\t\t<feat att="example" val="dialogue-turn-1" />
\t\t\t\t\t<feat att="example" val="dialogue-turn-2" />
\t\t\t\t</SenseExample>
\t\t\t\t<Equivalent>
\t\t\t\t\t<feat att="language" val="중국어" />
\t\t\t\t\t<feat att="lemma" val="中文翻譯" />
\t\t\t\t\t<feat att="definition" val="zh-def" />
\t\t\t\t</Equivalent>
\t\t\t</Sense>
\t\t</LexicalEntry>
\t\t<LexicalEntry att="id" val="100">
\t\t\t<feat att="homonym_number" val="2" />
\t\t\t<feat att="partOfSpeech" val="조사" />
\t\t\t<Lemma><feat att="writtenForm" val="가" /></Lemma>
\t\t\t<Sense att="id" val="1">
\t\t\t\t<feat att="definition" val="def-2" />
\t\t\t\t<Equivalent>
\t\t\t\t\t<feat att="language" val="중국어" />
\t\t\t\t\t<feat att="lemma" val="(无对应词汇)" />
\t\t\t\t\t<feat att="definition" val="no-equiv" />
\t\t\t\t</Equivalent>
\t\t\t</Sense>
\t\t</LexicalEntry>
\t\t<LexicalEntry att="id" val="100">
\t\t\t<feat att="homonym_number" val="1" />
\t\t\t<feat att="partOfSpeech" val="관용구" />
\t\t\t<Lemma><feat att="writtenForm" val="다른단어" /></Lemma>
\t\t\t<Sense att="id" val="1">
\t\t\t\t<feat att="definition" val="idiom-def" />
\t\t\t</Sense>
\t\t</LexicalEntry>
\t</Lexicon>
</LexicalResource>
"""

NO_EQUIVALENT_MARKER = "(无对应词汇)"


def test_sanitize_removes_illegal_control_chars(tmp_path):
    xml_path = tmp_path / "dirty.xml"
    dirty_text = SAMPLE_XML.replace("def-1", "def-1\x08tail")
    xml_path.write_text(dirty_text, encoding="utf-8")

    sanitized = _read_sanitized_xml_text(xml_path)
    assert "\x08" not in sanitized
    # 清理後應仍是合法 XML，可以正常解析
    root = ET.fromstring(sanitized)
    assert root.find("Lexicon") is not None


def test_parse_entry_extracts_all_fields():
    root = ET.fromstring(SAMPLE_XML)
    lexicon = root.find("Lexicon")
    entries = lexicon.findall("LexicalEntry")
    assert len(entries) == 3  # 同一 entry_id=100 底下有 3 筆完全不同的詞條

    parsed = [parse_entry(e, "sample.xml", NO_EQUIVALENT_MARKER) for e in entries]

    first = parsed[0]
    assert first["written_form"] == "가"
    assert first["homonym_number"] == "1"
    assert first["part_of_speech"] == "명사"
    assert first["pronunciation"] == "가ː"
    assert len(first["senses"]) == 1

    sense = first["senses"][0]
    assert sense["definition"] == "def-1"
    # 三種例句類型都應該被抓到，其中對話類型應保留兩筆（多輪對話）
    example_types = [ex["example_type"] for ex in sense["examples"]]
    assert example_types.count("구") == 1
    assert example_types.count("문장") == 1
    assert example_types.count("대화") == 2
    dialogue_texts = [ex["example_text"] for ex in sense["examples"] if ex["example_type"] == "대화"]
    assert dialogue_texts == ["dialogue-turn-1", "dialogue-turn-2"]

    zh_equiv = [eq for eq in sense["equivalents"] if eq["language"] == "중국어"]
    assert len(zh_equiv) == 1
    assert zh_equiv[0]["lemma"] == "中文翻譯"


def test_parse_entry_normalizes_no_equivalent_marker():
    root = ET.fromstring(SAMPLE_XML)
    lexicon = root.find("Lexicon")
    second_entry = lexicon.findall("LexicalEntry")[1]

    parsed = parse_entry(second_entry, "sample.xml", NO_EQUIVALENT_MARKER)
    equiv = parsed["senses"][0]["equivalents"][0]
    # 原始字串 "(无对应词汇)" 應被正規化為空字串，而不是保留原始佔位字串
    assert equiv["lemma"] == ""


def test_build_index_preserves_duplicate_entry_ids(tmp_path):
    """
    真實資料中同一個 entry_id 可能被多個完全不同的詞條共用（已於實測
    11 個檔案中發現 54 組、最多一組 28 個詞條共用同一 id）。索引必須用
    自動遞增的 entry_pk 當主鍵，不能用原始 entry_id，否則後面的詞條會
    覆寫掉前面的、造成資料遺失。
    """
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "sample.xml").write_text(SAMPLE_XML, encoding="utf-8")
    db_path = tmp_path / "index.sqlite3"

    stats = build_index(xml_dir, db_path, NO_EQUIVALENT_MARKER)
    assert stats["entries"] == 3
    assert stats["files"] == 1

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT COUNT(*) FROM entries")
    assert cur.fetchone()[0] == 3  # 3 筆全部保留，沒有因為 entry_id 相同而遺失

    cur = conn.execute("SELECT COUNT(DISTINCT entry_id) FROM entries")
    assert cur.fetchone()[0] == 1  # 但 entry_id 確實只有一個值（100）

    cur = conn.execute("SELECT written_form FROM entries ORDER BY entry_pk")
    written_forms = [row[0] for row in cur.fetchall()]
    assert written_forms == ["가", "가", "다른단어"]
    conn.close()
