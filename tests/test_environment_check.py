"""
測試 src/api/environment_check.py（Phase 7「一鍵確認環境是否齊全」，見
PROJECT_NOTES.md 第 16 節）。

沙盒沒有 GPU/torch/Ollama，這裡驗證的是「每一項檢查各自獨立、不會因為某
一項失敗就讓整個 check_environment() 掛掉」，以及回傳格式的正確性——不是
驗證每一項在沙盒裡都要是 True（沙盒本來就沒有 GPU，這是誠實反映環境，
不是 bug）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.environment_check import (  # noqa: E402
    check_dictionary_index,
    check_environment,
    check_java,
    check_ollama,
    check_python,
    check_python_packages,
)


def test_check_python_always_ok():
    item = check_python()
    assert item["ok"] is True
    assert item["name"] == "Python"
    assert "." in item["detail"]


def test_check_ollama_unreachable_returns_false_not_exception():
    item = check_ollama("http://localhost:1")  # 保證連不上的位址
    assert item["ok"] is False
    assert "無法連線" in item["detail"]


def test_check_dictionary_index_missing_file(tmp_path):
    item = check_dictionary_index(str(tmp_path / "does-not-exist.sqlite3"))
    assert item["ok"] is False
    assert "不存在" in item["detail"]


def test_check_dictionary_index_valid_file(tmp_path):
    import sqlite3
    db_path = tmp_path / "test_dict.sqlite3"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE entries (entry_pk INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO entries DEFAULT VALUES")

    item = check_dictionary_index(str(db_path))
    assert item["ok"] is True
    assert "1 筆詞條" in item["detail"]


def test_check_java_does_not_raise():
    item = check_java()
    assert "name" in item and "ok" in item and isinstance(item["ok"], bool)


def test_check_python_packages_returns_list_with_expected_names():
    items = check_python_packages()
    names = [i["name"] for i in items]
    assert "套件：fastapi" in names
    assert "套件：requests" in names
    assert all(isinstance(i["ok"], bool) for i in items)


def test_check_environment_aggregates_all_items_without_raising(tmp_path):
    """整合測試：即使字典索引檔不存在、Ollama 連不上，整個函式仍應正常回傳，不拋例外。"""
    items = check_environment(
        dict_db_path=str(tmp_path / "missing.sqlite3"),
        ollama_base_url="http://localhost:1",
    )
    assert isinstance(items, list)
    assert len(items) >= 10  # Python + GPU + Java + 3 KoNLPy + Mecab + Ollama + 字典 + 8 套件
    for item in items:
        assert set(item.keys()) == {"name", "ok", "detail"}
        assert isinstance(item["ok"], bool)
