# OCR 字幕擷取與多語意表徵系統

以規格書「專案架構.docx」為基礎之開發專案。詳細開發注意事項見 `PROJECT_NOTES.md`；在自己機器上「從 0 開始」跑完整測試（含 GPU 驗證、Phase 1-3 執行、denoise 比較）的完整步驟見 **`LOCAL_TESTING.md`**。

## 環境建置 (Phase 0)

```bash
bash scripts/setup_env.sh
```

或手動：

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> `easyocr`（含 torch）與 `konlpy`（需 JDK）安裝耗時較長，體積較大，請預留時間與硬碟空間。

## GPU 環境確認 (Phase 3 前置)

Step 4 OCR 強制要求使用 GPU（見 `PROJECT_NOTES.md` 第 10 節），偵測不到 GPU 會直接終止程式。請照以下步驟在**你自己的機器**上確認（開發用的雲端沙盒沒有 GPU，無法代為驗證）：

1. **確認 Windows 端 NVIDIA 驅動已支援 WSL**（若你是用 WSL 開發，如目前 `.venv` 的建立方式所示）：在 Windows PowerShell 執行 `nvidia-smi`，應能看到 GPU 型號與驅動版本、右上角 `CUDA Version`。若指令不存在，先到 NVIDIA 官網安裝支援 WSL 的顯示卡驅動。
2. **在 WSL / Linux 終端機內也執行一次 `nvidia-smi`**，確認能從 WSL 內部看到同一張顯卡（WSL2 是透過 Windows 端驅動轉發，不需要在 WSL 內另外裝驅動）。
3. **啟用專案的虛擬環境**：
   ```bash
   cd /mnt/c/Users/LinKJ/Desktop/專題資料/ocr_subtitle_system
   source .venv/bin/activate
   ```
4. **安裝支援 CUDA 的 torch**（版本需對應第 1 步看到的 `CUDA Version` 上限，實際安裝指令請至 https://pytorch.org/get-started/locally/ 選擇對應版本，例如）：
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   ```
5. **安裝其餘依賴**：`pip install -r requirements.txt`（此時 easyocr 應會偵測到已安裝的 CUDA 版 torch，不會另外覆蓋掉）。
6. **執行 GPU 檢查工具確認**：
   ```bash
   python scripts/check_gpu.py
   ```
   看到 `[GPU 檢查通過] 偵測到 N 張可用 GPU：...` 並列出你的顯卡名稱，即代表確認成功，可以繼續執行 `scripts/run_phase3.py`。
   若印出 `torch.cuda.is_available(): False` 或直接終止，代表驅動／torch 版本沒有正確搭配，請把 `check_gpu.py` 的完整輸出回報，再一起排查。

## 執行測試

```bash
pytest
```

## 目錄結構

```
config/         集中設定（採樣率、ROI、閾值等，禁止在模組內硬編碼）
src/schemas.py  所有模組間傳遞資料的標準化介面（pydantic model）
src/video_io/       Step 1 視訊源載入
src/frame_sampler/  Step 2 影格採樣
src/preprocessing/  Step 3 影像前處理
src/ocr/            Step 4 OCR 辨識
src/dedup/          Step 5 時序去重
src/nlp/            Step 6 多語意解析（翻譯／斷詞／整合）
src/export/         Step 8 結構化匯出（CSV / Anki，anki_exporter.py 尚未納入測試）
src/api/            Step 7 後端 API（FastAPI，Phase 6 已實作，見下方）
src/pipeline.py     [已過時／死碼] Phase 5 前的舊版 Step 1-6 orchestrator，
                    呼叫的 src/nlp/analyzer.py 等三個模組仍是 Phase 5 前
                    刻意留白的 stub；Phase 5 已改用三通道架構取代，Phase 6
                    的 API 改呼叫 src/api/pipeline_runner.py，未使用此檔案
frontend/           Step 7 前端頁面（Phase 7 已實作，見下方）
tests/              各模組單元測試
```

### Phase 6：後端 API（已實作，2026-07-26）

`src/api/main.py` 提供以下路由（決策紀錄見 PROJECT_NOTES.md 第 15 節）：

- `POST /api/upload`：接收影片檔案，儲存後立即在背景觸發完整流程
  （`src/api/pipeline_runner.py`：Phase 1→2→3(GPU)→Channel 1(可選幾個引擎)/2/3），
  回傳 `job_id`（同時作為 `video_id` 使用）。
- `GET /api/jobs/{job_id}/status`：查詢整體狀態（queued/running/done/failed）
  與各階段的成功/失敗/耗時明細（`JobStore`，SQLite 持久化，伺服器重啟後仍可查詢）。
- `GET /api/jobs/{job_id}/results?channel=`：取得指定通道的字幕/翻譯結果，
  預設 `channel3`，其餘 5 組（channel1_okt/komoran/kkma/mecab、channel2）
  透過 `channel` 查詢參數指定。每筆紀錄含 `timestamp_start`/`timestamp_end`
  （Phase 7 新增，從 `備註` 解析出的結構化秒數）。
- `POST /api/jobs/{job_id}/export?format=csv&channel=`：下載指定通道的
  `export.csv`；只支援 `format=csv`（Anki 本身即透過 CSV 匯入，未串接
  `anki_exporter.py`，見決策紀錄）。

啟動方式：`uvicorn src.api.main:app --reload`，啟動後開啟
`http://localhost:8000/` 即為 Phase 7 前端頁面（`create_app()` 會把
`frontend/` 掛載為靜態檔案，與 API 同源，避免瀏覽器端的 CORS/file:// 問題）。

### Phase 7：前端頁面 + 測試期間便利功能（已實作，2026-07-26）

`frontend/index.html` + `app.js` + `style.css`，純 HTML/CSS/JS、無建置流程。
分兩個區塊（決策紀錄見 PROJECT_NOTES.md 第 16 節）：

**核心介面**（成品會保留）：影片檔案選取＋開始按鈕 → 輪詢 `/api/jobs/{id}/status`
顯示進度 → 通道選擇下拉選單 → 結果表格（影片截圖／韓文單字／詞性／翻譯／例句，
截圖來自新增的 `GET /api/jobs/{id}/frame?timestamp=`，取最接近時間戳記的真實
OCR 影格）→ 匯出檔案按鈕（觸發瀏覽器下載 CSV）。

**測試用工具區**（`index.html` 裡的 `<section id="test-panel">`，成品完成後
使用者會要求整個移除，移除時不影響核心介面）：
- 一鍵確認環境是否齊全（新增 `GET /api/environment`，見
  `src/api/environment_check.py`：GPU/CUDA、Java、KoNLPy 4 引擎+Mecab-ko、
  Ollama 連線、字典索引檔、關鍵 Python 套件，只顯示有/無＋簡短原因）。
- 參數調整：取樣率(FPS)、最大影格數、LLM 模型/位址、OCR 最低信心值、去重
  時間間隔、CLAHE 對比強化強度、去雜訊強度（後三者透過
  `pipeline_runner._temporary_settings_override()` 暫時覆寫
  `config/settings.py`，執行後自動還原）。
- 是否去雜訊 (denoise) 開關。
- Channel 1/2/3 個別開關；Channel 1 額外可勾選要跑哪幾個子引擎。
- 各流程階段耗時表格（來自 `/api/jobs/{id}/status` 的 `stages` 明細）。

`/api/upload` 對應新增的 Form 參數：`include_channel1`／`channel1_engines`
（逗號分隔，如 `"okt,mecab"`）／`include_channel3`／`denoise`／
`sample_rate_fps`／`max_frames`／`model`／`base_url`／`min_confidence`／
`dedup_max_gap_sec`／`clahe_clip_limit`／`denoise_strength`，皆有預設值，
不影響既有呼叫方式（詳見 PROJECT_NOTES.md 第 16 節）。
