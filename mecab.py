"""
Mecab-ko 通用相容模組 (Universal Compatibility Layer)
======================================================
為專案提供統一的 MeCab 介面，跨 Python 3.8 ~ 3.14+ 及多作業系統 (Windows/Linux/macOS)。
優先使用現代跨平台預編譯 wheel (mecab-python3 + mecab-ko-dic)；
若環境存在舊版 python-mecab-ko 或 konlpy.tag.Mecab 亦可自動無縫相容。
"""

from __future__ import annotations

import sys
from typing import List, Tuple, Optional

_backend_name: Optional[str] = None
_tagger_factory = None
__version__ = "1.0.0"

# 1. 優先嘗試 mecab-python3 + mecab-ko-dic (相容 Python 3.8 ~ 3.14+，零編譯)
try:
    import mecab_ko_dic
    import MeCab as _NativeMeCab

    _backend_name = "mecab-python3 + mecab-ko-dic"
    __version__ = getattr(_NativeMeCab, "__version__", "1.0.12")

    class _NativeTaggerWrapper:
        def __init__(self, dicpath: Optional[str] = None):
            args = mecab_ko_dic.MECAB_ARGS if dicpath is None else f"-d \"{dicpath}\""
            self._tagger = _NativeMeCab.Tagger(args)
            self._backend = "mecab-python3"

        def pos(self, text: str) -> List[Tuple[str, str]]:
            node = self._tagger.parseToNode(text)
            res = []
            while node:
                if node.surface:
                    pos_tag = node.feature.split(",")[0]
                    res.append((node.surface, pos_tag))
                node = node.next
            return res

        def morphs(self, text: str) -> List[str]:
            return [w for w, _ in self.pos(text)]

        def nouns(self, text: str) -> List[str]:
            return [w for w, p in self.pos(text) if p.startswith("NN")]

    _tagger_factory = _NativeTaggerWrapper
except Exception:
    pass

# 2. 次選嘗試 konlpy.tag.Mecab (若使用者有系統編譯版)
if _tagger_factory is None:
    try:
        from konlpy.tag import Mecab as _KonlpyMecab
        # 測試是否能正常初始化（未編譯字典者會在此拋出例外）
        _test_tagger = _KonlpyMecab()
        _backend_name = "konlpy.tag.Mecab"

        class _KonlpyTaggerWrapper:
            def __init__(self, dicpath: Optional[str] = None):
                self._tagger = _KonlpyMecab(dicpath=dicpath) if dicpath else _KonlpyMecab()
                self._backend = "konlpy.tag.Mecab"

            def pos(self, text: str) -> List[Tuple[str, str]]:
                return self._tagger.pos(text)

            def morphs(self, text: str) -> List[str]:
                return self._tagger.morphs(text)

            def nouns(self, text: str) -> List[str]:
                return self._tagger.nouns(text)

        _tagger_factory = _KonlpyTaggerWrapper
    except Exception:
        pass

# 若完全沒有任何可用的 MeCab 後端，拋出 ImportError，符合 pytest.importorskip 語意
if _tagger_factory is None:
    raise ImportError(
        "未偵測到可用的 Mecab-ko 後端。\n"
        "請安裝推薦套件：pip install mecab-python3 mecab-ko-dic"
    )


class MeCab:
    """提供標準 MeCab 斷詞介面 (.pos, .morphs, .nouns)"""

    def __init__(self, dicpath: Optional[str] = None):
        self._impl = _tagger_factory(dicpath=dicpath)
        self._backend = getattr(self._impl, "_backend", _backend_name)

    def pos(self, text: str) -> List[Tuple[str, str]]:
        return self._impl.pos(text)

    def morphs(self, text: str) -> List[str]:
        return self._impl.morphs(text)

    def nouns(self, text: str) -> List[str]:
        return self._impl.nouns(text)
