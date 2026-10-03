"""
Step 5：時序去重與過濾 (Temporal Deduplication)
=================================================
將連續影格中重複出現的相同字幕合併為單一 DedupedSubtitle 紀錄。

注意事項：
- 目前採「完全相同字串」比對；OCR 雜訊可能使同一句字幕在不同影格
  辨識出些微差異文字，未來可改用文字相似度（如 Levenshtein）做模糊比對。
- 合併門檻（多久算「同一句」）需可設定，避免快速切換的字幕被誤合併。

2026-07-27 修正（見 PROJECT_NOTES.md 第 18 節，使用者本機真實測試發現）：
------------------------------------------------------------------------
舊版實作只用單一個 `current_text` 變數追蹤「目前正在進行中的一組」，
一次只能合併一種文字。但真實影格（例如單字卡影片）常常同時有多個文字
同時出現在畫面上（例如 학원／대학교／학교／학생 四個字同時在畫面上，
每一格 OCR 依序輸出這四筆結果），使得同一個字在結果序列中被其他同時
出現的字「插隊」。舊版只要文字一換就會把目前這組收尾，之後同一個字
再度出現時，`current_text` 已經是別的字了，於是被誤判成「新的一組」，
導致同一個字在真實資料中被拆成幾十筆零長度的重複項目（已用真實資料
`data/output/50f108b80fcd4b3ca8b5467cf12f7760` 驗證，學원 一字在
15-28 秒內被拆成 43 筆）。

修正方式（已與使用者確認，分組鍵採「只用文字比對」）：改成同時追蹤
「多個進行中的群組」，每個群組以文字內容為鍵；只有同一個字之間的時間
間隔超過 `max_gap_sec` 才收尾、視為不同次出現。`max_gap_sec` 數值本身
維持 1.5 秒不變（使用者確認，見 PROJECT_NOTES.md 第 18 節）。
"""

from __future__ import annotations
from typing import Dict, List

from src.schemas import OCRResult, DedupedSubtitle
from config.settings import DEDUP_CONFIG


class _OpenGroup:
    __slots__ = ("text", "start_time", "last_time", "confidences")

    def __init__(self, text: str, timestamp_sec: float, confidence: float) -> None:
        self.text = text
        self.start_time = timestamp_sec
        self.last_time = timestamp_sec
        self.confidences: List[float] = [confidence]

    def finalize(self) -> DedupedSubtitle:
        return DedupedSubtitle(
            text=self.text,
            start_time=self.start_time,
            end_time=self.last_time,
            avg_confidence=sum(self.confidences) / len(self.confidences),
        )


def deduplicate(results: List[OCRResult]) -> List[DedupedSubtitle]:
    """
    將依時間排序的 OCRResult 序列去重合併。

    同一時間點畫面上可能同時存在多個不同文字（例如單字卡影片一次顯示
    多個單字），因此改為同時追蹤多個「進行中」群組（分組鍵＝文字內容），
    而非只追蹤單一個當前群組——見上方模組說明的 2026-07-27 修正紀錄。

    Args:
        results: 依 timestamp_sec 遞增排序的 OCR 結果列表。

    Returns:
        list[DedupedSubtitle]: 合併後的字幕片段列表，依 start_time 排序。
    """
    if not results:
        return []

    gap_tolerance = DEDUP_CONFIG["max_gap_sec"]

    open_groups: Dict[str, _OpenGroup] = {}
    finalized: List[DedupedSubtitle] = []

    for r in results:
        text = r.text.strip()
        group = open_groups.get(text)

        if group is not None and (r.timestamp_sec - group.last_time) <= gap_tolerance:
            group.last_time = r.timestamp_sec
            group.confidences.append(r.confidence)
            continue

        # 沒有進行中的同文字群組，或間隔超過門檻——先把舊群組收尾（若存在），
        # 再以這筆結果開啟一組新的。
        if group is not None:
            finalized.append(group.finalize())
        open_groups[text] = _OpenGroup(text, r.timestamp_sec, r.confidence)

    # 收尾所有還在進行中、序列結束時仍未關閉的群組。
    for group in open_groups.values():
        finalized.append(group.finalize())

    finalized.sort(key=lambda s: s.start_time)
    return finalized
