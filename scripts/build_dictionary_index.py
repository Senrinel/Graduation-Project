"""
韓中字典索引建立腳本 (Phase 5 Channel 1 / 3 共用基礎建設)
==============================================================
將 `韩中字典xml/` 底下 11 個 LMF (Lexical Markup Framework) XML 檔
（國立國語院《한국어기초사전》，約 5.6 萬筆詞條）解析後，寫入一份
SQLite 索引檔，供 `src/nlp/dictionary.py` 快速依「韓文寫法」查詢。

設計原則（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 1、13.2 節）：
- 索引只需在開發/測試階段建立一次，之後重複使用，不影響成品執行效能。
- 原始 XML 內所有欄位都以 `<feat att="..." val="..." />` 表示，本腳本一律
  用 ElementTree 直接讀取 att/val 屬性，不依賴文字節點內容。
- 「無對應中文詞彙」在原始資料中固定以字串 "(无对应词汇)" 表示（已於
  11 個檔案中實測確認為唯一寫法，見 config.settings.DICTIONARY_CONFIG
  的 no_equivalent_marker），索引建立時正規化為空字串，查詢端不需要
  再特別判斷這個特殊字串。

已知資料品質問題（實測發現，重要）：
- `LexicalEntry` 的 `att="id"` 屬性（本檔案稱為 entry_id）**並非唯一**。
  實測 11 個檔案中共發現 54 組 entry_id 被重複使用，其中最多一組
  （id=73278）被 28 個完全不同的詞條（例如「한」「한 건 하다」「한
  귀로 흘리다」等慣用語）共用同一個 id。研判是原始辭典資料把「衍生
  慣用語」跟「基礎詞」歸在同一個 id 底下所致。因此本索引**不能**用
  entry_id 當作資料庫主鍵（若用 entry_id 當主鍵、以 INSERT OR REPLACE
  處理，會讓同一 id 底下除了最後一筆以外的詞條全部被覆寫遺失）。
  解法：entries 表改用自動遞增的 entry_pk 當主鍵，entry_id 僅作為
  一般欄位保留（供追溯原始資料使用，非唯一）。

資料庫結構（4 張表，詳見各 CREATE TABLE 註解）：
    entries         一筆 LexicalEntry（同形詞候選），主鍵為 entry_pk（非原始 entry_id）
    senses          一筆 Sense（詞義候選，同一 entry 可能有多個）
    sense_examples  一筆例句（同一 Sense 可能有多筆，依 type 分類）
    equivalents     一筆多語對照翻譯（同一 Sense 可能有多國語言）

用法：
    python scripts/build_dictionary_index.py
    python scripts/build_dictionary_index.py --xml-dir 韩中字典xml --output data/dictionary_index.sqlite3
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

# 讓腳本可以直接用 `python scripts/build_dictionary_index.py` 執行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DICTIONARY_CONFIG  # noqa: E402


# 已知資料品質問題：實測發現 11 個原始 XML 檔中，有 4 個檔案總共混入 7 個
# 非法的 XML 控制字元（如 \x08 backspace，疑似原始匯出工具留下的殘留字元），
# 這些字元在 XML 1.0 規範中禁止出現在內容裡，會讓 ElementTree 直接拋出
# "not well-formed" 錯誤。解析前先用這個正則移除（tab/換行/回車例外，其餘
# 0x00-0x1F 控制字元一律移除），不影響任何有意義的韓文/中文/其他語言內容。
_ILLEGAL_XML_CHARS_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _read_sanitized_xml_text(xml_path: Path) -> str:
    with open(xml_path, encoding="utf-8") as f:
        content = f.read()
    return _ILLEGAL_XML_CHARS_RE.sub("", content)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    entry_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,     -- 原始 XML 的 LexicalEntry id，非唯一，僅供追溯
    written_form TEXT NOT NULL,
    homonym_number TEXT,
    lexical_unit TEXT,
    part_of_speech TEXT,
    vocabulary_level TEXT,
    semantic_category TEXT,
    pronunciation TEXT,
    source_file TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_written_form ON entries(written_form);
CREATE INDEX IF NOT EXISTS idx_entries_entry_id ON entries(entry_id);

CREATE TABLE IF NOT EXISTS senses (
    sense_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_pk INTEGER NOT NULL REFERENCES entries(entry_pk),
    sense_num TEXT,
    definition TEXT,
    annotation TEXT
);
CREATE INDEX IF NOT EXISTS idx_senses_entry_pk ON senses(entry_pk);

CREATE TABLE IF NOT EXISTS sense_examples (
    example_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_pk INTEGER NOT NULL REFERENCES senses(sense_pk),
    example_type TEXT,
    example_text TEXT,
    turn_order INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_examples_sense_pk ON sense_examples(sense_pk);

CREATE TABLE IF NOT EXISTS equivalents (
    equivalent_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_pk INTEGER NOT NULL REFERENCES senses(sense_pk),
    language TEXT NOT NULL,
    lemma TEXT NOT NULL,
    definition TEXT
);
CREATE INDEX IF NOT EXISTS idx_equivalents_sense_pk ON equivalents(sense_pk);
CREATE INDEX IF NOT EXISTS idx_equivalents_language ON equivalents(sense_pk, language);
"""


def _feat_map(elem: ET.Element) -> dict:
    """
    取出某個 XML 元素「直接子節點」中所有 <feat att="X" val="Y" /> 的
    att -> val 對照表（不含孫層，例如 LexicalEntry 直接下的 feat 不會
    誤抓到 Lemma / WordForm / Sense 裡面的 feat）。

    注意：若同一層有多個相同 att 的 feat（目前資料中未發現這種情況），
    後面的會覆蓋前面的；有可能重複出現的欄位（如 SenseExample 的
    "example"）另外用 findall 個別處理，不透過本函式。
    """
    result = {}
    for feat in elem.findall("feat"):
        att = feat.get("att")
        val = feat.get("val")
        if att is not None:
            result[att] = val
    return result


def iter_lexical_entries(xml_path: Path) -> Iterator[ET.Element]:
    """逐一讀取一個 LMF XML 檔內的所有 LexicalEntry 元素（已先移除非法控制字元）。"""
    sanitized_text = _read_sanitized_xml_text(xml_path)
    root = ET.fromstring(sanitized_text)
    lexicon = root.find("Lexicon")
    if lexicon is None:
        return
    yield from lexicon.findall("LexicalEntry")


def parse_entry(entry_elem: ET.Element, source_file: str, no_equivalent_marker: str) -> dict:
    """將一個 LexicalEntry 解析成可直接寫入 SQLite 的巢狀資料結構。"""
    entry_id = int(entry_elem.get("val"))
    direct_feats = _feat_map(entry_elem)

    lemma_elem = entry_elem.find("Lemma")
    written_form = _feat_map(lemma_elem).get("writtenForm", "") if lemma_elem is not None else ""

    wordform_elem = entry_elem.find("WordForm")
    pronunciation = _feat_map(wordform_elem).get("pronunciation") if wordform_elem is not None else None

    senses = []
    for sense_elem in entry_elem.findall("Sense"):
        sense_feats = _feat_map(sense_elem)

        examples = []
        for example_elem in sense_elem.findall("SenseExample"):
            example_type = None
            texts = []
            for feat in example_elem.findall("feat"):
                att, val = feat.get("att"), feat.get("val")
                if att == "type":
                    example_type = val
                elif att == "example":
                    texts.append(val)
            for turn_order, text in enumerate(texts):
                examples.append({
                    "example_type": example_type,
                    "example_text": text,
                    "turn_order": turn_order,
                })

        equivalents = []
        for equiv_elem in sense_elem.findall("Equivalent"):
            equiv_feats = _feat_map(equiv_elem)
            lemma_val = equiv_feats.get("lemma", "") or ""
            if lemma_val.strip() == no_equivalent_marker:
                lemma_val = ""  # 正規化「無對應詞彙」為空字串，查詢端不需再特判
            equivalents.append({
                "language": equiv_feats.get("language", ""),
                "lemma": lemma_val,
                "definition": equiv_feats.get("definition"),
            })

        senses.append({
            "sense_num": sense_elem.get("val"),
            "definition": sense_feats.get("definition"),
            "annotation": sense_feats.get("annotation"),
            "examples": examples,
            "equivalents": equivalents,
        })

    return {
        "entry_id": entry_id,
        "written_form": written_form,
        "homonym_number": direct_feats.get("homonym_number"),
        "lexical_unit": direct_feats.get("lexicalUnit"),
        "part_of_speech": direct_feats.get("partOfSpeech"),
        "vocabulary_level": direct_feats.get("vocabularyLevel"),
        "semantic_category": direct_feats.get("semanticCategory"),
        "pronunciation": pronunciation,
        "source_file": source_file,
        "senses": senses,
    }


def insert_entry(conn: sqlite3.Connection, entry: dict) -> None:
    # 注意：entry_id 並非唯一（見模組 docstring「已知資料品質問題」），
    # 此處一律新增一筆（entry_pk 自動遞增），不使用 INSERT OR REPLACE，
    # 避免同一 entry_id 底下的其他詞條被覆寫遺失。
    cursor = conn.execute(
        """
        INSERT INTO entries
            (entry_id, written_form, homonym_number, lexical_unit,
             part_of_speech, vocabulary_level, semantic_category,
             pronunciation, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["entry_id"], entry["written_form"], entry["homonym_number"],
            entry["lexical_unit"], entry["part_of_speech"], entry["vocabulary_level"],
            entry["semantic_category"], entry["pronunciation"], entry["source_file"],
        ),
    )
    entry_pk = cursor.lastrowid

    for sense in entry["senses"]:
        cursor = conn.execute(
            """
            INSERT INTO senses (entry_pk, sense_num, definition, annotation)
            VALUES (?, ?, ?, ?)
            """,
            (entry_pk, sense["sense_num"], sense["definition"], sense["annotation"]),
        )
        sense_pk = cursor.lastrowid

        conn.executemany(
            """
            INSERT INTO sense_examples (sense_pk, example_type, example_text, turn_order)
            VALUES (?, ?, ?, ?)
            """,
            [
                (sense_pk, ex["example_type"], ex["example_text"], ex["turn_order"])
                for ex in sense["examples"]
            ],
        )

        conn.executemany(
            """
            INSERT INTO equivalents (sense_pk, language, lemma, definition)
            VALUES (?, ?, ?, ?)
            """,
            [
                (sense_pk, eq["language"], eq["lemma"], eq["definition"])
                for eq in sense["equivalents"]
            ],
        )


def build_index(xml_dir: Path, output_db: Path, no_equivalent_marker: str) -> dict:
    """解析 xml_dir 底下所有 .xml 檔，建立（或覆寫重建）output_db 索引。"""
    xml_files = sorted(xml_dir.glob("*.xml"))
    if not xml_files:
        raise FileNotFoundError(f"在 {xml_dir} 找不到任何 .xml 字典檔")

    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()  # 重新建立，避免舊資料殘留

    conn = sqlite3.connect(output_db)
    conn.executescript(SCHEMA_SQL)

    stats = {"files": 0, "entries": 0, "senses": 0}
    t0 = time.time()

    for xml_path in xml_files:
        file_entry_count = 0
        for entry_elem in iter_lexical_entries(xml_path):
            entry = parse_entry(entry_elem, xml_path.name, no_equivalent_marker)
            insert_entry(conn, entry)
            file_entry_count += 1
            stats["senses"] += len(entry["senses"])
        conn.commit()
        stats["files"] += 1
        stats["entries"] += file_entry_count
        print(f"  [{stats['files']:2d}/{len(xml_files)}] {xml_path.name}: {file_entry_count} 筆詞條")

    conn.close()
    stats["elapsed_sec"] = time.time() - t0
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="建立韓中字典 SQLite 索引")
    parser.add_argument(
        "--xml-dir", default=DICTIONARY_CONFIG["xml_dir"],
        help="LMF XML 字典檔所在目錄（預設讀取 config/settings.py 設定）",
    )
    parser.add_argument(
        "--output", default=DICTIONARY_CONFIG["index_db_path"],
        help="輸出的 SQLite 索引檔路徑（預設讀取 config/settings.py 設定）",
    )
    args = parser.parse_args()

    xml_dir = Path(args.xml_dir)
    output_db = Path(args.output)

    print(f"讀取字典 XML：{xml_dir.resolve()}")
    print(f"輸出索引檔：{output_db.resolve()}")
    print()

    stats = build_index(xml_dir, output_db, DICTIONARY_CONFIG["no_equivalent_marker"])

    print()
    print(f"[完成] 共處理 {stats['files']} 個檔案、{stats['entries']} 筆詞條、"
          f"{stats['senses']} 筆詞義，耗時 {stats['elapsed_sec']:.2f}s")
    print(f"索引已寫入：{output_db.resolve()}")


if __name__ == "__main__":
    main()
