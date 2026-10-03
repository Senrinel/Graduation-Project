"""測試 src/ocr/results_io.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ocr.results_io import load_ocr_results  # noqa: E402

SAMPLE_CSV = (
    "frame_id,timestamp_sec,text,bbox,confidence\n"
    '2,2.0,나중,"[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]",0.9\n'
    '0,0.0,먼저,"[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]",0.8\n'
    '1,1.0,다음,"[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]",0.85\n'
)


def test_load_ocr_results_sorts_by_timestamp(tmp_path):
    csv_path = tmp_path / "ocr_results.csv"
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8-sig")

    results = load_ocr_results(str(csv_path))

    assert [r.text for r in results] == ["먼저", "다음", "나중"]
    assert [r.timestamp_sec for r in results] == [0.0, 1.0, 2.0]


def test_load_ocr_results_parses_bbox_as_nested_list(tmp_path):
    csv_path = tmp_path / "ocr_results.csv"
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8-sig")

    results = load_ocr_results(str(csv_path))

    assert results[0].bbox == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    assert isinstance(results[0].confidence, float)
