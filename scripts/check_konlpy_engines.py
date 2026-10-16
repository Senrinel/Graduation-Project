"""
KoNLPy 五引擎環境檢查腳本 (Phase 5 環境建制)
==============================================
獨立驗證 Channel 1 需要用到的五個韓文斷詞引擎（Okt / Komoran / Kkma /
Hannanum / Mecab-ko）是否都能正確初始化與執行，並印出每個引擎對同一句
測試文字的斷詞結果與耗時，方便比較。

Okt / Komoran / Kkma / Hannanum 僅需 `pip install konlpy` + JDK 11+；
Mecab-ko 優先嘗試 `python-mecab-ko`（純 pip 安裝，自帶字典，不需編譯，
見 LOCAL_TESTING.md「Phase 5 環境建制」），失敗才退回 `konlpy.tag.Mecab`
（需另外編譯系統版 mecab + mecab-ko-dic）。若都未安裝，本腳本會印出清楚
的「未安裝」訊息並略過，不會讓整個腳本失敗。

已知問題：Hannanum（`kr.lucypark.jhannanum`）在較新版本 JDK（實測 JDK 21）
下會因為該套件內部用 `getProtectionDomain().getCodeSource()` 尋找自身資源
路徑的舊寫法失效而丟出 NullPointerException；JDK 11 下正常。若你的
`java -version` 是 17/21 以上且 Hannanum 失敗，屬已知相容性問題，
可安裝 JDK 11 並將 `JAVA_HOME` 指向該版本後再試。

用法：
    python scripts/check_konlpy_engines.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_SENTENCE = "오늘 날씨가 정말 좋네요"

# (顯示名稱, konlpy.tag 內的類別名稱)
JAVA_ENGINES = [
    ("Okt", "Okt"),
    ("Komoran", "Komoran"),
    ("Kkma", "Kkma"),
    ("Hannanum", "Hannanum"),
]


def check_java_engines() -> dict:
    """檢查四個純 Java 引擎（Okt/Komoran/Kkma/Hannanum）。"""
    results = {}
    try:
        import konlpy.tag as konlpy_tag
    except ImportError as e:
        print(f"[錯誤] 無法匯入 konlpy：{e}")
        print("       請先執行: pip install konlpy JPype1")
        return results

    for name, cls_name in JAVA_ENGINES:
        try:
            cls = getattr(konlpy_tag, cls_name)
            t0 = time.time()
            tagger = cls()
            init_s = time.time() - t0

            t0 = time.time()
            morphs = tagger.morphs(TEST_SENTENCE)
            pos = tagger.pos(TEST_SENTENCE)
            run_s = time.time() - t0

            print(f"[OK] {name}: 初始化 {init_s:.2f}s，斷詞 {run_s*1000:.1f}ms")
            print(f"     morphs = {morphs}")
            print(f"     pos    = {pos}")
            results[name] = {"available": True, "init_s": init_s, "run_s": run_s}
        except Exception as e:
            print(f"[失敗] {name}: {type(e).__name__}: {e}")
            results[name] = {"available": False, "error": str(e)}
    return results


def check_mecab() -> dict:
    """
    檢查 Mecab-ko。

    依序嘗試：
    1. mecab-python3 + mecab-ko-dic（現代跨平台預編譯 wheel，支援 Python 3.8 ~ 3.14+）
    2. python-mecab-ko（舊版二進位 wheel）
    3. konlpy.tag.Mecab（需系統編譯安裝 mecab 引擎 + mecab-ko-dic）
    """
    # 1. 優先嘗試 mecab-python3 + mecab-ko-dic
    try:
        import mecab_ko_dic
        import MeCab as _NativeMeCab

        t0 = time.time()
        tagger = _NativeMeCab.Tagger(mecab_ko_dic.MECAB_ARGS)
        init_s = time.time() - t0
        t0 = time.time()
        node = tagger.parseToNode(TEST_SENTENCE)
        pos = []
        while node:
            if node.surface:
                pos.append((node.surface, node.feature.split(",")[0]))
            node = node.next
        morphs = [w for w, _ in pos]
        run_s = time.time() - t0
        print(f"[OK] Mecab-ko（mecab-python3 + mecab-ko-dic）: 初始化 {init_s:.3f}s，斷詞 {run_s*1000:.2f}ms")
        print(f"     morphs = {morphs}")
        print(f"     pos    = {pos}")
        return {"available": True, "backend": "mecab-python3", "init_s": init_s, "run_s": run_s}
    except (ImportError, ModuleNotFoundError):
        pass
    except Exception as e:
        print(f"[失敗] mecab-python3 已安裝但執行失敗: {type(e).__name__}: {e}")

    # 2. 嘗試 python-mecab-ko
    try:
        from mecab import MeCab as PyMecab

        t0 = time.time()
        tagger = PyMecab()
        init_s = time.time() - t0
        t0 = time.time()
        morphs = tagger.morphs(TEST_SENTENCE)
        pos = tagger.pos(TEST_SENTENCE)
        run_s = time.time() - t0
        backend_name = getattr(tagger, "_backend", "python-mecab-ko")
        print(f"[OK] Mecab-ko（{backend_name}）: 初始化 {init_s:.3f}s，斷詞 {run_s*1000:.2f}ms")
        print(f"     morphs = {morphs}")
        print(f"     pos    = {pos}")
        return {"available": True, "backend": backend_name, "init_s": init_s, "run_s": run_s}
    except (ImportError, ModuleNotFoundError):
        pass  # 尚未安裝 python-mecab-ko，往下嘗試 konlpy.tag.Mecab
    except Exception as e:
        print(f"[失敗] python-mecab-ko 已安裝但執行失敗: {type(e).__name__}: {e}")

    try:
        from konlpy.tag import Mecab
    except ImportError:
        print("[未安裝] Mecab-ko：未安裝可用套件。")
        print("         建議執行: pip install mecab-python3 mecab-ko-dic")
        return {"available": False}

    try:
        t0 = time.time()
        tagger = Mecab()
        init_s = time.time() - t0
        t0 = time.time()
        morphs = tagger.morphs(TEST_SENTENCE)
        pos = tagger.pos(TEST_SENTENCE)
        run_s = time.time() - t0
        print(f"[OK] Mecab-ko（konlpy.tag.Mecab）: 初始化 {init_s:.2f}s，斷詞 {run_s*1000:.1f}ms")
        print(f"     morphs = {morphs}")
        print(f"     pos    = {pos}")
        return {"available": True, "backend": "konlpy.tag.Mecab", "init_s": init_s, "run_s": run_s}
    except Exception as e:
        print("[未安裝] Mecab-ko：底層 mecab 執行檔／字典尚未編譯安裝完成。")
        print(f"         （konlpy 回報：{type(e).__name__}: {e}）")
        print("         建議安裝預編譯套件: pip install mecab-python3 mecab-ko-dic")
        return {"available": False, "error": str(e)}


def main() -> None:
    print(f"測試句：「{TEST_SENTENCE}」\n")
    print("=== 純 Java 引擎（Okt / Komoran / Kkma / Hannanum）===")
    java_results = check_java_engines()

    print("\n=== Mecab-ko（獨立編譯安裝）===")
    mecab_result = check_mecab()

    print("\n=== 總結 ===")
    available = [name for name, r in java_results.items() if r.get("available")]
    available += ["Mecab-ko"] if mecab_result.get("available") else []
    print(f"可用引擎（{len(available)}/5）: {', '.join(available) if available else '無'}")


if __name__ == "__main__":
    main()
