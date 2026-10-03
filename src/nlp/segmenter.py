"""
Step 6b：單字拆解 (Word Segmentation)
======================================
韓文斷詞待 Phase 5 決定工具（KoNLPy 系列 / Mecab-ko），此處僅定義標準介面。

注意事項：
- KoNLPy 需先安裝 JDK 11+ 並設定 JAVA_HOME，Windows 環境安裝步驟較繁瑣。
- Mecab-ko 速度較快，但 Windows 上編譯／安裝較不直覺，需另行處理。
"""

from __future__ import annotations
from src.schemas import WordToken


def segment(text: str) -> list[WordToken]:
    """
    將句子拆解為單字，並標註詞性與釋義。

    Args:
        text: 原文（韓文句子）。

    Returns:
        list[WordToken]: 拆解後的單字列表。
    """
    raise NotImplementedError("韓文斷詞工具待 Phase 5 選定後實作")
