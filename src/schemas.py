"""
標準化資料模型 (Standardized I/O Schemas)
==========================================
定義整個 pipeline 中，各模組之間傳遞資料的「標準介面」。
所有模組（video_io, frame_sampler, preprocessing, ocr, dedup, nlp, export）
只允許透過這些模型交換資料，禁止傳遞裸露的 dict 或未定義結構的物件，
以確保模組間可獨立替換、獨立測試。
"""

from __future__ import annotations

from typing import List, Optional
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class Frame(BaseModel):
    """Step 2 輸出：單一採樣影格"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame_id: int = Field(..., description="影格序號，從 0 開始遞增")
    timestamp_sec: float = Field(..., description="該影格在原始影片中的時間點（秒）")
    image: np.ndarray = Field(..., description="影格原始像素資料 (BGR, H x W x 3)")


class PreprocessedFrame(BaseModel):
    """Step 3 輸出：前處理後、可直接餵入 OCR 的影格"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame_id: int
    timestamp_sec: float
    roi_image: np.ndarray = Field(
        ...,
        description=(
            "前處理後之灰階＋對比強化影像（未二值化）。預設為全畫面（不裁切），"
            "因實際字幕位置／大小／設計不固定，不假設固定 ROI；"
            "僅在設定 ROI 覆寫時才會是裁切後的區域。"
        ),
    )


class OCRResult(BaseModel):
    """Step 4 輸出：單一影格的 OCR 辨識結果"""
    frame_id: int
    timestamp_sec: float
    text: str
    bbox: List[List[float]] = Field(..., description="文字邊界框座標，四點多邊形")
    confidence: float = Field(..., ge=0.0, le=1.0)


class DedupedSubtitle(BaseModel):
    """Step 5 輸出：去重後、具時間區間的字幕片段"""
    text: str
    start_time: float
    end_time: float
    avg_confidence: float = Field(..., ge=0.0, le=1.0)


class WordToken(BaseModel):
    """Step 6 輸出的單字拆解結果"""
    word: str
    pos: str = Field(..., description="詞性標註")
    gloss: str = Field(..., description="中文釋義")


class SemanticResult(BaseModel):
    """Step 6 輸出：完整語意解析結果，對應一句 DedupedSubtitle"""
    original_text: str
    translation: str
    tokens: List[WordToken]
    example_sentence: Optional[str] = None
    start_time: float
    end_time: float


class ExportRecord(BaseModel):
    """Step 8 輸出：標準化匯出欄位，對應規格書 CSV 格式"""
    原文: str
    中文: str
    詞性: str
    例句: str = ""
    備註: str = ""


class DictionaryCandidate(BaseModel):
    """
    Phase 5 Channel 1 / 3 共用：字典查詢單一詞義候選。

    一個韓文寫法（written_form）可能對應多個同形詞（homonym_number 不同）、
    每個同形詞又可能有多個詞義（sense_num 不同），依決策紀錄（見
    PHASE5_MULTI_CHANNEL_PLAN.md 13.1 節）全部列出，不篩選單一「最佳」候選，
    一個詞義候選對應一筆 DictionaryCandidate。
    """
    written_form: str
    part_of_speech: str = ""
    homonym_number: str = ""
    sense_num: str = ""
    definition: str = Field("", description="韓文釋義")
    example: str = Field("", description="代表性韓文例句；例句本身沒有中文對照")
    translation: str = Field("", description="中文翻譯；查無對應詞彙則為空字串")
