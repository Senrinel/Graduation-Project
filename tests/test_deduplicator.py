"""
測試 src/dedup/deduplicator.py（Phase 4：時序去重）。

2026-07-27：使用者本機真實測試回報「時序去重明顯缺失，擷取的字句多處
重複」，用真實資料（data/output/50f108b80fcd4b3ca8b5467cf12f7760）確認
根因：舊版 deduplicate() 只用單一 current_text 追蹤，遇到真實影格常見的
「同一時間畫面上同時有多個不同文字」（例如單字卡影片 학원／대학교／
학교／학생 同時出現、逐格輪替），就無法把同一個字跨影格合併——見
PROJECT_NOTES.md 第 18 節。這裡的測試刻意重現這個真實情境（而非只測試
單一文字流的簡單案例），確保修正後的多群組追蹤邏輯正確。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dedup.deduplicator import deduplicate  # noqa: E402
from src.schemas import OCRResult  # noqa: E402


def _r(text: str, timestamp_sec: float, confidence: float = 0.9) -> OCRResult:
    return OCRResult(
        frame_id=int(timestamp_sec * 10),
        timestamp_sec=timestamp_sec,
        text=text,
        bbox=[[0, 0], [1, 0], [1, 1], [0, 1]],
        confidence=confidence,
    )


def test_deduplicate_empty_returns_empty():
    assert deduplicate([]) == []


def test_deduplicate_merges_consecutive_same_text_within_gap():
    results = [_r("화이팅", 0.0), _r("화이팅", 1.0), _r("화이팅", 2.0)]
    merged = deduplicate(results)
    assert len(merged) == 1
    assert merged[0].text == "화이팅"
    assert merged[0].start_time == 0.0
    assert merged[0].end_time == 2.0


def test_deduplicate_splits_same_text_when_gap_exceeded():
    # DEDUP_CONFIG["max_gap_sec"] == 1.5（見 config/settings.py）；
    # 5 秒的間隔遠超過門檻，應視為兩次不同的出現，而不是同一組。
    results = [_r("학교", 0.0), _r("학교", 5.0)]
    merged = deduplicate(results)
    assert len(merged) == 2
    assert (merged[0].start_time, merged[0].end_time) == (0.0, 0.0)
    assert (merged[1].start_time, merged[1].end_time) == (5.0, 5.0)


def test_deduplicate_interleaved_simultaneous_texts_merge_correctly():
    """
    重現真實 bug 場景：同一時間點畫面上同時有 4 個不同文字（如單字卡
    影片），OCR 依序輸出這 4 筆結果，且這個順序在每一格之間保持一致。
    修正前：同一個字每一格都會被其他字「插隊」而拆成獨立一筆（真實
    資料中 학원 在 15-28 秒被拆成 43 筆）。修正後：4 個字各自應該只
    合併成 1 筆，時間範圍涵蓋整段連續出現的區間。
    """
    words = ["학원", "대학교", "학교", "학생"]
    results = []
    for t in [15.0, 16.0, 17.0, 18.0]:
        for w in words:
            results.append(_r(w, t))

    merged = deduplicate(results)

    assert len(merged) == 4  # 不是 16 筆（4 字 x 4 格）
    by_text = {s.text: s for s in merged}
    assert set(by_text.keys()) == set(words)
    for w in words:
        assert by_text[w].start_time == 15.0
        assert by_text[w].end_time == 18.0


def test_deduplicate_output_sorted_by_start_time():
    # 讓其中一組先結束（間隔超過門檻提早收尾），確保輸出仍依 start_time
    # 排序，而不是依「哪一組先被收尾」排序。
    results = [
        _r("가", 0.0),
        _r("나", 0.5),
        _r("가", 1.0),  # "가" 這組會在這裡收尾（下一筆間隔超過門檻）
        _r("나", 1.0),
        _r("가", 10.0),  # 全新一組，時間上晚於 "나" 的結束
    ]
    merged = deduplicate(results)
    start_times = [s.start_time for s in merged]
    assert start_times == sorted(start_times)


def test_deduplicate_avg_confidence_computed_correctly():
    results = [_r("집", 0.0, confidence=0.8), _r("집", 1.0, confidence=1.0)]
    merged = deduplicate(results)
    assert len(merged) == 1
    assert merged[0].avg_confidence == 0.9
