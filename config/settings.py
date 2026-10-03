"""
集中設定檔 (Centralized Configuration)
========================================
所有可調參數集中於此，禁止在各模組中硬編碼 magic number，
方便日後調校與單元測試時覆寫。
"""

SAMPLING = {
    "rate_fps": 1.0,  # Step 2：預設採樣率
}

ROI = None
# Step 3：字幕 ROI。
#
# 決策紀錄（2026-07-25，使用者確認）：實際使用情境為各類 YouTube 影片，
# 字幕位置／大小／設計皆不固定，禁止假設固定座標。因此預設為 None，
# 代表「不裁切，直接處理全畫面」；自動偵測字幕位置留待 Future Roadmap。
#
# 若日後需要針對「已知固定版型」的特定影片手動指定裁切區域，可在
# ROI_OVERRIDES 中以「影片檔名（不含副檔名）」為 key 新增覆寫設定。
# 座標一律使用 0~1 之間的相對比例（而非像素），確保設定不受影片解析度影響。
ROI_OVERRIDES: dict = {
    # 範例（預設不啟用）：
    # "001": {"x": 0.0, "y": 0.75, "w": 1.0, "h": 0.25},
}

PREPROCESS_PARAMS = {
    # 決策紀錄（2026-07-25，使用者確認）：EasyOCR 為深度學習模型，對「過度
    # 二值化」的影像辨識效果通常較差，尤其字幕設計（顏色／背景對比）各異時，
    # 強制二值化可能洗掉文字或造成雜訊。因此 Step 3 輸出改為「灰階 + 對比
    # 強化（CLAHE）」，不做非黑即白的二值化。
    "clahe_clip_limit": 2.0,       # CLAHE 對比強化強度，越大對比越強
    "clahe_tile_grid_size": 8,     # CLAHE 分塊網格大小（8x8）
    "denoise": True,               # 是否執行去雜訊（全畫面去雜訊較耗時，可視效能關閉）
    "denoise_strength": 7,
    "upscale_factor": 1.0,         # 預設不放大；僅在有裁切小範圍 ROI 時才建議調大
}

OCR_CONFIG = {
    # 決策紀錄（2026-07-25，使用者明確要求）：Step 4 OCR 強制使用 GPU，
    # 若偵測不到可用 GPU 必須終止程式，禁止靜默改用 CPU。
    # GPU 偵測與強制終止邏輯見 src/ocr/gpu_check.py（ensure_gpu_available）。
    "languages": ["ko"],
    "min_confidence": 0.4,
}

DEDUP_CONFIG = {
    "max_gap_sec": 1.5,  # 判定為「同一句字幕」的最大時間間隔
}

ANKI_CONFIG = {
    "model_id": 1607392319,   # 固定值，勿隨意變更（見 export/anki_exporter.py 注意事項）
    "deck_id": 2059400110,
    "deck_name": "OCR Subtitle Vocabulary",
}

DICTIONARY_CONFIG = {
    # Phase 5 韓中字典（見 PHASE5_MULTI_CHANNEL_PLAN.md 第 1、13.2 節）。
    # 原始資料為 11 個 LMF XML 檔（韓國國立國語院《한국어기초사전》），
    # 索引在開發/測試階段建立一次即可，不影響成品執行效能。
    "xml_dir": "韩中字典xml",                        # 原始 XML 目錄（相對於專案根目錄）
    "index_db_path": "data/dictionary_index.sqlite3",  # 建好的索引快取位置
    "target_language": "중국어",                      # Equivalent 中要取哪個語言當作「中文」欄位
    # 無對應中文詞彙時，字典檔內固定以此字串標示（見 build_dictionary_index.py 說明），
    # 索引建立時會將其正規化為空字串，查詢端不需要再特別判斷這個特殊字串。
    "no_equivalent_marker": "(无对应词汇)",
    # 一個詞義（Sense）底下可能有多筆例句，例句欄位只需要「一句代表性例句」，
    # 依此優先序挑選第一個找得到的類型：文章／完整句子（문장）> 詞組（구）> 對話（대화）。
    # （此為工程上的合理預設，例句本身沒有中文對照，一律使用韓文原句。）
    "example_type_priority": ["문장", "구", "대화"],
}

API_CONFIG = {
    # Phase 6 後端 API（見 PROJECT_NOTES.md 第 15 節）。
    # 決策紀錄（2026-07-26，使用者確認）：
    #   1) /api/upload 真正接受任意上傳影片，並觸發完整流程（Phase1→2→3→Channel1/2/3）。
    #   2) /api/jobs/{id}/results 預設回傳 default_results_channel，其餘透過 ?channel= 查詢參數指定。
    #   3) 工作狀態採輕量持久化（SQLite），伺服器重啟後仍可查詢先前工作的進度/結果。
    #   4) 匯出僅支援 CSV（Anki 匯入本身就是吃 CSV，不需要另外接 anki_exporter.py）。
    "job_db_path": "data/jobs.sqlite3",
    "upload_dir": "data/uploads",
    "data_output_root": "data/output",
    "allowed_video_extensions": [".mkv", ".mp4", ".mov", ".avi"],
    "valid_channels": [
        "channel1_okt", "channel1_komoran", "channel1_kkma", "channel1_mecab",
        "channel2", "channel3",
    ],
    "default_results_channel": "channel3",
    "denoise_mode": "on",  # 上傳影片跑完整流程時使用哪一種前處理版本；denoise 最終決策仍延後到專案尾聲
    "llm_model": "qwen2.5:7b",
    "llm_base_url": "http://localhost:11434",
}
