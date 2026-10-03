"""
Step 3：影像前處理 (Pre-processing)
====================================
將原始 Frame 轉換為適合 OCR 的 PreprocessedFrame。

設計決策（2026-07-25，使用者確認，詳見 PROJECT_NOTES.md）：

1. ROI／裁切策略：實際使用情境為各類 YouTube 影片，字幕位置、大小、設計皆
   不固定，**禁止假設固定裁切座標**。預設行為為「不裁切，直接處理全畫面」；
   僅在 `config.settings.ROI_OVERRIDES` 中針對特定已知影片手動指定時才裁切
   （座標為 0~1 相對比例，不受解析度影響）。自動偵測字幕位置留待 Future
   Roadmap 才實作，本階段不做。

2. 二值化策略：EasyOCR 為深度學習模型，對「過度二值化」影像的辨識效果通常
   較差，尤其字幕設計（顏色／背景對比）各異時，強制二值化可能洗掉文字或
   產生雜訊。因此本模組輸出為「灰階 + CLAHE 對比強化」，**不做非黑即白的
   二值化**，較符合 EasyOCR 特性也較能耐受多樣化的真實素材。

3. 去雜訊 (denoise) 效能與決策方式：實測對全畫面 1920x1080 影像做
   fastNlMeansDenoising 每影格約 447ms，關閉則約 4ms（差約 100 倍）。
   使用者決議（2026-07-25）：**專案測試期間兩種都做**，等 Step 4 OCR
   接上後比對兩者辨識率；若去雜訊對辨識率的提升低於 15%，之後就預設關閉。
   本函式因此提供 `denoise` 參數可明確覆寫 True/False，供測試期間並行輸出
   兩種版本比較（見 scripts/run_phase2.py 的 --denoise both 模式）。
   最終預設值待 Phase 4/5 依實測數據決定，目前 config 中的預設值僅為過渡。

本模組刻意保持「不預設完美條件」：不假設字幕一定存在、不假設固定顏色對比、
不假設固定解析度或位置。
"""

from __future__ import annotations

from typing import Optional

import cv2

from config.settings import PREPROCESS_PARAMS
from src.schemas import Frame, PreprocessedFrame


def _resolve_roi_pixels(roi_frac: dict, width: int, height: int) -> tuple[int, int, int, int]:
    """將 0~1 相對比例 ROI 轉換為像素座標，並限制在畫面範圍內。"""
    x = max(0, min(int(round(roi_frac["x"] * width)), width - 1))
    y = max(0, min(int(round(roi_frac["y"] * height)), height - 1))
    w = max(1, min(int(round(roi_frac["w"] * width)), width - x))
    h = max(1, min(int(round(roi_frac["h"] * height)), height - y))
    return x, y, w, h


def preprocess(frame: Frame, roi: Optional[dict] = None, denoise: Optional[bool] = None) -> PreprocessedFrame:
    """
    對單一 Frame 執行前處理，輸出可直接餵入 OCR 的影像。

    Args:
        frame: 原始採樣影格。
        roi: 選用的裁切區域，格式為 {"x","y","w","h"}（0~1 相對比例）。
             預設為 None，代表不裁切、處理全畫面（見模組說明之設計決策）。
        denoise: 是否執行去雜訊，明確傳入 True/False 會覆寫
            `config.PREPROCESS_PARAMS["denoise"]`；預設 None 代表沿用設定檔。
            測試期間可分別傳入 True/False 以比較兩種輸出（見設計決策 3）。

    Returns:
        PreprocessedFrame: 含前處理後影像（灰階 + 對比強化，未二值化）。
    """
    image = frame.image
    height, width = image.shape[:2]

    if roi is not None:
        x, y, w, h = _resolve_roi_pixels(roi, width, height)
        image = image[y:y + h, x:x + w]

    scale = PREPROCESS_PARAMS["upscale_factor"]
    if scale != 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    clahe = cv2.createCLAHE(
        clipLimit=PREPROCESS_PARAMS["clahe_clip_limit"],
        tileGridSize=(PREPROCESS_PARAMS["clahe_tile_grid_size"], PREPROCESS_PARAMS["clahe_tile_grid_size"]),
    )
    enhanced = clahe.apply(gray)

    use_denoise = PREPROCESS_PARAMS["denoise"] if denoise is None else denoise
    if use_denoise:
        enhanced = cv2.fastNlMeansDenoising(enhanced, h=PREPROCESS_PARAMS["denoise_strength"])

    return PreprocessedFrame(frame_id=frame.frame_id, timestamp_sec=frame.timestamp_sec, roi_image=enhanced)
