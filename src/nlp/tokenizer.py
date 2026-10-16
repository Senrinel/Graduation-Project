"""
韓文斷詞引擎統一介面 (Phase 5 Channel 1)
==============================================
把 Okt / Komoran / Kkma（皆透過 `konlpy.tag`）與 Mecab-ko（透過
`python-mecab-ko`，見 `LOCAL_TESTING.md`「Phase 5 環境建制」B 節）
四個斷詞引擎包成統一介面，供 Channel 1 runner 依 `--engine` 參數切換。

Hannanum 已於 2026-07-26 正式排除（使用者實測兩種修法皆無法解決
`NullPointerException`，見 PROJECT_NOTES.md 13.6 節），不在此列。

已知限制／簡化（工程預設，供 Channel 1 第一輪多引擎模擬測試使用；
非使用者明確規定，若字典命中率不理想可再調整）：
- KoNLPy／Mecab 只做斷詞與詞性標註，不做「字典原形還原」
  （lemmatization）。例如「좋아요」會斷成「좋」(形容詞語幹) + 「아요」
  (語尾)，但字典裡的寫法是辭典形「좋다」。本模組對詞性標記為「動詞／
  形容詞語幹」的詞彙，嘗試在查字典前補回「다」還原成辭典形
  （`Token.dictionary_form`），呼叫端查無結果時可再退回
  `Token.word`（斷詞原文）查一次。
- 各引擎詞性標記系統不同：Okt 用 "Verb"/"Adjective"；
  Komoran、Kkma、Mecab-ko 皆用 "VV"/"VA"（實測確認一致）。

已知的引擎間差異（實測發現，非本模組能修正，故意保留讓比較數據呈現
真實差異）：Komoran / Kkma / Mecab-ko 會把動詞/形容詞拆成「語幹＋語尾」
兩個詞（例如「좋네요」拆成「좋」(VA) + 「네요」(EC)），本模組補回「다」
即可還原辭典形「좋다」；但 **Okt 不會拆開語幹與語尾**，會把整個「좋네요」
當成一個 Adjective 詞彙輸出，此時補「다」只會得到「좋네요다」，查不到
字典。這是 Okt 斷詞風格本身的限制，不在此模組另外用規則硬拆（那需要
一份完整的韓文語尾清單，超出本次範圍），會直接反映在 Okt 的字典命中率
上——這正是四引擎比較實驗想呈現的真實差異之一。
"""

from __future__ import annotations

from typing import List, NamedTuple, Protocol


class Token(NamedTuple):
    word: str               # 斷詞後的原始文字（語幹形式，可能不是辭典形）
    pos: str                 # 詞性標記（各引擎標記系統不同，未統一）
    dictionary_form: str     # 供查字典使用的寫法（已嘗試還原動詞/形容詞辭典形）


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> List[Token]:
        ...


# 各引擎中，代表「動詞／形容詞語幹」的詞性標記集合，符合此標記者會嘗試
# 補回「다」還原成辭典形。
_PREDICATE_STEM_TAGS = {
    "okt": {"Verb", "Adjective"},
    "komoran": {"VV", "VA"},
    "kkma": {"VV", "VA"},
    "mecab": {"VV", "VA"},
}


def _to_dictionary_form(engine_name: str, word: str, pos: str) -> str:
    if pos in _PREDICATE_STEM_TAGS[engine_name] and not word.endswith("다"):
        return word + "다"
    return word


class _KonlpyTokenizer:
    """包住 konlpy.tag 底下的 Okt / Komoran / Kkma。"""

    def __init__(self, engine_name: str, tagger):
        self._engine_name = engine_name
        self._tagger = tagger

    def tokenize(self, text: str) -> List[Token]:
        return [
            Token(word=word, pos=pos, dictionary_form=_to_dictionary_form(self._engine_name, word, pos))
            for word, pos in self._tagger.pos(text)
        ]


class _MecabTokenizer:
    """包住 Mecab-ko（支援 mecab-python3 + mecab-ko-dic 或 python-mecab-ko）。"""

    def __init__(self):
        # 1. 優先嘗試 mecab-python3 + mecab-ko-dic（現代跨平台 wheel，支援 Python 3.8 ~ 3.14+）
        try:
            import mecab_ko_dic
            import MeCab as _NativeMeCab
            self._native_tagger = _NativeMeCab.Tagger(mecab_ko_dic.MECAB_ARGS)
            self._tagger = None
            return
        except Exception:
            pass

        # 2. 嘗試 python-mecab-ko (或通用相容層 mecab.py)
        try:
            from mecab import MeCab
            self._tagger = MeCab()
            self._native_tagger = None
            return
        except Exception:
            pass

        # 3. 嘗試 konlpy.tag.Mecab (若使用者有系統編譯版)
        try:
            from konlpy.tag import Mecab as _KonlpyMecab
            self._tagger = _KonlpyMecab()
            self._native_tagger = None
            return
        except Exception as e:
            raise RuntimeError(
                "未安裝或無法初始化 Mecab-ko 斷詞引擎。\n"
                "可透過 pip 安裝預編譯套件：pip install mecab-python3 mecab-ko-dic\n"
                "亦可改用推薦之 Komoran 引擎（或 Okt、Kkma）。"
            ) from e

    def pos(self, text: str) -> List[tuple[str, str]]:
        if getattr(self, "_native_tagger", None) is not None:
            node = self._native_tagger.parseToNode(text)
            res = []
            while node:
                if node.surface:
                    res.append((node.surface, node.feature.split(",")[0]))
                node = node.next
            return res
        return self._tagger.pos(text)

    def tokenize(self, text: str) -> List[Token]:
        return [
            Token(word=word, pos=pos, dictionary_form=_to_dictionary_form("mecab", word, pos))
            for word, pos in self.pos(text)
        ]


def get_tokenizer(engine_name: str) -> Tokenizer:
    """
    依引擎名稱取得斷詞器（延遲載入對應套件，避免 import 到不需要的重依賴）。

    Args:
        engine_name: "okt" / "komoran" / "kkma" / "mecab"

    Returns:
        實作 `tokenize(text) -> List[Token]` 的物件。

    Raises:
        ValueError: 傳入未知或已排除的引擎名稱（例如 "hannanum"）。
    """
    if engine_name == "okt":
        from konlpy.tag import Okt
        return _KonlpyTokenizer("okt", Okt())
    if engine_name == "komoran":
        from konlpy.tag import Komoran
        return _KonlpyTokenizer("komoran", Komoran())
    if engine_name == "kkma":
        from konlpy.tag import Kkma
        return _KonlpyTokenizer("kkma", Kkma())
    if engine_name == "mecab":
        return _MecabTokenizer()
    raise ValueError(
        f"未知或不支援的斷詞引擎：{engine_name!r}（可用：okt / komoran / kkma / mecab；"
        "hannanum 已於 2026-07-26 正式排除，見 PROJECT_NOTES.md 13.6 節）"
    )
