"""
Step 8b：Anki 字卡匯出
========================
將 ExportRecord 列表轉換為 Anki 可匯入之 .apkg 字卡牌組。

注意事項：
- 依賴 genanki 套件；牌組與筆記型別 id 需固定（隨機產生的 id 若每次變動，
  重複匯入會被 Anki 視為不同牌組），已在 config/settings.py 中固定寫死。
"""

from __future__ import annotations
from pathlib import Path
from typing import List
import genanki

from src.schemas import ExportRecord
from config.settings import ANKI_CONFIG


def export_anki(records: List[ExportRecord], output_path: str | Path) -> Path:
    """
    將匯出紀錄轉換為 Anki 牌組並寫出 .apkg 檔案。

    Args:
        records: 待匯出的紀錄列表。
        output_path: 輸出 .apkg 檔案路徑。

    Returns:
        實際寫入的檔案路徑。
    """
    model = genanki.Model(
        ANKI_CONFIG["model_id"], "OCR Subtitle Model",
        fields=[{"name": "原文"}, {"name": "中文"}, {"name": "詞性"}, {"name": "例句"}, {"name": "備註"}],
        templates=[{
            "name": "Card 1",
            "qfmt": "{{原文}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{中文}}<br><i>{{詞性}}</i><br>{{例句}}',
        }],
    )
    deck = genanki.Deck(ANKI_CONFIG["deck_id"], ANKI_CONFIG["deck_name"])

    for r in records:
        note = genanki.Note(model=model, fields=[r.原文, r.中文, r.詞性, r.例句, r.備註])
        deck.add_note(note)

    output_path = Path(output_path)
    genanki.Package(deck).write_to_file(str(output_path))
    return output_path
