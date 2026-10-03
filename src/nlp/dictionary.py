"""
韓中字典查詢模組 (Phase 5 Channel 1 / 3 共用)
==============================================
讀取 `scripts/build_dictionary_index.py` 建立好的 SQLite 索引，依「韓文
寫法」查詢所有同形詞／多義詞候選。一個詞義（Sense）對應一筆
`DictionaryCandidate`，供 Channel 1／3 組成結構化輸出（`ExportRecord`）。

決策紀錄（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 1、13.1 節）：
- 同形詞／多義詞全部列出，不篩選單一「最佳」候選。
- 查無中文對應詞彙時，`translation` 回傳空字串（原始資料中以固定字串
  "(无对应词汇)" 表示，已於索引建立階段正規化為空字串，本模組不需要
  再處理該特殊字串）。
- 例句沒有中文對照，一律回傳韓文原句；同一詞義可能有多筆例句，依
  `config.settings.DICTIONARY_CONFIG["example_type_priority"]` 的順序
  （預設：完整句子「문장」> 詞組「구」> 對話「대화」）挑選一句代表性
  例句；這是工程上的合理預設，非使用者明確規定，若需要改變優先序或
  改成回傳全部例句，只需調整設定或本模組即可。

用法：
    from src.nlp.dictionary import DictionaryIndex

    with DictionaryIndex() as dictionary:
        candidates = dictionary.lookup("가")
        for c in candidates:
            print(c.part_of_speech, c.definition, c.translation)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import DICTIONARY_CONFIG
from src.schemas import DictionaryCandidate


class DictionaryIndex:
    """
    包住 SQLite 連線的字典查詢器。

    建議整個 channel 執行期間重複使用同一個實例（例如用 `with` 包住整段
    處理流程），避免每次查詞都重新開檔案；`close()` 或離開 `with` 區塊時
    才關閉連線。
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or DICTIONARY_CONFIG["index_db_path"])
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"字典索引不存在：{self.db_path}\n"
                "請先執行 `python scripts/build_dictionary_index.py` 建立索引"
                "（一次性建置，見 PHASE5_MULTI_CHANNEL_PLAN.md 第 1 節）。"
            )
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._target_language: str = DICTIONARY_CONFIG["target_language"]
        self._example_priority: List[str] = DICTIONARY_CONFIG["example_type_priority"]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DictionaryIndex":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def lookup(self, written_form: str) -> List[DictionaryCandidate]:
        """
        依韓文寫法查詢所有同形詞／多義詞候選。

        Args:
            written_form: 欲查詢的韓文寫法（例如斷詞後的詞彙原形）。

        Returns:
            候選詞義列表；查無此寫法時回傳空 list（呼叫端可依此判斷
            字典未命中，Channel 3 會依此觸發 LLM fallback）。
        """
        entry_rows = self._conn.execute(
            """
            SELECT entry_pk, homonym_number, part_of_speech
            FROM entries WHERE written_form = ?
            ORDER BY entry_pk
            """,
            (written_form,),
        ).fetchall()
        if not entry_rows:
            return []

        candidates: List[DictionaryCandidate] = []
        for entry_row in entry_rows:
            sense_rows = self._conn.execute(
                """
                SELECT sense_pk, sense_num, definition
                FROM senses WHERE entry_pk = ?
                ORDER BY sense_pk
                """,
                (entry_row["entry_pk"],),
            ).fetchall()
            for sense_row in sense_rows:
                candidates.append(
                    DictionaryCandidate(
                        written_form=written_form,
                        part_of_speech=entry_row["part_of_speech"] or "",
                        homonym_number=entry_row["homonym_number"] or "",
                        sense_num=sense_row["sense_num"] or "",
                        definition=sense_row["definition"] or "",
                        example=self._pick_example(sense_row["sense_pk"]),
                        translation=self._pick_translation(sense_row["sense_pk"]),
                    )
                )
        return candidates

    def _pick_example(self, sense_pk: int) -> str:
        """依 example_type_priority 挑一句代表性韓文例句；找不到偏好類型則退回第一筆。"""
        rows = self._conn.execute(
            """
            SELECT example_type, example_text
            FROM sense_examples WHERE sense_pk = ?
            ORDER BY turn_order
            """,
            (sense_pk,),
        ).fetchall()
        if not rows:
            return ""

        by_type: Dict[Optional[str], str] = {}
        for row in rows:
            by_type.setdefault(row["example_type"], row["example_text"])

        for preferred_type in self._example_priority:
            if preferred_type in by_type:
                return by_type[preferred_type]
        return rows[0]["example_text"]

    def _pick_translation(self, sense_pk: int) -> str:
        """取該詞義在目標語言（預設中文）的翻譯；查無對應則回傳空字串。"""
        row = self._conn.execute(
            """
            SELECT lemma FROM equivalents
            WHERE sense_pk = ? AND language = ?
            LIMIT 1
            """,
            (sense_pk, self._target_language),
        ).fetchone()
        return row["lemma"] if row else ""
