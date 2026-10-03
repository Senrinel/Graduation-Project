# 專案注意事項 (Project Notes)

以「基於 OCR 之字詞擷取與多語意表徵系統」規格書為基礎，記錄整個開發過程中必須遵守的架構原則與各階段技術注意事項。本檔案會隨專案進展持續更新。

## 1. 架構設計原則（全專案必守）

### 1.1 模組化 (Modularity)

- 每一個規格書中的 Step（1~8）都對應獨立的 Python 套件（`src/video_io`、`src/frame_sampler`、`src/preprocessing`、`src/ocr`、`src/dedup`、`src/nlp`、`src/export`、`src/api`）。
- 每個模組只做一件事，不得跨模組直接存取彼此的內部狀態；模組之間僅透過 `src/schemas.py` 定義的資料模型溝通。
- 任何演算法邏輯的替換（例如換一個 OCR 引擎、換一個翻譯引擎）都應只需要修改單一模組內部，不影響其他模組與呼叫端。`src/nlp/translator.py`、`src/nlp/segmenter.py` 目前刻意留白（`NotImplementedError`），就是為了在 Phase 5 才決定實作方案，同時保證介面已經固定。
- `src/pipeline.py` 是唯一負責「呼叫順序」的 orchestrator，不包含任何演算法細節。

### 1.2 標準化輸入／輸出 (Standardized I/O)

- 所有模組間傳遞的資料一律使用 `src/schemas.py` 中定義的 pydantic model（`Frame`、`PreprocessedFrame`、`OCRResult`、`DedupedSubtitle`、`WordToken`、`SemanticResult`、`ExportRecord`），禁止傳遞裸露的 `dict` 或 tuple。
- 好處：型別檢查、欄位驗證（如 `confidence` 必須介於 0~1）、單元測試時可直接建構假資料、未來加欄位時有明確的變更點。
- CSV 匯出欄位固定為：原文、中文、詞性、例句、備註，對應規格書「資料持久化格式」；`ExportRecord` 即為此欄位的程式化定義，不得任意增刪欄位（如需擴充，先討論再改 schema）。

### 1.3 集中設定 (Centralized Configuration)

- 所有可調參數（採樣率、ROI 座標、二值化參數、OCR 信心門檻、去重時間門檻、Anki model/deck id）都放在 `config/settings.py`，模組內禁止寫死 magic number。
- 好處：日後校調參數只需改一個檔案；單元測試可覆寫設定而不動到程式邏輯。

### 1.4 程式風格

- 一律使用 type hints 與 docstring（Google style：Args / Returns / Raises）。
- 統一用 `black` 格式化、`ruff` 做 lint。
- 每個模組頂部都有簡短說明其對應的規格書 Step、輸入輸出與已知限制／待辦事項。

## 2. 環境建置 (Phase 0) 注意事項

- Python 版本：建議 3.10+。
- `easyocr` 依賴 `torch`，安裝體積約 2-3GB，且首次執行會下載語言模型（需網路連線），本機安裝需預留時間與硬碟空間。
- 韓文斷詞若採用 `konlpy`：需先安裝 **JDK 11+** 並設定 `JAVA_HOME`；Windows 環境安裝流程較繁瑣，建議提前測試，必要時改用 Mecab-ko 或其他純 Python 方案。
- 若未來有 NVIDIA GPU + CUDA，可將 `config/settings.py` 中 `OCR_CONFIG["use_gpu"]` 設為 `True`，OCR 速度可大幅提升；純 CPU 環境下 EasyOCR 逐影格辨識可能偏慢，需注意整體處理時間。
- API 金鑰（若採用線上翻譯 API）一律放在 `.env`，不得寫死在程式碼或提交進版本控制（`.gitignore` 已排除 `.env`）。

## 3. 各模組後續開發注意事項

| 模組 | 對應 Step | 主要待決事項 |
|---|---|---|
| `preprocessing` | Step 3 | ROI 座標目前是佔位值，需依實際影片解析度重新校正；二值化/去雜訊參數需用真實素材反覆調校 |
| `ocr` | Step 4 | EasyOCR Reader 為單例快取，避免重複初始化造成效能問題；信心門檻需視實測誤判率調整 |
| `dedup` | Step 5 | 目前用完全字串比對，OCR 雜訊可能造成同句字幕辨識結果略有差異，未來需評估改用相似度比對（如 Levenshtein） |
| `nlp` | Step 6 | 翻譯引擎與韓文斷詞工具尚未選定，需在 Phase 5 決定「線上 API vs 本地模型」的取捨（品質、成本、隱私、離線可用性） |
| `export` | Step 8 | Anki 匯出的 model/deck id 已固定寫死，避免重複匯入被視為不同牌組；CSV 使用 UTF-8 with BOM 避免 Excel 開啟亂碼 |
| `api` | Step 7（後端） | 路由骨架已建立，實際邏輯串接留待 Phase 6；需定義非同步工作（影片處理）狀態查詢機制（job/status） |
| `frontend` | Step 7（前端） | 目前僅骨架，需與 `src/api/main.py` 的 REST 契約保持一致 |

## 4. 測試策略

- `tests/` 下每個模組對應獨立測試檔案，優先使用固定的假資料（synthetic frame / 已知文字）而非依賴真實影片，確保測試可重現、可離線執行。
- Phase 0 已建立 `tests/test_schemas.py` 作為 smoke test，驗證標準化資料模型可正確建構與驗證。
- 之後每個 Phase 完成對應模組實作後，需補上該模組的單元測試，最後才進行 Step1-8 端到端整合測試。

## 5. 資料與隱私考量

- 若 Phase 5 選擇線上翻譯 API，使用者影片中的文字內容會被傳送至第三方服務，需在後續文件中明確告知使用者。
- `data/input/`、`data/output/` 已加入 `.gitignore`，避免使用者影片與匯出結果被誤提交進版本控制。

## 6. Phase 1 重要發現：測試素材與規格書設想不同

`raw/` 資料夾中的 10 支測試影片（001~010.mkv）經實際檢視後，**內容並非「影片畫面 + 燒錄字幕」**，而是**整段皆為全螢幕韓語單字／選擇題卡**（例如：題目卡「고양이 / A.dog B.cat C.tiger D.wolf」、單字卡「이야기 [iyagi] story」）。

這與規格書範例（「오늘 날씨가 정말 좋네요」燒錄字幕疊加在影片畫面下方）情境不同，會直接影響 Phase 2 的 ROI 設計：

- 規格書設想：字幕固定在畫面下方一小塊區域 -> 可用固定小範圍 ROI 裁切。
- 實際測試素材：文字版面滿版且置中，不同影片／不同卡片的顏色、版面（有無題目列、單字位置、羅馬拼音列）都不固定 -> **固定小 ROI 不適用**，Phase 2 需改為「近乎全畫面 OCR」或依卡片版面動態偵測文字區塊，並列為 Phase 2 開工前需與使用者確認的問題。
- 影片為靜態卡片形式，同一張卡會持續顯示數秒到數十秒，1 FPS 採樣下會產生大量幾乎相同的影格，這正是 Step 5（時序去重）存在的意義，Phase 1 不需特別處理。

## 7. Phase 1 執行結果

- 10 支影片皆為 1920x1080、H.264 編碼；fps 不一致（001-005 為 29.97 fps，006-010 為 25 fps）——`load_video()` 已正確從各影片自行讀取 fps，`sample_frames()` 採樣率計算不受影響。
- 全部 10 支影片皆可被 OpenCV 正常開啟並讀取首影格，無損毀或格式不支援問題。
- 以 006.mkv（368 秒）做全片 1 FPS 採樣端到端測試：耗時約 22 秒、輸出 369 張影格，效能可接受。
- 新增 `scripts/run_phase1.py` 作為 Step 1-2 的可執行入口：輸入影片路徑，輸出採樣影格圖片 + 標準化 `manifest.csv`（frame_id, timestamp_sec, filename），供後續 Phase 2 開發直接讀取使用。
- 新增 `tests/test_phase1_pipeline.py`，以合成影片驗證 metadata 讀取與採樣邏輯正確性（離線可重現，不依賴 raw/ 真實素材）。
- 已知良性警告：部分影片以 OpenCV 開啟時會印出 `Error parsing Opus packet header`，屬音訊流解析警告，不影響影像讀取（pipeline 不需要音訊）。

## 8. Phase 2 使用者決策紀錄（2026-07-25）

實際使用情境為各類 YouTube 影片，字幕位置、大小、設計都不固定，使用者明確指示「禁止預設目標為期望完美狀態」。針對 Phase 1 提出的疑慮，使用者確認以下決策：

1. **ROI／裁切策略**：預設不裁切，全畫面前處理。不假設字幕固定位置；自動偵測留待 Future Roadmap。若未來需要，`config.settings.ROI_OVERRIDES` 可針對已知固定版型的特定影片手動指定（以 0~1 相對比例設定，不受解析度影響）。
2. **二值化策略**：不做非黑即白的強制二值化，改為「灰階 + CLAHE 對比強化」。理由：EasyOCR 為深度學習模型，過度二值化在字幕設計（顏色／背景對比）各異時容易洗掉文字或產生雜訊，灰階＋對比強化更能耐受多樣化素材。
3. **去雜訊 (denoise) 效能與決策方式**：實測對全畫面 1920x1080 影像做 fastNlMeansDenoising 每影格約 447~477ms，關閉則約 4~35ms（差約 15~100 倍）。由於 Step 4 OCR 尚未接上，無法單從速度判斷是否值得。使用者決議：**專案測試期間兩種都做**，`scripts/run_phase2.py` 預設 `--denoise both`，同時輸出 `processed/denoise_on/` 與 `processed/denoise_off/` 兩份結果供之後 Phase 4 比對辨識率；**若去雜訊對辨識率的提升低於 15%，之後就預設關閉**。此門檻與最終預設值待 Phase 4/5 依實測數據決定。

**重要提醒（使用者明確指示）**：後續所有「影片內容辨識」一律透過專案程式碼（EasyOCR 等模組）執行，禁止由我（Claude）直接以肉眼判讀畫面文字內容取代 OCR。Phase 1/2 對畫面內容的檢視僅用於確認前處理的裁切範圍、影像格式是否正確（以程式化方式比對 shape / dtype / unique values 等指標），不涉及文字辨識本身。

## 9. Phase 2 執行結果

- `src/preprocessing/pipeline.py` 已依上述決策重寫：`preprocess(frame, roi=None, denoise=None)`，預設全畫面、灰階+CLAHE、不二值化；`denoise` 參數可明確覆寫供比較測試。
- 新增 `scripts/run_phase2.py`：讀取 Phase 1 輸出的 `frames/manifest.csv`，套用前處理後輸出 `processed/denoise_on/` 與 `processed/denoise_off/` 兩份影像＋manifest，並列印各自耗時。
- 已對 001.mkv（15 影格）與 003.mkv（10 影格）實測：輸出影像 shape 與原始影格一致（確認未誤裁切）、dtype 為 uint8、unique values > 2（確認未被二值化）；denoise_on/off 兩版 mean/std 差異極小，最終是否關閉待 Step 4 OCR 接上後依辨識率比對決定。
- 新增 `tests/test_preprocessing.py`（4 項測試，皆用合成漸層影格離線驗證）：預設全畫面不裁切、輸出非二值化、roi 覆寫可正確按比例裁切、frame_id/timestamp 正確保留。
- 全專案測試（`tests/`）共 8 項全數通過。

## 10. Phase 3 使用者決策與重要限制（2026-07-25）

使用者明確要求：Step 4 OCR **必須使用 GPU**，若程式偵測到只能用 CPU，必須直接終止，且必須正確讀取 GPU 資訊（而非只是布林值判斷）。

**實作內容：**

- 新增獨立模組 `src/ocr/gpu_check.py`：
  - `get_gpu_info()`：透過 `torch.cuda` API 讀取所有可用 GPU 的裝置名稱、顯示記憶體、CUDA capability。
  - `ensure_gpu_available()`：強制檢查點，偵測不到 GPU 時印出清楚錯誤訊息並 `sys.exit(1)` 終止程式，**沒有任何 CPU fallback 分支**。
- `src/ocr/recognizer.py` 的 `get_reader()` 在建立 EasyOCR Reader 前一定先呼叫 `ensure_gpu_available()`，且固定傳入 `gpu=True`（不再提供 `use_gpu` 設定選項，避免被誤設為 False）。
- 新增 `scripts/run_phase3.py`：Step 4 CLI 入口，**刻意把 GPU 檢查放在程式最開頭、且延後匯入 `recognizer`／`easyocr`**，確保沒有 GPU 時程式會直接因為 GPU 檢查失敗而終止，不會先花時間匯入 easyocr 或下載模型才發現沒有 GPU。

**重要限制（必須讓使用者知道）**：本開發沙盒環境**沒有 GPU 硬體**（無 `nvidia-smi`、無 `/dev/nvidia*`、無 CUDA），且無法連線至 PyTorch 官方 CUDA wheel 索引（`download.pytorch.org` 被 proxy 擋下），完整 PyPI 版 torch（內含 CUDA 動態庫）體積達 GB 等級，也不適合在此沙盒安裝。因此：

- 無法在此沙盒對「真實 GPU + EasyOCR」做端到端 OCR 驗證，這件事必須在使用者自己有 GPU 的機器上執行。
- 已用兩種方式驗證程式邏輯本身正確：
  1. `tests/test_gpu_check.py`（5 項測試）：用 `sys.modules` 注入假的 `torch` 模組（不需真的安裝 torch），分別驗證「無 GPU 時 `ensure_gpu_available()` 會以 `SystemExit(1)` 終止」與「有 GPU 時正確回傳裝置資訊、不終止」兩種分支。
  2. 額外用一個臨時 stub 模組（僅供測試、非專案檔案）對 `scripts/run_phase3.py` 做過一次完整 CLI 端到端測試：模擬「無 GPU」時程式印出清楚錯誤訊息並以 exit code 1 終止（未觸及 easyocr）；模擬「有 1 張 GPU」時程式正確印出裝置資訊並繼續往下執行（之後才因沙盒未安裝 easyocr 而失敗，屬預期之外的環境限制，非 GPU 邏輯問題）。
- `requirements.txt` 中的 `easyocr`（內含 torch）仍需使用者在自己的 GPU 機器上安裝；安裝支援 CUDA 的 torch 版本，是 `torch.cuda.is_available()` 能回傳 `True` 的前提。

## 11. 關於「能否讓開發沙盒使用使用者本機硬體」的明確回覆（2026-07-25）

使用者詢問是否能讓 Claude 的開發沙盒直接運用使用者本機的硬體（包含 GPU）。這裡明確記錄結論：**不行，且沒有可行的變通方法**。

原因：開發沙盒是一個獨立、隔離的雲端 Linux 環境，與使用者本機（Windows/WSL）之間沒有任何硬體層級或網路層級的連線通道；沙盒的 bash 工具只能操作沙盒自己的檔案系統與掛載的資料夾，無法存取、驅動或轉發使用者電腦上的實體裝置（包含 GPU）。這與「程式沒寫好」無關，是架構層面的隔離限制。

**因此的實務安排**：

- 本專案所有需要 GPU 的步驟（Phase 3 OCR 及之後）本來就設計為「由使用者在自己的機器上執行」，沙盒僅負責開發、寫程式、以及用假資料（synthetic frame、mock torch 模組）驗證程式邏輯正確性。這與正常的軟體開發流程一致：開發環境（沙盒）與正式執行環境（使用者自己的 GPU 主機）本來就允許不同。
- 新增 `scripts/check_gpu.py` 作為輕量、獨立的本機驗證工具，供使用者在自己機器上快速確認 torch 是否正確抓到 GPU，不需要準備任何影片或前處理資料。
- 完整「從 0 開始」的本機測試步驟（環境安裝、GPU 驗證、跑 Phase 1-3、比較 denoise on/off 辨識率）已整理成獨立文件 **`LOCAL_TESTING.md`**，針對使用者目前的環境（Windows + WSL2，專案資料夾內已有 WSL 建立的 `.venv`）撰寫，不需要再重新摸索。
- 若使用者在自己機器上執行時遇到問題，可將完整終端機輸出提供給 Claude，由 Claude 依輸出內容遠端協助判斷問題（例如驅動版本、torch 版本是否搭配），但無法由 Claude 直接連線除錯。

## 11.1 沙盒開發持續性原則（確保缺硬體不會卡住 Phase 4-9 開發）

因為使用者本機測試需要 GPU，而沙盒沒有 GPU，為了讓後續 Phase 4-9 的開發不因為缺硬體而卡住，往後遇到「需要重硬體或重依賴（GPU/torch/easyocr/konlpy 等）」的模組時，沙盒端一律採用以下已驗證可行的做法繼續開發，不需要等使用者先在本機裝好環境才能動工：

1. **程式照常撰寫、`py_compile` 語法檢查**：所有模組即使沙盒裝不了對應套件，仍可正常撰寫並用 `python3 -m py_compile` 確認語法正確（Phase 3 的 `easyocr`、之後 Phase 5 的 `konlpy` 皆適用此法）。
2. **重依賴一律用 mock 注入方式做單元測試**：透過 `sys.modules["套件名"] = 假模組` 的方式，在不需要真的安裝該套件（或真的有對應硬體）的情況下，驗證程式邏輯本身的分支是否正確。已在 `tests/test_gpu_check.py` 驗證過這個模式可行且穩定。
3. **CLI 腳本的控制流程用臨時 stub 驗證**：需要時可寫一個「只為了這次驗證、不算專案檔案」的假模組（例如 Phase 3 驗證 `run_phase3.py` 時用過的假 `torch` stub），跑一次完整 CLI 流程確認分支正確，驗證完就刪除，不留在專案裡。
4. **真實效果驗證交給使用者本機**：沙盒完成邏輯與語法驗證後，把「怎麼在本機真正跑起來」寫成清楚步驟（如本次的 `LOCAL_TESTING.md`），使用者跑完回報實測數據（辨識率、效能等），沙盒再依數據把最終決策寫回 `config/settings.py` 與本檔案。

這個原則從 Phase 3 開始適用，Phase 5（`konlpy` 需要 JDK）預期也會遇到類似情況，屆時會延用同一套模式。

## 12. Phase 3 OCR 品質數據（真實素材，001.mkv，619 影格）

使用者已在自己機器（RTX 4060 8GB）跑出真實 OCR 結果，取代原本規劃中「Phase 4 才能決定」的 denoise 開關，統計如下：

- **偵測數量**：denoise_on 3326 筆、denoise_off 3347 筆（off 多 0.6%）；涵蓋影格數相同（605/619）。
- **信心分數**：on 平均 0.8700、off 平均 0.8530（on 只高 2.0%）；低信心（<0.5）比例 on 8.57% vs off 8.13%，off 反而略低。
- **逐影格文字集合比較**：605 個共同影格中 18.2% 完全相同；denoise_off 多抓到額外文字（如頁碼、符號）的影格數（116）反而比 denoise_on（77）多，方向不一致，代表 denoise 沒有穩定地提升細節辨識。
- **Phase 1 耗時**（619 影格，兩版本共用）：27.85s（45.0 ms/影格）。
- **Phase 2 前處理耗時**：denoise_on 122.82s vs denoise_off 11.85s（相差 10.4 倍）。
- **Phase 3 OCR 耗時**（乾淨重跑，不含模型下載）：denoise_on 總計 206.83s（初始化 1.42s + 逐影格辨識 205.42s，331.9 ms/影格）；denoise_off 總計 206.32s（初始化 1.35s + 逐影格辨識 204.97s，331.1 ms/影格）——兩者幾乎相同（差 0.25%），代表 OCR 推論本身耗時不受前處理是否去雜訊影響。
- **完整「觸發到結果」總時間**（Phase 1 + 2 + 3 加總）：denoise_on = 27.85 + 122.82 + 206.83 = **357.50s**；denoise_off = 27.85 + 11.85 + 206.32 = **246.02s**。denoise_off 整體快 31.2%（快 111.48 秒），差異完全來自 Phase 2。

**決策更新（2026-07-25，使用者指示）**：denoise 開關的最終決定，**與 Phase 5 三通道比較一起，留到專案尾聲再依完整數據決定**，不在此時定案。兩個版本（denoise_on / denoise_off）的資料與統計皆保留，`scripts/run_phase2.py` 預設的 `--denoise both` 機制與現有 `config/settings.py` 中的 `PREPROCESS_PARAMS["denoise"]` 暫不更動。上述數據（品質差異約 2%、遠低於 15% 門檻；总時間 denoise_off 快 31.2%）先記錄在案，留待專案尾聲一併納入決策。

## 13. Phase 5 規劃：三通道 NLP 架構（2026-07-25，使用者已確認架構方向，尚未開始實作）

使用者要求將「OCR 文字 → 結構化輸出」這段拆成 3 個獨立通道，各自蒐集數據（時間、辨識文字、代理準確度指標等），三通道彼此在流程與時間序上都要獨立、不衝突，直到專案尾聲再依數據決定留哪個通道／模組。**完整規劃內容見獨立文件 `PHASE5_MULTI_CHANNEL_PLAN.md`，程式碼尚未撰寫，等使用者下令才開始實作。** 此處只記錄關鍵確認決策，供快速查閱。

### 13.1 已確認的架構決策

| 決策點 | 確認結果 |
|---|---|
| Regex 範圍與時機 | 只保留韓文字元，作用在 **OCR 原始輸出上**，清理完才進入後續查字典/輸出流程，兩者不衝突。 |
| 去除重複字詞 | 指**跨影格重複字句**（沿用既有 `src/dedup/deduplicator.py`，Step 5 模組，不重寫）；同句內字元重複則交給 KoNLPy 斷詞處理即可，不需要額外邏輯。 |
| Channel 1 範圍 | KoNLPy 五個斷詞引擎（Okt/Komoran/Kkma/Hannanum/Mecab-ko）**各自視為一個子通道**，全部都跑、都記錄統計數據，供比較（各引擎速度/安裝差異見 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 2 節）。 |
| 字典索引 | 開發/測試階段建立一次索引快取即可，不影響成品執行效能。 |
| 詞義消歧 | 同形詞/多義詞全部列出（不挑一個）；查無中文對應則翻譯欄位直接留空，不做其他 fallback（Channel 1 本身）。 |
| Channel 2 本地 LLM | 已確認推薦方案：**Ollama + `qwen2.5:7b`**（4.7GB，官方庫可直接 `ollama pull`，多語含韓文能力已驗證），備選 `qwen3:8b` 或手動匯入韓文專門微調模型 `Bllossom-8B`。 |
| Channel 3 觸發條件 | KoNLPy 將詞彙拆為破碎單字、或整段判為名詞，且字典查無此寫法 → 送 LLM 依上下文推測正確字詞 → 猜到就重新查字典、回原流程；猜不到就跳過該段（不輸出），記錄一筆 fallback 失敗。 |
| 執行隔離 | 三通道／子通道依序執行、不同時跑，避免 OCR／KoNLPy／本地 LLM 同時佔用同一張 GPU 顯存。 |
| 準確度指標 | 目前先用「**字典命中率**」作為代理指標，不依賴人工標註 ground truth。 |

### 13.2 字典檔案調查結果（`韩中字典xml/`，已用程式檢視結構，非人工判讀）

- 實際格式為 **11 個 LMF XML 檔**（非 JSON，先前規劃筆誤已更正），共約 **5.66 萬筆 `LexicalEntry`**，來源為國立國語院《한국어기초사전》多語對照資料。
- 每個詞條含：韓文寫法（`Lemma.writtenForm`）、詞性（`partOfSpeech`）、難度分級（`vocabularyLevel`）、同形異義編號（`homonym_number`）；每個 `Sense` 含韓文釋義、韓文例句（`SenseExample`，僅韓文無中文對照）、多語 `Equivalent`（`language="중국어"` 即中文翻譯，部分詞條為「無對應詞彙」）。
- **已知限制**：例句沒有中文對照，Channel 1 例句欄位只能給韓文原句；翻譯欄位取自 Equivalent 中文釋義，查無則留空（見 13.1 決策）。
- **效能考量**：11 個檔案合計約 370MB，不能每次啟動都重新解析 XML，規劃建索引快取（SQLite），一次建立即可重複使用。

### 13.3 詳細規劃

完整的三通道流程圖、KoNLPy 五引擎比較表、Mecab-ko 於 WSL2 的安裝步驟、Ollama/Qwen2.5 安裝步驟、RunReport 統計欄位設計、建議實作順序，皆已寫入 **`PHASE5_MULTI_CHANNEL_PLAN.md`**，此處不重複列出以避免兩份文件內容不同步。

### 13.4 已確認：Channel 3 選型（2026-07-25）

Channel 3 維持單一版本，不比照 Channel 1 針對五個引擎各跑一次，固定使用**速度最快的引擎 Mecab-ko**（KoNLPy 官方基準測試 0.28s/100K 字元，遠快於其餘四個引擎，見 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 2 節）。

### 13.5 環境建制進度（2026-07-25，沙盒 + 使用者本機皆已驗證）

使用者下令開始 Phase 5 環境建制。沙盒沒有 GPU，但 KoNLPy 的四個純 Java 引擎不需要 GPU，已在沙盒**真實安裝並驗證**（非 mock，JDK 11，實際跑出斷詞結果）：Okt、Komoran、Kkma、Hannanum 皆正常運作，共 4/5（Mecab-ko 沙盒當時無法驗證）。

**使用者本機（WSL2，JDK 21.0.10）實測結果與沙盒不同，共 3/5**：

- Okt / Komoran / Kkma：✅ 正常。
- Hannanum：❌ 丟出 `NullPointerException`。原先懷疑是**單純的 JDK 17/21 相容性問題**（底層 `kr.lucypark.jhannanum` 套件內部用舊寫法 `getProtectionDomain().getCodeSource().getLocation()` 尋找自身資源路徑，在新版 JDK 下該呼叫回傳 `null` 而失效；沙盒為 JDK 11 故未重現）。使用者實測用 `sudo update-alternatives --config java` 把系統預設 `java` 切到 JDK 11.0.31（`java -version` 確認顯示 11）、以及明確 `export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64` 兩種方式，重跑後 Hannanum **都以完全相同的錯誤失敗**，證明根因不是「切換 `java` 指令或 `JAVA_HOME` 指向哪個版本」這麼單純。**使用者決定（2026-07-26）：正式放棄 Hannanum，不再追查根因，後續所有計畫與實作皆排除此引擎**（不影響其餘引擎與 Channel 3）。
- Mecab-ko：使用者一開始依原規劃嘗試 bitbucket 原始碼手動編譯（`mecab-0.996-ko-0.9.2` + `mecab-ko-dic-2.1.1-20180720`），過程中終端機貼上內容有錯亂，且編譯完成後重跑 `check_konlpy_engines.py` 仍顯示 `[未安裝]`。改為 `pip install python-mecab-ko` 後，套件本身安裝成功（`python-mecab-ko-1.3.7` + `python-mecab-ko-dic-2.1.1.post2`），但因舊版 `check_konlpy_engines.py` 只測試 `konlpy.tag.Mecab` 路徑（未偵測 `python-mecab-ko` 自身 API），仍誤報未安裝。**已修正**：`check_mecab()` 改為優先呼叫 `python-mecab-ko` 的原生 API（`from mecab import MeCab`），此路徑在沙盒實測（初始化 0.000s、斷詞 0.33ms，結果正確）與使用者本機的套件安裝狀態下都應可正確回報 `[OK]`，不再需要手動編譯步驟。

**結論**：Mecab-ko 的建議安裝方式已從「bitbucket 原始碼手動編譯」改為「`pip install python-mecab-ko`」（更簡單、不需編譯，已寫入 `requirements.txt` 正式依賴），手動編譯僅保留為 `LOCAL_TESTING.md` 中的備用方案。Hannanum 已確定放棄使用（見上），Channel 1 正式定案為 4 個子通道（Okt/Komoran/Kkma/Mecab-ko），不影響 Channel 3（固定用 Mecab-ko）。

另外，使用者本機執行 Ollama 安裝腳本時遇到 `ERROR: This version requires zstd for extraction`，解法為先執行 `sudo apt-get install -y zstd` 再重跑安裝腳本，已寫入 `LOCAL_TESTING.md` C 節。Mecab-ko 備用編譯方案與 Ollama 所需的網域（bitbucket.org、ollama.com）仍被沙盒網路白名單擋下，且沙盒無 sudo 權限，這兩項的實際安裝驗證**必須在使用者本機完成**（Ollama 部分待 zstd 修正後由使用者重跑確認）。

修改檔案：
- `scripts/check_konlpy_engines.py`：`check_mecab()` 改為優先嘗試 `python-mecab-ko` 原生 API，失敗才退回 `konlpy.tag.Mecab`；docstring 補充 Hannanum JDK21 已知問題說明。
- `requirements.txt`：`python-mecab-ko>=1.3.7` 由註解改為正式依賴；JPype1 註解更新為反映實測結果（沙盒 4/5、本機 3/5 因 Hannanum JDK21 問題）。
- `LOCAL_TESTING.md`：B 節改為以 `pip install python-mecab-ko` 為主，手動編譯列為摺疊備用方案；C 節加入 `sudo apt-get install -y zstd` 修復步驟；A 節與疑難排解表加入 Hannanum JDK21 已知問題說明。

### 13.6 環境建制最終確認（2026-07-25，使用者本機重跑）

使用者依修正後的 `check_konlpy_engines.py` 重跑，並完成 Ollama 安裝，也嘗試切換 JDK 版本排除 Hannanum 問題，結果：

- **KoNLPy：4/5 引擎可用** — Okt、Komoran、Kkma、**Mecab-ko（走 `python-mecab-ko` 原生 API，初始化 0.006-0.036s，斷詞 13.9-16.1ms，結果正確）**皆為 `[OK]`。
- **Hannanum：已確定放棄，不再追查**。使用者已試過兩種修法：（1）`sudo update-alternatives --config java` 切到 JDK 11.0.31；（2）明確 `export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64`。兩者重跑後 Hannanum 都丟出完全相同的 `NullPointerException`，證明根因不是 JDK 版本選擇（也不是 JPype JVM 路徑偵測問題）。**使用者決定（2026-07-26）：忽略 Hannanum 這個引擎，後續所有計畫與實作皆不再包含它**。Channel 1 正式定案為 **4 個子通道**：Okt、Komoran、Kkma、Mecab-ko。
- **Ollama + Qwen2.5:7b：已完成並驗證**。`sudo apt-get install -y zstd` 解決安裝腳本報錯後，`ollama pull qwen2.5:7b` 成功下載（4.7GB），`ollama run qwen2.5:7b "안녕하세요, 테스트입니다."` 正確輸出通順的韓文回應，`nvidia-smi` 確認顯存用量由閒置 1435MiB 升至 6058MiB，證實有使用 GPU。確認 Channel 2/3 所需的本地 LLM 執行環境已就緒。
- **GPU / 測試套件**：`nvidia-smi` 確認 RTX 4060（Driver 591.74、CUDA 13.1）正常；`pytest tests/ -q` 在使用者本機也是 13 項全過。

**結論：Phase 5 環境建制已全部完成。** Channel 1 四個子通道（Okt/Komoran/Kkma/Mecab-ko，Hannanum 已正式排除）、Channel 2（Ollama + qwen2.5:7b）、Channel 3（固定用 Mecab-ko）所需執行環境皆已在使用者本機驗證可用，無待解決事項。使用者已下令繼續下一步，開始 Phase 5 **模組程式碼實作**（依 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 7 節建議順序，第一步為字典索引 `scripts/build_dictionary_index.py` + `src/nlp/dictionary.py`）。

### 13.7 模組實作：字典索引 + 查詢（2026-07-26，已完成）

第一步 `scripts/build_dictionary_index.py` + `src/nlp/dictionary.py` 已完成並對全部 11 個真實 XML 檔實測（56,555 筆詞條、76,833 筆詞義、826,505 筆多語翻譯，索引檔約 219MB）。詳細規格、真實查詢結果範例、以及過程中發現並修正的兩個真實資料品質問題（entry_id 並非唯一、XML 檔內混有非法控制字元），皆記錄於 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 12.1 節，此處不重複列出。新增測試 9 項（`test_build_dictionary_index.py` 4 項、`test_dictionary.py` 5 項）。

### 13.8 模組實作：Regex 清理 + 執行報告 schema（2026-07-26，已完成）

第二步 `src/nlp/text_cleaner.py`（只留韓文字元 + 空白，使用者確認不保留標點）與 `src/nlp/stats.py`（`RunReport` + `RunReportBuilder`，輸出格式使用者確認為 CSV）已完成，詳細設計見 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 12.2 節。新增測試 14 項。

### 13.9 模組實作：Channel 1 runner + 四引擎模擬測試（2026-07-26，已完成）

第三步 `src/nlp/tokenizer.py`（統一斷詞介面）+ `scripts/run_channel1.py`（Channel 1 完整流程：OCR 原文 → 清理 → 去重 → 斷詞 → 查字典 → 結構化輸出）已完成，並在沙盒環境對**真實 OCR 辨識資料**（`data/output/001/ocr_on/ocr_results.csv`，使用者本機真實 GPU 跑出的 3326 筆結果）跑完 Okt / Komoran / Kkma / Mecab-ko 四個子通道的完整模擬測試（沙盒本身即有可用的 JDK 11 + KoNLPy + python-mecab-ko，故能真實執行，非 mock）。四引擎字典命中率相近（88-90%），Mecab-ko 總耗時最短。詳細數據表格、實測發現的引擎間真實差異（Okt 不拆語幹/語尾，導致部分動詞/形容詞辭典形還原失敗），皆記錄於 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 12.3 節。新增測試 8 項。

### 13.10 模組實作：Channel 2（llm_client.py + Channel 2 runner）（2026-07-26，已完成）

第四步 `src/nlp/llm_client.py`（`OllamaClient`，抽象 LLM 呼叫介面）+ `src/nlp/llm_annotator.py`（prompt 設計＋JSON 解析容錯）+ `scripts/run_channel2.py`（完整流程：OCR 原文 → 清理 → 去重 → 整句交給 LLM → 結構化輸出）已完成。

**沙盒沒有真正的 Ollama**（`ollama.com` 被沙盒網路白名單擋下），所以比照 Phase 3 GPU 檢查邏輯的驗證模式，寫了一個臨時的假 Ollama HTTP 伺服器讓 `run_channel2.py` 跑一次完整流程驗證（讀檔→清理→去重→呼叫 LLM→解析→寫檔），確認 2008 句字幕、2008 次呼叫、0 次解析失敗，控制流程完全正確；但**這次模擬測試的翻譯/例句內容是假伺服器規則生成的佔位文字，不是真正 `qwen2.5:7b` 的輸出，不代表真實品質**，測試用的假伺服器與這批假輸出資料都沒有同步到專案資料夾。真實品質驗證需要使用者在已裝好 Ollama + qwen2.5:7b 的本機執行 `scripts/run_channel2.py`。詳見 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 12.4 節。

新增測試 16 項（含 `OllamaClient` 的 mock 測試、`llm_annotator` 的 FakeLLMClient 測試）。全專案測試共 **56 項全過**。

**使用者本機真實驗證（2026-07-26）**：`requests` 套件需另外 `pip install`（已補進 `requirements.txt`，先前漏裝）；補裝後對真實資料實測，總耗時 3591.24s、2008 次呼叫中 2001 次成功解析／7 次失敗、4401 個詞彙中 3011 個有翻譯（68.4%，低於 Channel 1 的 88-90%，符合預期，LLM 未經字典驗證）。詳細數據與跟假伺服器模擬結果的對比記錄於 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 12.5 節。

### 13.11 模組實作：Channel 3（混合通道）（2026-07-26，已完成）

第五步 `src/nlp/llm_fallback.py`（fallback 推測 prompt + 解析）+ `scripts/run_channel3.py`（Channel 1 架構固定 Mecab-ko，字典查無結果才呼叫 LLM 推測）已完成。三層測試驗證：單元測試（FakeLLMClient）、用小型合成字典驗證「成功挽回／確實失敗／字典本身命中不觸發 LLM」三種情境、以及沙盒對真實資料的控制流程模擬（假伺服器一律回應「猜不到」，驗證最壞情境下 Channel 3 正確退化為與 Channel 1 Mecab-ko 完全相同的結果：2784 詞彙、2471 命中、313 次 fallback 全部失敗，313=2784-2471 數字吻合）。真實 LLM 推測成功率待使用者本機驗證。詳見 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 12.6 節。新增測試 8 項。全專案測試共 **64 項全過**。

**至此，Phase 5 三通道（Channel 1/2/3）+ 所有共用元件的模組程式碼皆已完成**，下一步為使用者本機執行真實驗證（尤其 Channel 3 的真實 fallback 挽回率），以及更多真實影片素材的批次測試，最終於專案尾聲決定通道/子通道去留。

### 13.12 Phase 0-5 全流程驗收：10 支真實影片（2026-07-26，使用者本機，`scripts/_pipeline_smoke_test.py`）

使用者建立臨時驗收腳本並對 `raw/` 全部 10 支影片跑過 Phase 1→2→3→Channel 1（4 引擎）→Channel 3，**80 個階段紀錄全數成功**。詳細分析（詳見 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 12.8 節）：

1. **統計邏輯無 bug**：10 支影片逐一核對，channel3 的 `dict_hit_count` 恆等於「channel1_mecab 命中數 + fallback 成功數」，無一例外；匯出資料看似大量重複列，納入時間戳記後即為預期的詞彙重複出現，非邏輯錯誤。
2. **Channel 3 fallback 真實成本效益偏低**：10 支影片加總 2930 次呼叫僅 50 次成功（1.7%），多花約 912 秒——是通道去留決策的重要數據點。
3. **Channel 1 四引擎加權命中率**：Okt 81.5%、Komoran 86.5%、Kkma 84.7%、Mecab 85.2%（Okt 偏低與已知的詞幹/語尾不切分限制一致）。
4. **影片 009/010 字幕數異常偏少**：研判為「編號詞彙卡」格式素材、與其餘連續對話字幕格式不同，屬素材差異非管線缺陷，仍建議使用者目視確認。
5. **影片 008**：語言內容最豐富、各引擎命中率最低、fallback 次數最多、耗時最長，適合做為品質比較重點案例。

**依使用者訂下的驗收標準，Phase 0-5 可視為功能上已完成**；範圍外未完成項目：Anki 匯出未納入驗收測試、無正式永久單一入口腳本、Phase 6/7/9 未開始、通道/denoise 最終決策與 Channel 2 全量 10 支影片測試仍留待後續。

## 14. 目前進度

- [x] Phase 0：專案骨架、標準化 schema、集中設定、環境建置腳本
- [x] Phase 1：本地影片匯入與影格採樣（已用 10 支真實測試影片驗證，`scripts/run_phase1.py` 可執行）
- [x] Phase 2：影像前處理（全畫面預設、灰階+CLAHE 不二值化、denoise 兩版比較機制，`scripts/run_phase2.py` 可執行）
- [x] Phase 3：OCR GPU 強制檢查邏輯已實作並測試通過；真實素材辨識數據已取得（見第 12 節），denoise 決策留到專案尾聲與 Phase 5 一併決定
- [x] Phase 4：時序去重（`src/dedup/deduplicator.py`；2026-07-27 使用者本機真實測試發現「多處重複」bug 並已修復——原本單一 current_text 追蹤無法處理同一時間畫面多個文字同時出現的情況，改為同時追蹤多個進行中群組，見第 18 節；新增 `tests/test_deduplicator.py` 6 項，全專案 138 項全過；使用者已重新測試並確認：去重修復有效，另有部分「重複項」其實是字典一詞多義的正確輸出、非錯誤，見第 18.5 節）
- [x] Phase 5：三通道 NLP 架構（規劃已確認，見第 13 節與 `PHASE5_MULTI_CHANNEL_PLAN.md`；**環境建制、三通道模組程式碼、以及 10 支真實影片的 Phase 0-5 全流程驗收（80/80 階段成功）皆已完成**——Channel 1（4 個子通道 Okt/Komoran/Kkma/Mecab-ko，Hannanum 已正式排除，10 影片加權命中率 81.5-86.5%）、Channel 2（`llm_client.py`+`llm_annotator.py`+`run_channel2.py`，已用真實 qwen2.5:7b 在使用者本機驗證：3591s／2008 句／68.4% 有翻譯，僅 001 完整驗證）、Channel 3（`llm_fallback.py`+`run_channel3.py`，10 影片加總真實 fallback 挽回率僅 1.7%、多花約 912 秒）皆已完成並以真實資料驗證，見第 13.7-13.12 節，全專案測試 64 項全過；**依使用者訂下的驗收標準功能上已完成，尚餘：Anki 匯出驗收、Channel 2 全量 10 影片測試、專案尾聲通道/denoise 最終決策**）
- [x] Phase 6：後端 API 串接（`src/api/main.py`+`job_store.py`+`pipeline_runner.py`+`results_reader.py` 已實作並經模擬驗證（真實 phase1/2 執行、對真實 001 資料的讀取、發現並修補一項未預期例外安全網缺口），見第 15 節；真實上傳/GPU/Ollama 端到端驗證待使用者本機執行）
- [x] Phase 7：前端介面（`frontend/index.html`+`app.js`+`style.css` 已實作，含核心介面（檔案選取/開始/結果表格含影片截圖/匯出）+ 測試期間便利功能區（環境檢查/參數調整/通道開關/階段耗時），後端同步擴充（denoise 開關/channel1-3 個別開關/channel1 子引擎選擇/config 暫時覆寫/結構化 timestamp/影格截圖端點），皆經沙盒模擬驗證（含真實 HTTP 上傳路徑），見第 16 節；真實瀏覽器操作與真實 GPU/Ollama 端到端驗證待使用者本機執行）
- [x] Phase 8：CSV / Anki 匯出驗證（使用者 2026-07-27 確認：結構與內容皆正確無誤；規格書提到的 Anki 字卡（`.apkg`）匯出格式本身尚未實作/驗證，留待 Phase 9，見第 19.2 節第 3 項）
- [ ] Phase 9：整合測試與 MVP 驗收（規劃見第 19 節；通道/denoise 最終決策已用真實 finaltest 資料完成，見第 20 節——denoise關閉、Channel1預設Komoran、Channel2/3不設為預設；MVP 5項功能整合驗收與其餘 19.2 節項目尚未進行）

## 15. Phase 6：後端 API 串接（2026-07-26，已實作）

### 15.1 開始前的規格不確定性與使用者決策

進入 Phase 6 前，`src/api/main.py` 只有路由骨架（4 個路由皆 `NotImplementedError`），`PROJECT_NOTES.md` 舊版第 3 節只留下一行「路由骨架已建立，實際邏輯串接留待 Phase 6」，沒有任何 request/response schema、job 狀態設計、或部署範圍的規格文件。實作前先逐一列出以下不確定性並請使用者確認：

1. **`/api/upload` 的範圍**：是否要真正支援任意新影片上傳並觸發完整流程？→ **確認**：是，且沙盒用模擬方式驗證控制流程，真實端到端執行（GPU OCR + Ollama）留給使用者本機驗證。
2. **`/api/jobs/{id}/results` 預設回傳哪個/哪些通道**（六組結果 channel1_okt/komoran/kkma/mecab、channel2、channel3，「最終保留哪個通道」已明確延後到專案尾聲）→ **確認**：預設回傳 `channel3`，其餘透過 `?channel=` 查詢參數指定。
3. **工作狀態（job/status）持久化方式**（Channel 2 單支影片耗時可達近 1 小時，需要撐過伺服器重啟）→ **確認**：輕量持久化，SQLite 記錄 job 狀態。
4. **匯出端點是否要一併補上未經測試的 `anki_exporter.py`**→ **確認**：不需要，Anki 本身透過 CSV 匯入，只需支援 `format=csv`。

### 15.2 實作內容

- `config/settings.py`：新增 `API_CONFIG`（job db 路徑、上傳目錄、合法 channel 清單、預設回傳 channel、denoise 模式、LLM 預設模型/位址）。
- `src/api/job_store.py`：`JobStore` 類別，SQLite 兩張表（`jobs` 整體狀態、`job_stages` 各階段成功/失敗/耗時明細），每次操作各自開關連線，避免背景執行緒與主執行緒共用連線的執行緒安全疑慮。
- `src/api/pipeline_runner.py`：`run_full_pipeline()`，比照 `scripts/_pipeline_smoke_test.py` 已驗證過的串接順序（Phase1→2→GPU 檢查→Phase3→Channel1 四引擎/2/3），差異在於寫入 `JobStore` 而非彙整 CSV；`video_id` 直接使用 `job_id`，避免與既有 `raw/001`~`010` 手動測試資料衝突；phase1/2/3/GPU 檢查任一失敗視為整體失敗並停止，Channel 1 四引擎/2/3 彼此獨立、個別失敗不影響其他 channel 繼續嘗試（整體工作仍算 done）。**刻意不重用已過時的 `src/pipeline.py`**（其呼叫的 `src/nlp/analyzer.py`/`translator.py`/`segmenter.py` 三個 Step 6 舊介面仍是 Phase 5 前刻意留白的 stub，Phase 5 已用三通道架構取代，此檔案屬於死碼，未刪除但也未使用，見 README.md 目錄結構說明）。
- `src/api/results_reader.py`：讀取 `data/output/<video_id>/<channel>/export.csv` + `stats/<channel>_report.csv`，轉成 API 回傳的 JSON（NaN 一律轉為空字串）。
- `src/api/main.py`：`create_app()` 工廠函式（可注入 job db / 輸出目錄 / 上傳目錄路徑，方便測試互相隔離），4 個路由皆已實作：
  - `POST /api/upload`（接收檔案、驗證副檔名、存檔、建立 job、背景觸發 `run_full_pipeline`）
  - `GET /api/jobs/{id}/status`（整體狀態 + 各階段明細 + 該影片目前已存在哪些 channel 結果）
  - `GET /api/jobs/{id}/results?channel=`（預設 channel3，404 訊息會附上目前工作狀態方便除錯）
  - `POST /api/jobs/{id}/export?format=csv&channel=`（回傳 export.csv 檔案；`format=anki` 明確回傳 400 並說明理由）

### 15.3 已知沙盒限制

模組層級的預設 `app = create_app()` 在沙盒的 FUSE 掛載輸出目錄下會因 SQLite `disk I/O error` 無法初始化（與 `build_dictionary_index.py` 建索引時遇到的限制同一原因），已用 try/except 包住、退化為 `app = None`，不影響 `create_app()` 函式本身或真正部署（使用者本機一般檔案系統不會有此問題）；測試一律呼叫 `create_app()` 並指定 `tmp_path` 路徑。真正的 GPU OCR / Ollama LLM 呼叫同樣無法在沙盒驗證，`run_full_pipeline` 的控制流程改用注入的假階段函式（`stage_functions` 參數）驗證。

### 15.4 測試

新增 `tests/test_job_store.py`（7 項）、`tests/test_pipeline_runner.py`（7 項）、`tests/test_results_reader.py`（6 項）、`tests/test_api_main.py`（14 項），共新增 34 項，全部使用假的階段函式/背景工作，不需要真正 GPU/Ollama。全專案測試共 **98 項全過**。

### 15.5 待使用者本機驗證

- 真正上傳一支新影片（非 `raw/001`~`010`），確認 `/api/upload` → GPU OCR → Channel 1/2/3 全部跑完、`/api/jobs/{id}/status` 與 `/api/jobs/{id}/results` 回傳內容正確。
- 確認 `uvicorn src.api.main:app` 在本機可正常啟動（沙盒因 SQLite 限制無法驗證這一步，見 15.3 節）。
- Channel 2 全流程納入後單支影片可能耗時近 1 小時，建議先用 `include_channel2=false` 測試流程正確性，再視情況實際跑一次完整版本。

### 15.6 模擬驗證與安全網修補（2026-07-26）

使用者要求「模擬驗證 Phase 6 的架構，確保能夠正確傳出傳入與前端溝通」。用 FastAPI `TestClient` + 直接呼叫 `run_full_pipeline()`（可注入部分真實函式、部分假函式）做以下驗證，皆為真實程式碼執行，非人工判讀：

1. **路由契約**：不支援副檔名（400）、查詢不存在的 job_id（status/results 皆 404）皆正確。
2. **誠實反映沙盒限制的真實路徑**：用真實 `raw/002.mkv` 跑真實 `phase1`+`phase2`（影格擷取、CLAHE 前處理皆真的執行），`gpu_check` 誠實回報沙盒無 GPU（非造假）→ job 正確轉為 `status=failed`、`current_stage=gpu_check`，錯誤訊息清楚，`stages` 明細完整。
3. **Channel 獨立性設計驗證**：假 `phase3`（直接複製一段真實 OCR 結果）+ 真實 Channel 1（4 引擎全部成功）+ 真實 Channel 3（沙盒無 Ollama，fallback 呼叫真的連線失敗）→ Channel 3 該階段記錄失敗，但整體 job 仍正確轉為 `status=done`，Channel 1 的結果仍可正常查詢——確認「channel 彼此獨立、個別失敗不拖垮整體」的設計如預期運作。
4. **對真實 production 資料的讀取**：手動建立一個指向真實已完成的 001 影片的 job，`/api/jobs/{id}/status` 的 `available_channels` 正確列出全部 6 組真實結果；`/api/jobs/{id}/results?channel=...` 對 channel3/channel1_okt/channel2 皆正確回傳真實筆數與統計；`export?format=csv` 正確回傳真實 2.6MB CSV 檔案（正確 `Content-Type`/檔名）；`format=anki` 正確回傳 400。

**發現並修補一項架構缺口**：`run_full_pipeline()` 原本在 `_default_stage_functions()`（匯入六個 Phase/Channel 模組）與 `job_store.update_job(status="running")` 這兩步——這兩步都跑在任何 `_run_stage()` 保護之前——若其中任一步拋出未預期例外（模擬時真的因為沙盒沒裝 `torch` 而觸發過一次；使用者本機已裝 `torch` 不會遇到這個特定原因，但任何其他未預期例外仍有同樣風險），整個背景工作會直接崩潰，job 永遠停在 `queued`、`job_stages` 全空，前端完全查不到失敗原因。

## 16. Phase 7：前端介面 + 測試期間便利功能（2026-07-26，已實作）

### 16.1 需求與開始前確認的不確定性

使用者要求前端須包含：影片檔案選取、開始按鈕、結果顯示（影片截圖／韓文單字／單字詞性／單字翻譯／單字例句）、匯出檔案按鈕；另外要有以下「測試期間方便操作、成品完成後會要求移除」的功能區：一鍵確認環境是否齊全（只顯示有/無）、各參數調整、是否 denoise、是否經過 Channel 1/2/3（Channel 1 可選 4 個子通道之一或多個）、各流程階段耗時。

實作前列出以下不確定性並請使用者確認：

1. **denoise 開關／Channel 1/2/3 個別開關／Channel 1 子引擎選擇，Phase 6 完全不支援**（denoise 寫死開啟、Channel 1 永遠跑滿 4 引擎、Channel 3 永遠執行）→ **確認**：一併擴充後端，讓這些開關真正生效（不是純前端裝飾），使用者也已預告成品完成後會要求移除/簡化這些欄位。
2. **環境檢查要包含哪些項目** → **確認**：GPU/CUDA、Ollama 連線、KoNLPy 4 引擎+Mecab-ko、字典索引檔是否存在，另外加上「Python、Java 以及其他開發所需環境」→ 實作為：Python 版本、`java -version`、以及 8 個關鍵 Python 套件（torch/cv2/easyocr/requests/fastapi/pydantic/konlpy/mecab）逐一 `importlib.import_module` 驗證。
3. **每個單字旁的「影片截圖」要顯示什麼**——`export.csv` 只有塞在備註文字裡的時間戳記，沒有結構化欄位，也沒有任何服務影格圖片的端點 → **確認**：顯示對應時間戳記的真實 OCR 影格，需新增結構化 timestamp 欄位 + 新增影格圖片服務端點。
4. **「各參數調整」具體要調整哪些** → **確認**：取樣率(FPS)／最大影格數、LLM 模型名稱／Ollama 位址、OCR 最低信心值／去重時間間隔、CLAHE 對比強化強度／去雜訊強度。

### 16.2 實作內容

- **`src/api/environment_check.py`**（新增，獨立檔案，之後要整個移除只需刪這個檔案 + `main.py` 裡對應的一個路由）：`check_python()`／`check_gpu()`／`check_java()`／`check_konlpy_engines()`（重用既有 `scripts/check_konlpy_engines.py` 的 `check_java_engines()`/`check_mecab()`，不重複實作，Hannanum 不列入）／`check_ollama()`／`check_dictionary_index()`／`check_python_packages()`，彙整為 `check_environment()`，每項檢查各自 try/except，回傳 `[{"name","ok","detail"}, ...]`。`GET /api/environment` 路由（`main.py`）呼叫並回傳 JSON。
- **`src/api/pipeline_runner.py` 擴充**：新增參數 `denoise`／`include_channel1`／`channel1_engines`／`include_channel3`／`config_overrides`。其中 `min_confidence`/`dedup_max_gap_sec`/`clahe_clip_limit`/`denoise_strength` 目前分散在 `preprocessing/pipeline.py`／`ocr/recognizer.py`／`dedup/deduplicator.py` 內部直接讀取全域設定字典（非函式參數），改用新的 `_temporary_settings_override()` context manager：執行前暫時覆寫 `config/settings.py` 的全域字典值、執行後（含例外時）一律還原，避免重構這幾個底層模組介面——風險最小，且完全符合「測試期間功能，之後會移除」的定位；已知限制：對整個行程共用的設定物件生效，若同時有兩個工作平行執行且指定不同的 override 會互相干擾（單一使用者本機工具不會遇到，且拿掉本功能後這個限制也一併消失，已記錄在模組 docstring）。
- **`src/api/main.py` 的 `/api/upload`** 新增對應 Form 參數並轉呈給 `run_full_pipeline()`；`channel1_engines` 接受逗號分隔字串（如 `"okt,mecab"`）。
- **`src/api/results_reader.py` 擴充**：新增 `_extract_timestamp_range()`（正規表達式從 `備註` 解析 `"字幕 X.Xs-Y.Ys"`，不改動既有三個 channel runner 的匯出格式，避免既有 10 支影片的真實資料作廢）+ `resolve_frame_path()`（讀取 `frames/manifest.csv`，找時間戳記最接近的原始截圖，非 Phase 2 前處理後的灰階版本，更容易辨識）。`read_channel_results()` 回傳的每筆紀錄新增 `timestamp_start`/`timestamp_end` 欄位。新增 `GET /api/jobs/{job_id}/frame?timestamp=` 路由。
- **`frontend/index.html` + `app.js` + `style.css`**（純 HTML/CSS/JS，無建置流程）：核心介面（檔案選取／開始／結果表格／匯出）+ 明顯用虛線框與底色區隔的測試工具區（環境檢查、參數調整、通道開關、階段耗時表格），兩者程式碼與 DOM 結構完全分離，之後移除測試工具區不影響核心介面。`main.py` 的 `create_app()` 新增 `app.mount("/", StaticFiles(...))`（放在所有 `/api/*` 路由註冊之後，確保不會攔截 API 請求），讓 `uvicorn src.api.main:app` 啟動後直接開 `http://localhost:8000/` 就能用，與 API 同源、避免 CORS/file:// 問題。

### 16.3 沙盒模擬中意外發現：JPype/JVM 在背景執行緒啟動會導致行程無法正常結束（非功能性 bug，已記錄非修補）

在幫 `/api/environment` 寫測試時，透過 `TestClient` 呼叫會觸發 KoNLPy（Okt/Komoran/Kkma，底層透過 JPype 啟動 JVM）的背景執行緒場景，發現：該次請求本身正確回應（狀態碼、內容皆正確），但整個 Python 行程之後卡住、無法正常結束（需要外部 kill）。進一步排查（見暫存測試腳本）：

- 直接在主執行緒呼叫 `check_konlpy_engines()`：正常結束（exit code 0）。
- 用 `threading.Thread` 在背景執行緒呼叫同一函式：函式本身執行完成（能看到完整輸出），但行程之後卡住。
- 用最小 FastAPI app + `BackgroundTasks` 重現同樣情況：背景工作本身完成、`/go` 的回應正確，且之後對同一伺服器連續呼叫 5 次其他路由都正常回應（**伺服器持續運作正常，不是功能性卡死**）；只有整個 Python 行程要結束時才會卡住。

**結論**：這是 JPype 啟動 JVM 時的執行緒依附（thread affinity）已知限制類型的行為，只影響「乾淨結束行程」（例如 `uvicorn` 收到 Ctrl+C/SIGTERM 時的優雅關閉，可能需要按兩次或改用強制關閉），**不影響伺服器實際處理請求的正確性**（已用連續 5 次請求驗證）。因為：(a) 這不影響任何功能正確性，(b) 修正需要更動 KoNLPy/JPype 的使用方式或改在子行程執行，屬於較大幅度的架構調整，不符合目前投入產出比；因此**這裡選擇記錄下來、不修補**，並在測試套件裡透過 monkeypatch 假的 `check_environment()`（`tests/test_api_main.py`）與只在主執行緒直接測試真正邏輯（`tests/test_environment_check.py`）避開這個限制，確保測試套件本身不會被拖累卡住。使用者本機若也遇到 `uvicorn` 關閉時卡住，屬已知現象，多按一次 Ctrl+C 或直接關閉終端機視窗即可。

### 16.4 模擬驗證（2026-07-26，沙盒，皆為真實程式碼執行）

1. `denoise=False` 真實跑 `phase1`+`phase2`：驗證 `phase3` 真的收到 `processed/denoise_off` 路徑（而非寫死的 `denoise_on`）。
2. `channel1_engines=["okt","mecab"]`：驗證只有這兩個子通道被執行、`komoran`/`kkma` 完全沒被觸發。
3. `include_channel1=False`：驗證 Channel 1 完全不會被呼叫。
4. 對真實已完成的 001 影片資料呼叫 `GET /api/jobs/{id}/results`：確認新增的 `timestamp_start`/`timestamp_end` 欄位正確解析（例如 `15.0`/`15.0`），並用該時間戳記呼叫 `GET /api/jobs/{id}/frame`，成功取回一張真實 102KB JPEG 影格。
5. 真正透過 HTTP `POST /api/upload`（multipart form，非直接呼叫 Python 函式）上傳真實 `raw/002.mkv`，帶入 `denoise=false`／`max_frames=10`／`channel1_engines=mecab`／`include_channel2=false`／`include_channel3=false`：確認整條路徑（表單解析 → 背景工作 → 安全網）都運作正常——沙盒沒有 `torch`，在 `phase3` 匯入階段被 16.3 節之前（Phase 6 §15.6）新增的安全網正確接住，job 明確轉為 `status=failed` 並附上清楚錯誤訊息，而非卡住。

新增測試：`tests/test_environment_check.py`（7 項）、`tests/test_pipeline_runner.py` 新增 6 項（denoise/channel 開關/子引擎/config_overrides 相關）、`tests/test_results_reader.py` 新增 5 項（timestamp 解析＋frame 端點）、`tests/test_api_main.py` 新增 9 項（environment 路由、upload 新參數轉呈、frame 路由）。全專案測試共 **126 項全過**。

### 16.5 待使用者本機驗證

- 啟動 `uvicorn src.api.main:app --reload`，瀏覽器開啟 `http://localhost:8000/` 確認頁面正常顯示。
- 真正選一支新影片、按「開始」，確認整個流程（含真實 GPU OCR、真實 Ollama）都能透過網頁完成，結果表格與影片截圖正確顯示。
- 試按「一鍵確認環境是否齊全」，確認回報內容與本機實際安裝狀況相符。
- 確認 `uvicorn` 關閉時是否真的會遇到 16.3 節描述的卡住現象；若會，屬已知限制，多按一次 Ctrl+C 即可。

## 17. 使用者本機真實測試發現的兩個問題（2026-07-27，已修復）

使用者在真實環境啟動 `uvicorn src.api.main:app --reload` 並實際操作網頁介面（一鍵環境檢查、Channel 1 單/多引擎、Channel 2、Channel 3）時，依序發現並回報以下兩個問題。

### 17.1 問題一：缺少 `python-multipart`，`create_app()` 建立失敗但完全沒有錯誤訊息

**現象**：網頁打開後顯示「Internal Server Error」，終端機只看到 `TypeError: 'NoneType' object is not callable`，看不出真正原因。

**根本原因**（已在沙盒直接重現確認，非猜測）：`requirements.txt` 已列出 `python-multipart>=0.0.9`（Phase 6 時 `/api/upload` 需要 `File`/`Form` 就已經加入），但使用者的 venv 沒有安裝。經實測確認：這個套件缺少時，甚至只是 `from fastapi import ...` 這一行就會直接 `ImportError`（Starlette 的 `requests.py` 在最上層就 `import python_multipart`），導致 `main.py` 裡 `app = create_app()` 的 try/except 整個吃下這個例外、退化為 `app = None`。

**修復**：
1. 使用者端修復：`pip install python-multipart`（或重新 `pip install -r requirements.txt`）。
2. 程式端修復：`main.py` 最外層那個原本「完全靜默」的 `except Exception: app = None`（原本是為了容忍沙盒 FUSE 掛載目錄的 SQLite 已知限制而設計，見第 15.3 節），改為**先把完整 traceback 印到 stderr 再退回 `app = None`**——沙盒的已知限制依然不會讓整個模組匯入失敗，但使用者本機以後若因為任何原因（缺套件、設定錯誤等）真的建立失敗，終端機會直接看到清楚的錯誤內容，不會再像這次一樣被完全吃掉、查不出原因。

### 17.2 問題二：上傳 AV1 編碼影片，OCR 全部辨識出 0 筆結果，讀取結果時 API 出現 500

**現象**：環境檢查、Channel 1 單/多引擎、Channel 2、Channel 3 都跑完顯示「狀態：done｜目前階段：finished」，但結果與匯出檔案都是空的；瀏覽結果時 API 回傳 500，終端機顯示 `pandas.errors.EmptyDataError: No columns to parse from file`。

**根本原因**（已在真實 log 中確認，非猜測）：使用者上傳的測試影片是 **AV1 編碼**，終端機清楚顯示：

```
[av1 @ 0x...] Your platform doesn't support hardware accelerated AV1 decoding.
[av1 @ 0x...] Failed to get pixel format.
[av1 @ 0x...] Get current frame error
[完成] 共輸出 0 張影格...
```

這是目前 WSL2 環境下 OpenCV 所用的 ffmpeg 建置無法解碼 AV1 造成的，**不是 Phase 6/7 程式邏輯的錯誤**——Phase 1 沒有拋出任何例外，只是真的一張影格都擷取不到。但因為沒有任何攔截機制，流程照樣一路空跑完 Phase 2/3/Channel 1-3，最後在讀取結果時才因為「空白 CSV 讀不出欄位名稱」而在 API 層炸開一個難懂的 500 錯誤。

**修復（三處，全部已測試驗證）**：
1. `src/export/csv_exporter.py`：`export_csv([], ...)` 原本會寫出「連欄位名稱都沒有」的 CSV；改為固定寫入 `EXPORT_COLUMNS`（原文/中文/詞性/例句/備註）標題列，即使 0 筆資料也是一份合法、可被 `pd.read_csv()` 正常讀回的檔案。
2. `src/api/results_reader.py`：`read_channel_results()` 額外用 `except pd.errors.EmptyDataError` 接住「更誇張地」完全空白的檔案（保護使用者在這次修復生效「之前」已經產生的舊檔案），一律回傳 `record_count=0` 而不是讓 API 500。
3. `src/api/pipeline_runner.py`：新增 `_count_manifest_rows()`，在 Phase 1 一結束就檢查 `frames/manifest.csv` 是否真的擷取到影格；若為 0，立刻攔截為 `status="failed"`、`current_stage="phase1_frame_check"`，並附上明確訊息（提示可能是編碼格式不支援，建議改用 H.264/H.265），不再讓整條流程空跑 Phase 2/3/Channel 1-3 之後才在讀取結果時才發現問題。

**建議使用者**：換一支 H.264 或 H.265 編碼的影片重新測試（`raw/001.mkv`～`010.mkv` 這 10 支既有測試影片先前皆確認可正常運作，應該不是 AV1）；若手上的素材大多是 AV1 編碼，之後可能需要另外確認 WSL2 環境的 ffmpeg 是否能安裝支援 AV1 硬解/軟解的版本（例如透過 conda-forge 的 ffmpeg 或系統套件更新），這部分待使用者需要時再進一步處理。

新增測試：`tests/test_csv_exporter.py`（3 項，新檔案）、`tests/test_pipeline_runner.py` 新增 2 項（0 張影格攔截）、`tests/test_results_reader.py` 新增 1 項（完全空白檔案的防禦性讀取）。全專案測試共 **132 項全過**。

## 18. Phase 4 時序去重 bug（2026-07-27，使用者本機真實測試發現，已修復）

**使用者回報**：「Phase 4：時序去重明顯缺失，擷取的字句多處重複」，同時回報 Channel 2「有多數翻譯缺失以及少數錯誤」，並詢問兩者是否有優化空間；另確認 Phase 8（CSV/Anki 匯出）格式驗證已完成、只需確認內容正確性。

### 18.1 診斷（皆用真實資料與真實程式碼，未憑空判斷）

用 `data/output/50f108b80fcd4b3ca8b5467cf12f7760`（對應 `raw/001.mkv`，含真實 Channel 2 輸出）追查：

- **`src/dedup/deduplicator.py` 舊版根本原因**：`deduplicate()` 只用單一個 `current_text` 變數追蹤「目前進行中的一組」，一次只能合併一種文字。但真實影格（單字卡風格影片）常常同時有多個文字同時顯示在畫面上——例如 15-28 秒這段，`학원／대학교／학교／학생` 四個字同時在畫面上，OCR 每一格都依序輸出這四筆結果。舊版邏輯只要文字一換就會把「目前這組」收尾，等到同一個字下一次出現時，`current_text` 已經是別的字，於是被誤判成全新一組。
- **量化證據**：真實 `channel2/export.csv` 裡，`학원` 一字在 15-28 秒之間（幾乎每一格都偵測到）被拆成 **43 筆**零長度（start=end，單一影格）的獨立紀錄，完全沒有合併；`대학교`／`학교`／`학생` 同樣的模式。呼叫鏈確認：`scripts/run_channel1.py`/`run_channel2.py`/`run_channel3.py` 都是 `load_ocr_results()`（只依 `timestamp_sec` 排序，同時間戳記的多筆文字之間不做任何分組）→ 直接丟給 `deduplicate()`，中間沒有任何依文字或 bbox 分組的前處理，因此這個 bug 會影響全部三個 channel。
- **Channel 2 品質量化**（同一份真實資料，4542 筆中）：31.5%（1429 筆）翻譯欄位空白，但抽樣確認絕大多數是提示詞刻意允許 LLM 對助詞/詞尾（에/을/은/이/여/습/음/입니다/시/들/잘…）留空，屬於設計行為、非錯誤；另有 0.66%（30 筆）是 LLM 產生亂碼/幻覺翻譯（例如「잘comings가ircraft吗？」「SHALL NOT BE LISTED AS IT IS AN AUXILIARY WORD」），這是真正的錯誤，且目前完全沒有輸出內容驗證機制；真正的 timeout/JSON 解析失敗只占 0.5%（`error_count=10`／`llm_call_count=1998`）。Channel 3 有字典優先＋LLM fallback 的安全網，Channel 2 是純 LLM、沒有任何備援或事後驗證。

### 18.2 使用者確認的修復方向

診斷後就以下三點徵詢使用者確認（未自行決定）：

1. **去重分組鍵**：只用文字比對，還是文字＋bbox 位置一起比對？→ **使用者選擇「只用文字比對」**（符合目前資料型態：同一字不會同時在畫面兩個不同位置出現）。
2. **Channel 2 優化**：加入輸出內容驗證／加入字典備援／維持現狀？→ **使用者選擇「維持現狀，暫不修改」**，這次先只處理 Phase 4 去重 bug，Channel 2 之後有空再優化。
3. **`max_gap_sec` 門檻**：分組邏輯修正後是否要調整目前的 1.5 秒？→ **使用者選擇「維持 1.5 秒不變」**。

### 18.3 修復內容

`src/dedup/deduplicator.py` 改寫 `deduplicate()`：不再只追蹤單一 `current_text`，改成同時追蹤「多個進行中的群組」（`Dict[str, _OpenGroup]`，鍵＝文字內容）；同一個字只要下一次出現的間隔在 `max_gap_sec`（1.5 秒）內就延續同一組，超過門檻才收尾、之後同一個字再出現視為新的一組。所有輸入結果跑完後，把仍在進行中的群組全部收尾，並依 `start_time` 排序回傳（因為現在多組交錯收尾，順序不再天然照時間排列，需要額外排序這一步）。

**驗證**：
- 新增 `tests/test_deduplicator.py`（此模組先前完全沒有專屬測試檔案），6 項測試涵蓋：同文字在門檻內合併、超過門檻拆成兩組、**重現真實 bug 場景**（4 個字同時輪替出現、驗證各自只合併成 1 組而非 16 組）、輸出依時間排序、平均信心值計算正確、空輸入。
- 直接對真實資料重跑：用修正後的 `deduplicate()` 重新處理 `50f108b80fcd4b3ca8b5467cf12f7760` 的原始 `ocr_results.csv`（3326 筆原始 OCR 結果），`학원／대학교／학교／학생` 四字現在都各自正確合併成 **1 組**、時間範圍 `15.0s-28.0s`（修正前 `학원` 一字是 43 組），去重後總群組數為 145 組。
- 全專案測試套件（含新增 6 項）在沙盒 outputs 與使用者真實工作目錄兩邊皆執行過，**共 138 項全過**。

### 18.4 待使用者本機驗證

使用者提到「時序去重後會再測試一遍」——建議直接對既有真實影片（例如 `001.mkv`）重跑完整流程，確認網頁上顯示的單字列表不再出現同一個字大量重複的零長度項目，且時間戳記/截圖對應正確。Channel 2 品質（空白翻譯／少數亂碼）這次刻意未修改，維持現狀；Phase 8 CSV/Anki 匯出格式本身沒有異動，內容正確性會隨著這次去重修復而改善（因為匯出內容直接來自去重後的結果）。

### 18.5 使用者回饋（2026-07-27）：Phase 8 確認無誤、Phase 4 重複項另有解釋

使用者確認 Phase 8（CSV/Anki 匯出）內容正確無誤。同時補充：重新測試後看到的「重複項」其中一部分並非 bug，而是**字典查詢本身「一詞多義」**——同一個原文字在字典裡對應多筆不同詞義/詞性/例句，正確地各自輸出成一列（例如 `備註` 欄位裡的「同形詞X‧詞義Y」標記，見 `results_reader.py` 模組說明），這是預期行為。18.1-18.3 節修的是另一個不同的根因（同一時間畫面多個文字同時出現、被拆成同一個字跨影格的多筆零長度紀錄），兩者並存但成因不同，皆已個別確認。

## 19. Phase 9 規劃（2026-07-27，尚未開始，先行規劃）

依使用者要求說明 Phase 9（整合測試與 MVP 驗收）的規劃內容。先釐清一件事：**規格書（`專案架構.docx`）對 MVP 的定義只有一份 5 項功能檢查表**（第 4 節「最小可行性產品 (MVP) 範圍」），沒有任何準確率/速度等數字門檻，也完全沒有提到「多通道比較」「denoise 開關決策」「Step 1-8 端到端整合測試」等字眼——這些都是本專案自己在開發過程中額外加上、且明確講好「留到最後」才決定的延伸範圍（見第 258 行、11.1 節等處的記錄），不是規格書本來就要求的。因此 Phase 9 實際上要收斂兩塊性質不同的工作：

### 19.1 規格書要求的 MVP 驗收（5 項功能檢查表，皆已個別完成，尚未「同一次連續執行」驗證過）

規格書 5 項：本地影片檔選取與讀取、影片畫面定頻擷取、畫面文字 OCR 辨識、辨識結果與中文翻譯之可視化顯示、學習數據 CSV 匯出功能。這些在 Phase 0-8 都已個別實作並驗證過，但目前為止都是「各階段分開測試」，尚未做過「使用者在自己機器上，用真實 GPU + Ollama，從頭到尾一次跑完整條路徑不中斷」的驗收：

- 用至少 2-3 支風格不同的影片（例如題目卡 vs 單字卡）各自完整跑一次「選檔案→開始→網頁顯示影片截圖/單字/詞性/翻譯/例句→匯出 CSV」，確認 5 項功能同時成立、沒有卡住或例外中斷。
- 這件事只能在使用者本機執行（需要真實 GPU + Ollama），沙盒無法代勞。

### 19.2 本專案自行延伸、明確留到最後才決定的事項

1. **通道／denoise 最終決策**：Channel 1 四個子引擎、Channel 2、Channel 3、denoise on/off，目前都刻意都保留、留到專案尾聲一起決定。沙盒可以把目前已收集到的真實數據（各通道 dict_hit_rate、Channel 2 空白率/錯誤率、各流程耗時）整理成比較表協助決策，但「最終要保留哪一個當預設值」需要使用者拍板——這也是規格書完全沒定義、需要另外討論決策標準的地方。
2. **Channel 2 全量 10 支影片測試**：目前只有 001 完整跑過真實 Ollama（見第 13 節），要做上面的通道比較，需要使用者本機補跑剩下 9 支。
3. **Anki 匯出**：目前只驗證了 CSV 結構與內容（Phase 8，使用者已確認無誤）；規格書提到的「Anki 字卡」匯出（`.apkg` 或搭配 Anki 的 CSV 匯入）尚未實作/驗證，需要先確認要用哪種格式、是否要在使用者本機真的匯入一次 Anki 驗證卡片顯示正確。
4. **Phase 7 測試面板移除**：使用者在 Phase 7 一開始就說「後續完成版本我會要求刪除修改」——需要使用者明確下指令，是現在（Phase 9 開始前）就拿掉一鍵環境檢查/參數調整/通道開關/耗時列表，還是等全部驗收都過了才拿掉。
5. **全專案回歸測試**：目前 138 項全過，Phase 9 收尾前後都要保持全過，作為最後的 gate。
6. **文件收尾**：`README.md`／`LOCAL_TESTING.md`／`PROJECT_NOTES.md` 更新為反映上述決策後的最終版本（例如拿掉測試面板後的操作說明、最終預設通道/denoise 設定）。

### 19.3 待使用者確認的問題

- 19.2 節 1-4 項的優先順序，是否都要在 Phase 9 做，還是分批？
- 通道/denoise 最終決策要用什麼具體指標比較（例如單純看 dict_hit_rate，還是也要考慮處理時間、Channel 2 錯誤率）？
- Phase 7 測試面板現在就移除，還是等 19.1/19.2 全部跑完才移除？

## 20. Phase 9：通道與 denoise 最終決策（2026-08-29，已用真實最終測試資料決定）

### 20.1 測試方式與範圍

使用者在 `finaltest/`（01.mkv、12.2分鐘；02.mp4、18.7分鐘，皆為 1920x1080 H.264，非 AV1）用 `scripts/run_finaltest.sh` 透過真實 HTTP API（等效網頁操作）完整跑過 Channel1(4引擎)+Channel2+Channel3、denoise on，結果存於 `finaltest/01_result/`、`finaltest/02_result/`、`finaltest/0X_status.json`。

**發現並排除一份過期分析檔**：`finaltest/` 內原本已有 `Phase9_通道與denoise最終決策分析.xlsx`（建立於 2026-08-15，早於這次測試資料產生的時間 2026-08-29），其 Channel2/01.mkv 數據（聲稱耗時311.5秒後失敗）與這次真實 `01_status.json`（實際成功、耗時544.31秒）矛盾，判定為過期/來源不明的檔案，分析時完全未採用其任何數字，改以新檔名 `Phase9_通道與denoise最終決策分析_複核版.xlsx` 呈現、所有數字重新從真實 `status.json`/`stats/*.csv` 讀取計算（並經 LibreOffice 重算、0 個公式錯誤）。

### 20.2 關鍵真實數據

- **Channel 2 可靠度**：01.mkv 成功但耗時 544.31 秒（總管線耗時/影片時長＝136%，已超過影片本身長度）；**02.mp4 執行超過 30 分鐘後 Ollama 直接 `ReadTimeout` 失敗、0 筆輸出**（總管線耗時/影片時長＝233%）。即使成功的那次，翻譯留白率也有 37.8%。
- **Channel 3 fallback 成本效益**：字典命中率比 Channel1-Mecab 單獨只多 +0.23pp（01.mkv）/+0.55pp（02.mp4），但 fallback 成功率僅 1.09%／3.13%（183次呼叫2次成功；543次呼叫17次成功），耗時卻是 Channel1-Mecab 單獨執行的 7.92倍／7.09倍。與歷史 10 支影片數據（fallback 成功率 1.7%、加總多花 912 秒）方向一致。
- **Channel 1 四引擎**：本次 2 支影片加權命中率 Komoran 86.4%＞Kkma 84.5%＞Mecab 81.7%＞Okt 76.1%；與歷史 10 支影片加權命中率（Komoran 86.5%＞Mecab 85.2%＞Kkma 84.7%＞Okt 81.5%）相比，**Komoran 在兩組獨立真實資料中都是第一名**，Okt 都是最後一名。四引擎間耗時差距僅數秒，對總管線耗時影響 <3%，非決策關鍵。
- **Denoise on/off**：沿用 Phase 3、001.mkv 619 影格真實 A/B 測試（PROJECT_NOTES 第 12 節，非本次新測，本次最終測試只跑了 denoise on）——辨識率（信心分數 proxy）提升僅 2.0%，遠低於使用者自訂的 15% 門檻，且偵測數量/低信心比例/逐格文字集合等指標方向不一致支持「on 較好」；總處理時間反而多花 31.2%。本次最終測試（denoise on）中 Phase2 也佔共用階段耗時的 32%～37%，佐證關閉後可省下的時間佔比不小。

### 20.3 最終決策

| 項目 | 決定 |
|---|---|
| Denoise | **關閉（OFF）** |
| Channel 1 引擎 | **Komoran（單一預設引擎）** |
| Channel 3（字典+LLM fallback） | 不建議設為預設 |
| Channel 2（純 LLM） | 不建議設為預設；建議僅列為進階/選用模式，或視資源評估是否下線 |
| 建議最終管線 | Phase1擷取 → Phase2前處理(denoise OFF) → Phase3 OCR → Phase4時序去重 → Channel1(Komoran) → CSV/Anki匯出 |

完整數據、公式與圖表見 `finaltest/Phase9_通道與denoise最終決策分析_複核版.xlsx`（分頁：最終決策／Channel1四引擎比較／Channel2與Channel3成本效益／Denoise開關評估／原始數據）。

### 20.4 待使用者確認/後續動作

- Channel2/Channel3 是「完全從程式碼移除」還是「保留程式碼但前端不預設顯示、列為進階選項」，屬產品範圍決策，本次分析只回答「預設用哪個」，未決定是否刪碼。
- 上面決策定案後，需要實際修改 `frontend/`（拿掉/預設值調整）與 `src/api/pipeline_runner.py` 的預設參數，這部分尚未動工，待使用者確認範圍後再進行。
- 19.2 節其餘項目（Anki 匯出格式、Phase 7 測試面板移除時機、全專案回歸測試）仍待處理。

### 20.5 使用者確認最終規格（2026-08-29）

使用者確認最終規格定案：**Channel 1 選 Komoran、denoise OFF**，與 20.3 節分析結論一致。同時明確指示：**這次先不對程式碼進行修改**——即 `frontend/` 預設值、`src/api/pipeline_runner.py` 預設參數等實作變更，仍維持 20.4 節所述「待後續」狀態，本次僅止於規格定案與紀錄，不進行程式碼異動。Channel2/Channel3 是否從程式碼移除，也尚未決定，維持現狀。
