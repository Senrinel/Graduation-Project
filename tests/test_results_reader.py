"""測試 src/api/results_reader.py（讀取 Channel export.csv / stats csv 轉成 API JSON）。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.results_reader import (  # noqa: E402
    ChannelResultsNotFound,
    export_csv_path,
    list_available_channels,
    read_channel_results,
    resolve_frame_path,
)


def _write_export_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _write_stats_csv(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    pd.DataFrame([row]).to_csv(path, index=False, encoding="utf-8")


def test_read_channel_results_happy_path(tmp_path):
    root = tmp_path / "output"
    _write_export_csv(
        root / "001" / "channel3" / "export.csv",
        [{"原文": "집", "中文": "家", "詞性": "명사", "例句": "집에 가다", "備註": "note1"}],
    )
    _write_stats_csv(
        root / "001" / "stats" / "channel3_report.csv",
        {"channel": "channel3", "video_id": "001", "word_count_total": 10, "dict_hit_count": 8, "dict_hit_rate": 0.8},
    )

    result = read_channel_results(root, "001", "channel3")
    assert result["video_id"] == "001"
    assert result["channel"] == "channel3"
    assert result["record_count"] == 1
    assert result["records"][0]["原文"] == "집"
    assert result["stats"]["dict_hit_count"] == 8


def test_read_channel_results_missing_export_raises(tmp_path):
    root = tmp_path / "output"
    with pytest.raises(ChannelResultsNotFound):
        read_channel_results(root, "999", "channel3")


def test_read_channel_results_invalid_channel_raises_value_error(tmp_path):
    root = tmp_path / "output"
    with pytest.raises(ValueError):
        export_csv_path(root, "001", "channel99_not_real")


def test_read_channel_results_without_stats_file_returns_none_stats(tmp_path):
    root = tmp_path / "output"
    _write_export_csv(
        root / "001" / "channel2" / "export.csv",
        [{"原文": "학교", "中文": "学校", "詞性": "명사", "例句": "", "備註": ""}],
    )
    result = read_channel_results(root, "001", "channel2")
    assert result["stats"] is None
    # 空字串欄位應該讀成 ""，不是 NaN
    assert result["records"][0]["例句"] == ""


def test_list_available_channels_only_lists_existing(tmp_path):
    root = tmp_path / "output"
    _write_export_csv(root / "001" / "channel1_mecab" / "export.csv", [{"原文": "a", "中文": "b", "詞性": "c", "例句": "", "備註": ""}])
    _write_export_csv(root / "001" / "channel3" / "export.csv", [{"原文": "a", "中文": "b", "詞性": "c", "例句": "", "備註": ""}])

    available = list_available_channels(root, "001")
    assert set(available) == {"channel1_mecab", "channel3"}


def test_list_available_channels_empty_for_unknown_video(tmp_path):
    root = tmp_path / "output"
    assert list_available_channels(root, "nonexistent") == []


# ----------------------------------------------------------------------
# Phase 7：結構化時間戳記解析（見 PROJECT_NOTES.md 第 16 節）。這裡用真實
# 三個 channel runner 實際會寫出的 備註 格式（見 scripts/run_channel1.py /
# run_channel2.py / run_channel3.py），確保正規表達式跟真實資料吻合，
# 不是憑空捏造格式再驗證自己寫的正規表達式。
# ----------------------------------------------------------------------

def test_read_channel_results_parses_timestamp_from_channel1_note_format(tmp_path):
    root = tmp_path / "output"
    _write_export_csv(
        root / "001" / "channel1_mecab" / "export.csv",
        [{"原文": "학원", "中文": "学院，学校", "詞性": "명사", "例句": "...",
          "備註": "引擎=mecab｜詞性=NNG｜同形詞0‧詞義1｜字幕 15.0s-15.0s"}],
    )
    result = read_channel_results(root, "001", "channel1_mecab")
    record = result["records"][0]
    assert record["timestamp_start"] == 15.0
    assert record["timestamp_end"] == 15.0


def test_read_channel_results_parses_timestamp_from_channel3_note_format(tmp_path):
    root = tmp_path / "output"
    _write_export_csv(
        root / "001" / "channel3" / "export.csv",
        [{"原文": "집", "中文": "家", "詞性": "명사", "例句": "...",
          "備註": "通道=channel3｜引擎=mecab｜詞性=NNG｜LLM fallback 命中｜同形詞0‧詞義1｜字幕 42.5s-44.0s"}],
    )
    result = read_channel_results(root, "001", "channel3")
    record = result["records"][0]
    assert record["timestamp_start"] == 42.5
    assert record["timestamp_end"] == 44.0


def test_read_channel_results_unparseable_note_returns_none_timestamps(tmp_path):
    root = tmp_path / "output"
    _write_export_csv(
        root / "001" / "channel2" / "export.csv",
        [{"原文": "학교", "中文": "学校", "詞性": "명사", "例句": "", "備註": "沒有時間戳記格式的文字"}],
    )
    result = read_channel_results(root, "001", "channel2")
    record = result["records"][0]
    assert record["timestamp_start"] is None
    assert record["timestamp_end"] is None


# ----------------------------------------------------------------------
# Phase 7：resolve_frame_path()（供 GET /api/jobs/{id}/frame 使用）
# ----------------------------------------------------------------------

def _write_frame_manifest(root: Path, video_id: str, rows: list[dict]) -> None:
    frames_dir = root / video_id / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    with open(frames_dir / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=["frame_id", "timestamp_sec", "filename"])
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        (frames_dir / row["filename"]).write_bytes(b"FAKEJPEGBYTES")


def test_resolve_frame_path_picks_nearest_timestamp(tmp_path):
    root = tmp_path / "output"
    _write_frame_manifest(root, "001", [
        {"frame_id": 0, "timestamp_sec": 0.0, "filename": "frame_000000.jpg"},
        {"frame_id": 1, "timestamp_sec": 5.0, "filename": "frame_000001.jpg"},
        {"frame_id": 2, "timestamp_sec": 10.0, "filename": "frame_000002.jpg"},
    ])

    path = resolve_frame_path(root, "001", timestamp=5.9)
    assert path is not None
    assert path.name == "frame_000001.jpg"

    path2 = resolve_frame_path(root, "001", timestamp=9.9)
    assert path2.name == "frame_000002.jpg"


def test_resolve_frame_path_missing_manifest_returns_none(tmp_path):
    root = tmp_path / "output"
    assert resolve_frame_path(root, "999", timestamp=1.0) is None


# ----------------------------------------------------------------------
# 2026-07-27 真實使用時發現：影片編碼格式不受支援（AV1）導致 Phase 1 擷取
# 到 0 張影格，一路產生 0 筆結果；`export_csv([], ...)` 修復前會寫出完全
# 沒有欄位名稱的 CSV，`pd.read_csv()` 讀取時丟出 EmptyDataError，變成 API
# 500 錯誤（見 PROJECT_NOTES.md 第 17 節）。這裡驗證兩層防護：
#   1) 新版 `export_csv([], ...)`（見 test_csv_exporter.py）本來就會寫出
#      有標題列的合法 CSV，正常路徑不會走到這裡的 except 分支。
#   2) 這裡額外驗證：即使檔案「更誇張地」完全空白（沒有任何內容，模擬
#      這個修復生效前使用者機器上已經產生的舊檔案），read_channel_results
#      仍要能優雅回傳 0 筆結果，而不是讓 API 500。
# ----------------------------------------------------------------------

def test_read_channel_results_truly_empty_file_returns_zero_records_not_crash(tmp_path):
    root = tmp_path / "output"
    export_path = root / "001" / "channel1_okt" / "export.csv"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text("", encoding="utf-8-sig")  # 完全空白，修復前的舊檔案就是長這樣

    result = read_channel_results(root, "001", "channel1_okt")
    assert result["record_count"] == 0
    assert result["records"] == []
