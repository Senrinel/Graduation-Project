"""
Phase 7：「一鍵確認環境是否齊全」檢查模組
================================================
使用者決策紀錄（2026-07-26，見 PROJECT_NOTES.md 第 16 節）：這是「測試期間
方便操作」的功能區域，正式成品完成後使用者會要求移除，因此本模組刻意
獨立成單一檔案，之後要整個刪除也很單純（只需拿掉 `main.py` 裡對應的一個
路由 + 這個檔案本身）。

使用者確認要檢查的項目：
  1) GPU / CUDA（torch.cuda 是否可用）——OCR 強制要求，最關鍵的一項。
  2) Ollama 服務是否可連線——Channel 2/3 需要。
  3) KoNLPy 4 引擎（Okt/Komoran/Kkma）+ Mecab-ko——Channel 1 四個子通道
     所需（Hannanum 已於 Phase 5 正式排除，不列入檢查，見 PROJECT_NOTES.md
     13.6 節）。
  4) 字典索引檔是否存在且可查詢。
  5) 「包含 Python、Java 以及其他開發所需環境」——另外檢查 Python 版本、
     Java（`java -version`，KoNLPy 的 Okt/Komoran/Kkma 底層透過 JPype
     呼叫 JVM 所需）、以及本專案關鍵 Python 套件是否皆可正確匯入。

每一項檢查刻意都包成獨立函式、彼此不共用例外處理，任何一項檢查本身
如果丟例外，也只會讓「這一項」回報失敗，不會讓整個環境檢查端點掛掉
（每項檢查各自 try/except，並記錄失敗原因方便除錯）。

**重要**：這裡直接重用 `scripts/check_konlpy_engines.py` 既有的
`check_java_engines()` / `check_mecab()`（Phase 5 環境建制時就已寫好、
沙盒與使用者本機都驗證過），避免重複實作同一件事。這兩個函式會真的
初始化每個引擎（各約數百毫秒到數秒），所以本端點屬於「使用者主動按下
才執行」的一次性檢查，不建議前端自動輪詢。
"""

from __future__ import annotations

import importlib
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _item(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": ok, "detail": detail}


def check_python() -> dict:
    """Python 版本（本身一定「有」，只是回報版本字串供確認是否符合預期）。"""
    return _item("Python", True, f"{platform.python_version()}（{sys.executable}）")


def check_gpu() -> dict:
    """GPU / CUDA 是否可用（OCR 強制要求，見 src/ocr/gpu_check.py）。"""
    try:
        import torch
    except ImportError as e:
        return _item("GPU / CUDA", False, f"torch 未安裝：{e}")

    try:
        if not torch.cuda.is_available():
            return _item("GPU / CUDA", False, "torch 已安裝，但 torch.cuda.is_available() 回傳 False")
        names = [torch.cuda.get_device_properties(i).name for i in range(torch.cuda.device_count())]
        return _item("GPU / CUDA", True, f"{len(names)} 張可用：{', '.join(names)}")
    except Exception as e:  # noqa: BLE001
        return _item("GPU / CUDA", False, f"{type(e).__name__}: {e}")


def check_java() -> dict:
    """Java（JDK）是否可用——KoNLPy 的 Okt/Komoran/Kkma 底層透過 JPype 呼叫 JVM 所需。"""
    try:
        proc = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=10,
        )
        version_line = (proc.stderr or proc.stdout or "").splitlines()[0] if (proc.stderr or proc.stdout) else ""
        return _item("Java (JDK)", proc.returncode == 0, version_line)
    except FileNotFoundError:
        return _item("Java (JDK)", False, "找不到 java 執行檔（未安裝或未加入 PATH）")
    except Exception as e:  # noqa: BLE001
        return _item("Java (JDK)", False, f"{type(e).__name__}: {e}")


def check_konlpy_engines() -> list[dict]:
    """
    Channel 1 四個子通道所需的斷詞引擎：Okt / Komoran / Kkma（純 Java，透過
    KoNLPy）+ Mecab-ko（獨立套件）。直接重用 scripts/check_konlpy_engines.py
    既有的檢查函式，避免重複實作。Hannanum 已排除，不檢查。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from scripts.check_konlpy_engines import check_java_engines, check_mecab

    items = []
    try:
        java_results = check_java_engines()
        for name in ("Okt", "Komoran", "Kkma"):
            r = java_results.get(name, {"available": False, "error": "未執行到（konlpy 匯入失敗）"})
            if r.get("available"):
                items.append(_item(
                    f"KoNLPy / {name}", True,
                    f"初始化 {r['init_s']:.2f}s，斷詞 {r['run_s']*1000:.1f}ms",
                ))
            else:
                items.append(_item(f"KoNLPy / {name}", False, r.get("error", "未安裝或初始化失敗")))
    except Exception as e:  # noqa: BLE001
        for name in ("Okt", "Komoran", "Kkma"):
            items.append(_item(f"KoNLPy / {name}", False, f"{type(e).__name__}: {e}"))

    try:
        mecab_result = check_mecab()
        if mecab_result.get("available"):
            items.append(_item(
                "Mecab-ko", True,
                f"backend={mecab_result.get('backend')}，初始化 {mecab_result['init_s']:.3f}s",
            ))
        else:
            items.append(_item("Mecab-ko", False, mecab_result.get("error", "未安裝")))
    except Exception as e:  # noqa: BLE001
        items.append(_item("Mecab-ko", False, f"{type(e).__name__}: {e}"))

    return items


def check_ollama(base_url: str) -> dict:
    """Ollama 服務是否可連線（Channel 2/3 需要）。"""
    try:
        import requests
        resp = requests.get(f"{base_url}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get("name") for m in resp.json().get("models", [])]
            return _item("Ollama 服務", True, f"{base_url}，已安裝模型：{models or '(無)'}")
        return _item("Ollama 服務", False, f"{base_url} 回應狀態碼 {resp.status_code}")
    except Exception as e:  # noqa: BLE001
        return _item("Ollama 服務", False, f"無法連線 {base_url}：{type(e).__name__}: {e}")


def check_dictionary_index(dict_db_path: str) -> dict:
    """字典索引檔是否存在且可查詢（見 scripts/build_dictionary_index.py）。"""
    path = Path(dict_db_path)
    if not path.exists():
        return _item("字典索引檔", False, f"{path} 不存在，需先執行 scripts/build_dictionary_index.py")
    try:
        import sqlite3
        with sqlite3.connect(str(path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        return _item("字典索引檔", True, f"{path}，共 {count} 筆詞條")
    except Exception as e:  # noqa: BLE001
        return _item("字典索引檔", False, f"{path} 存在但查詢失敗：{type(e).__name__}: {e}")


# 「其他開發所需環境」：本專案關鍵 Python 套件是否皆可正確匯入。
_REQUIRED_PACKAGES = [
    ("torch", "OCR GPU 推論"),
    ("cv2", "影片讀取／前處理（opencv-python）"),
    ("easyocr", "Step 4 OCR"),
    ("requests", "Channel 2/3 呼叫 Ollama REST API"),
    ("fastapi", "Phase 6 後端 API"),
    ("pydantic", "標準化 schema"),
    ("konlpy", "Channel 1 斷詞（Okt/Komoran/Kkma）"),
    ("mecab", "Channel 1/3 斷詞（python-mecab-ko）"),
]


def check_python_packages() -> list[dict]:
    items = []
    for module_name, purpose in _REQUIRED_PACKAGES:
        try:
            mod = importlib.import_module(module_name)
            version = getattr(mod, "__version__", "(無版本資訊)")
            items.append(_item(f"套件：{module_name}", True, f"{purpose}｜版本 {version}"))
        except ImportError as e:
            items.append(_item(f"套件：{module_name}", False, f"{purpose}｜未安裝：{e}"))
        except Exception as e:  # noqa: BLE001
            items.append(_item(f"套件：{module_name}", False, f"{purpose}｜匯入時發生例外：{type(e).__name__}: {e}"))
    return items


def check_environment(dict_db_path: str, ollama_base_url: str) -> list[dict]:
    """彙整全部環境檢查項目，回傳一份扁平清單（每項含 name/ok/detail）供 API 直接回傳為 JSON。"""
    items: list[dict] = []
    items.append(check_python())
    items.append(check_gpu())
    items.append(check_java())
    items.extend(check_konlpy_engines())
    items.append(check_ollama(ollama_base_url))
    items.append(check_dictionary_index(dict_db_path))
    items.extend(check_python_packages())
    return items
