# Phase 5 規劃：多通道語意處理與比較實驗

本文件記錄 Phase 5（OCR 原始文字 -> 結構化輸出）的架構規劃，經與使用者確認（2026-07-25）。環境建制已於 2026-07-26 全部完成，**使用者已下令開始模組程式碼實作**，目前進行中（見第 7 節建議順序與第 12 節實作進度）。實作時逐項核對本文件、更新為實際狀態。

## 0. 目標與原則

- 用 3 個通道（Channel 1/2/3）分別實作「OCR 原文 -> 結構化輸出」，彼此在程式邏輯與執行時間序上都保持獨立（依序執行、不同時佔用 GPU），直到專案尾聲再依統計數據決定留用哪個/哪些通道與模組。
- Channel 1 底下依 KoNLPy 斷詞引擎各自視為一個子通道，全部都跑、都記錄統計數據。**原規劃 5 個引擎（Okt/Komoran/Kkma/Hannanum/Mecab-ko），Hannanum 已於 2026-07-26 正式排除（環境問題無法解決，使用者決定不再追查），故實際為 4 個子通道：Okt/Komoran/Kkma/Mecab-ko。**
- 準確度先以「字典命中率」為代理指標（無需人工標註 ground truth）。

## 1. 共用元件（三通道都會用到）

| 模組（規劃中，尚未建立） | 用途 |
|---|---|
| `src/nlp/text_cleaner.py` | Regex 清理 OCR 輸出：僅保留韓文字元（範圍待實作時定義 Unicode 區間），在進入斷詞/查字典前執行 |
| `src/dedup/deduplicator.py`（已存在，Phase 1-3 已建好） | 跨影格重複字句去除，三通道共用，不重寫 |
| `src/nlp/dictionary.py` | 讀取索引後的字典，依寫法查詞，回傳所有同形詞/多義詞候選；查無中文對應時翻譯欄位留空 |
| `scripts/build_dictionary_index.py` | 一次性索引腳本：解析 `韩中字典xml/` 11 個 LMF-XML 檔（共約 5.6 萬詞條），建成快速查詢用的索引（規劃用 SQLite，key 為韓文寫法），供 `dictionary.py` 讀取。索引在開發/測試階段建立即可，不影響成品執行效能 |
| `src/nlp/stats.py`（新增 RunReport schema） | 標準化「執行報告」欄位，見第 5 節 |
| `src/nlp/llm_client.py` | LLM 呼叫的抽象介面（本地 Ollama 實作 + 預留外部 API 實作），Channel 2、3 共用 |

## 2. Channel 1：本地套件（每個 KoNLPy 引擎各一子通道）

**流程**：OCR 原文 -> `text_cleaner`（regex 僅留韓文）-> `deduplicator`（沿用既有 Step 5，去除跨影格重複字句）-> 該引擎斷詞 -> `dictionary.py` 查詢（同形詞/多義詞全列出；無中文對應則翻譯欄位空缺）-> 結構化輸出（沿用既有 `ExportRecord` schema，一個詞義候選一列）。

**四個子通道**（KoNLPy 官方 100K 字元基準測試數據，konlpy.org；原規劃五個引擎，**Hannanum 已於 2026-07-26 正式排除**，見第 9-11 節說明）：

| 子通道 | 底層技術 | 速度（100K 字元） | 特性 | 安裝 |
|---|---|---|---|---|
| `channel1_kkma` | 純 Java (JDK+JPype) | 35.72s（最慢） | 標籤最細緻、消歧最好 | `pip install konlpy` + JDK 11+ |
| `channel1_komoran` | 純 Java | 25.60s | 模糊詞保守判為名詞 | 同上 |
| `channel1_okt` | 純 Java | 2.47s | 針對非正式文本調校 | 同上 |
| `channel1_mecab` | 獨立 C++ 引擎 + 字典 | 0.28s（最快） | 空格消歧處理好 | `pip install python-mecab-ko`（純 pip，見下方） |

~~`channel1_hannanum`（8.83s，模糊詞保守判為名詞）~~：**已排除**。使用者實測 `NullPointerException`，嘗試 `update-alternatives` 切換 JDK 版本、明確設定 `JAVA_HOME` 兩種修法皆無效，判定根因不明且非阻塞性問題，2026-07-26 決定不再追查、後續實作不包含此引擎。

**Mecab-ko 安裝（已於沙盒與使用者本機 WSL2 實測確認）**：

```bash
pip install python-mecab-ko
```

`python-mecab-ko` 是完全自包含的 PyPI 套件，自帶已編譯好的字典（`python-mecab-ko-dic`），純 pip 安裝即可，**不需要**額外編譯 mecab 引擎或下載字典檔。實測：沙盒安裝後 `from mecab import MeCab; MeCab().morphs(...)` 初始化 0.000s、斷詞 0.33ms，結果正確；使用者本機 `pip install python-mecab-ko` 也已成功（`python-mecab-ko-1.3.7` + `python-mecab-ko-dic-2.1.1.post2`）。這取代了原先規劃的 bitbucket 原始碼手動編譯方式（該方式在使用者本機實測容易因終端機貼上錯亂、字典編譯步驟不完整而失敗，已改列為文件中的備用方案，見 `LOCAL_TESTING.md` B 節）。

其餘四個引擎（Okt/Komoran/Kkma/Hannanum）僅需 `pip install konlpy` + JDK 11+ + 設定 `JAVA_HOME`，無需額外編譯。**但 Hannanum 在 JDK 17/21 下有已知相容性問題**（見第 9 節），使用者本機（JDK 21.0.10）實測 Hannanum 失敗，Okt/Komoran/Kkma 三者正常。

## 3. Channel 2：本地 LLM

**流程**：OCR 原文 -> LLM（透過 `llm_client.py`）一次推測修正錯字/多餘字 + 輸出詞性/例句/翻譯（要求結構化 JSON 回覆）-> 結構化輸出。

**執行環境**：Ollama（包裝 llama.cpp、REST API、自動 GPU/量化處理，整合最簡單，對比 llama.cpp 需手動設定、transformers 需自行處理量化後端）。

**推薦模型**：`qwen2.5:7b`（4.7GB，官方 Ollama 庫可直接 `ollama pull`，多語含韓文能力已驗證），作為預設；若韓文品質不足，備選 `qwen3:8b`（5.2GB）或手動匯入韓文專門微調模型 `Bllossom-8B`（需手動下載 GGUF + `ollama create`，未在官方庫）。

**環境安裝步驟（待實作時加入 `LOCAL_TESTING.md`）**：

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama run qwen2.5:7b "안녕하세요, 테스트입니다."   # 驗證模型可用、輸出韓文正常
```

`llm_client.py` 透過 Ollama 的本地 REST API（預設 `http://localhost:11434/api/generate`）呼叫，並設計成抽象介面（後續要接外部 LLM API 只需新增一個實作類別，呼叫端程式碼不需修改）。

## 4. Channel 3：混合

**流程**：以 Channel 1 為底（暫定使用 Channel 1 比較結果中表現最佳的引擎；若使用者希望每個引擎都各自再配一次 Channel 3，屬於範圍擴增，需再確認）-> 斷詞後查字典 -> 若該詞查無（斷詞結果為破碎單字，或整段被判為名詞，且字典查無此寫法）-> 呼叫 Channel 2 的 `llm_client` 請 LLM 依上下文推測正確字詞 -> 猜到就帶著修正後的字詞重新查字典、回到原流程 -> 猜不到就跳過該段（不輸出，但記錄一筆 `llm_fallback_failed`）。

## 5. 統計紀錄格式（RunReport，三通道共用同一 schema）

規劃欄位（`src/nlp/stats.py` 待新增 pydantic model）：

- `channel`：`channel1_okt` / `channel1_komoran` / `channel1_kkma` / `channel1_hannanum` / `channel1_mecab` / `channel2` / `channel3`
- `video_id`、`run_timestamp`
- `total_time_sec`：整個通道執行總耗時
- `module_times`：各模塊耗時明細（regex 清理、dedup、斷詞、字典查詢/LLM 呼叫、輸出寫檔）
- `word_count_total`：處理的詞彙總數
- `dict_hit_count` / `dict_hit_rate`：字典命中數與命中率（**目前的準確度代理指標**）
- `llm_call_count` / `llm_fallback_success_count` / `llm_fallback_fail_count`（Channel 2/3 適用）
- `error_count`：處理過程中的例外/失敗次數

輸出位置規劃：`data/output/<video>/stats/<channel>_report.csv`（或 json，待實作時定案）。

## 6. 執行隔離規則

- 所有通道／子通道依序執行，不同時跑，避免 GPU（OCR 已用掉一部分顯存、Channel 2/3 的 LLM 推論）互相搶用同一張 8GB 顯卡。
- Channel 1 各子通道（純 CPU，KoNLPy 不需要 GPU）理論上可平行跑，但為了計時公平比較，一樣規劃成依序執行。

## 7. 建議實作順序（待使用者下令後依此順序進行）

1. `scripts/build_dictionary_index.py` + `src/nlp/dictionary.py`（基礎建設，Channel 1、3 都依賴）
2. `src/nlp/text_cleaner.py`（regex 清理）
3. `src/nlp/stats.py`（RunReport schema）
4. Channel 1 runner（可用 `--engine` 參數切換五個引擎）+ 對應測試（沙盒端可用假資料測試 dictionary/text_cleaner 邏輯；KoNLPy 實際斷詞需在有 JDK 的環境驗證，比照 GPU 檢查的「沙盒驗證邏輯、本機驗證真實效果」模式）
5. Channel 2：`llm_client.py`（含 mock 測試）+ `LOCAL_TESTING.md` 補上 Ollama 安裝步驟 + Channel 2 runner
6. Channel 3 runner（整合 Channel 1 + Channel 2 fallback 邏輯）
7. 使用者本機安裝好五個 KoNLPy 引擎 + Ollama/Qwen2.5，實際跑過所有通道／子通道，收集 RunReport 數據
8. 專案尾聲：依收集到的字典命中率、耗時等數據，決定最終保留哪個通道/子通道

## 8. 已確認事項（2026-07-25）

- **Channel 3 維持單一版本**：不比照 Channel 1 針對五個引擎各跑一次，固定使用**速度最快的引擎**。依 KoNLPy 官方基準測試（第 2 節），Mecab-ko（0.28s/100K 字元）遠快於其餘四個引擎，故 Channel 3 底層斷詞固定採用 **Mecab-ko**。

## 9. 環境建制進度（2026-07-25，沙盒 + 使用者本機皆已驗證）

**沙盒驗證**（無 GPU，但 KoNLPy 的四個純 Java 引擎不需要 GPU，已在沙盒**真實安裝並驗證**，非 mock；沙盒 JDK 為 11）：

| 引擎 | 沙盒驗證結果（JDK 11） |
|---|---|
| Okt | ✅ 正常，初始化 0.26s，斷詞 2.0s（JVM 較重，屬正常現象） |
| Komoran | ✅ 正常，初始化 1.64s，斷詞 4.2ms |
| Kkma | ✅ 正常，初始化 0.00s（延遲載入），斷詞 3.0s |
| Hannanum | ✅ 正常，初始化 0.00s，斷詞 0.37s |
| Mecab-ko（python-mecab-ko） | ✅ 正常，初始化 0.000s，斷詞 0.33ms |

測試句「오늘 날씨가 정말 좋네요」各引擎斷詞結果一致（오늘/날씨/가/정말/좋(네요)），詞性標籤細節不同，符合預期。

**使用者本機驗證**（WSL2，JDK 21.0.10，實測結果）：

| 引擎 | 本機驗證結果（JDK 21.0.10） |
|---|---|
| Okt | ✅ 正常 |
| Komoran | ✅ 正常 |
| Kkma | ✅ 正常 |
| Hannanum | ❌ `NullPointerException`（`kr.lucypark.jhannanum` 在 `WorkflowFactory.getPredefinedWorkflow` 內部尋找自身資源路徑時失敗）。**追蹤更新**：原先懷疑是 JDK 17/21 相容性問題，但使用者實測用 `update-alternatives --config java` 切到 JDK 11.0.31 後，`java -version` 已顯示 11，Hannanum **仍以相同錯誤失敗**，證明不只是 `/usr/bin/java` 指向哪個版本的問題（KoNLPy 透過 JPype 啟動 JVM 時，可能是依 `JAVA_HOME` 或自行掃描 `/usr/lib/jvm/` 來決定實際載入的 JVM，不一定跟著 `update-alternatives` 走）。下一步建議：明確設定 `export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64` 後再測；若仍失敗則不再視為單純 JDK 版本問題（可能與含中文字元的專案路徑「專題資料」有關），且鑑於 Hannanum 本非五引擎中最快/最準者、Channel 3 也不依賴它，屬可接受的「此引擎在使用者環境不可用」結論 |
| Mecab-ko | 一開始嘗試 bitbucket 原始碼手動編譯（步驟繁瑣、過程中終端機貼上內容有錯亂，難以確認字典是否編譯完整），改用 `pip install python-mecab-ko` 後套件安裝成功（`python-mecab-ko-1.3.7` + `python-mecab-ko-dic-2.1.1.post2`）。修正 `check_konlpy_engines.py` 改為優先呼叫 `python-mecab-ko` 原生 API 後，使用者本機重跑已確認 **`[OK]`**（初始化 0.006-0.036s，斷詞 13.9-16.1ms，結果正確） |

**結論**：Mecab-ko 已改用更簡單可靠的 `pip install python-mecab-ko`（不需編譯），取代原規劃的 bitbucket 手動編譯方式，**已於使用者本機驗證成功**。Hannanum 目前在使用者環境仍不可用，根因尚未完全確認（JDK 版本切換無效），待使用者嘗試明確設定 `JAVA_HOME` 後才能進一步判斷；不影響 Channel 1 其餘四個子通道，也不影響 Channel 3（固定用 Mecab-ko）。

**Ollama + Qwen2.5:7b：已於使用者本機驗證成功**。`ollama run qwen2.5:7b "안녕하세요, 테스트입니다."` 正確以韓文回應；`nvidia-smi` 顯示執行期間顯存用量從閒置 1435MiB 升至 6058MiB，確認有使用 GPU。安裝過程中先遇到 `curl -fsSL https://ollama.com/install.sh | sh` 因缺少 zstd 而失敗（`ERROR: This version requires zstd for extraction`），解法為先 `sudo apt-get install -y zstd` 再重跑安裝腳本，已寫入 `LOCAL_TESTING.md` C 節，使用者已照此修復並確認可用。

**沙盒環境限制**（不變，僅供參考）：Ollama 與 Mecab-ko 備用手動編譯方案需要的網域（ollama.com、bitbucket.org）仍被沙盒網路白名單擋下，這兩項的實際驗證只能在使用者本機進行——如上，皆已在本機完成驗證。

新增/修改檔案：
- `scripts/check_konlpy_engines.py`：獨立驗證五個引擎的診斷腳本，`check_mecab()` 已改為優先嘗試 `python-mecab-ko` 原生 API，失敗才退回 `konlpy.tag.Mecab`；docstring 補充 Hannanum JDK21 已知問題說明。
- `requirements.txt`：`python-mecab-ko>=1.3.7` 已改為正式（未註解）依賴；JPype1 註解更新為反映實測 3/5（本機）與 4/5（沙盒）Java 引擎可用情況。
- `LOCAL_TESTING.md`：B 節改為以 `pip install python-mecab-ko` 為主，手動編譯列為備用方案（摺疊區塊）；C 節加入 zstd 修復步驟；A 節與疑難排解表加入 Hannanum JDK21 已知問題說明。

## 10. 環境建制最終確認（2026-07-26，使用者本機，Hannanum 已定案排除）

使用者依修正後的 `check_konlpy_engines.py` 重跑，完成 Ollama 安裝，並嘗試兩種方式排除 Hannanum 問題，結果：

- KoNLPy：**4/5**（Okt、Komoran、Kkma、Mecab-ko 皆 `[OK]`；Mecab-ko 走 `python-mecab-ko` 原生 API，初始化 0.006-0.036s、斷詞 13.9-16.1ms，結果正確）。
- Hannanum：**已確定放棄，不再追查**。使用者先用 `sudo update-alternatives --config java` 切到 JDK 11.0.31（`java -version` 確認顯示 11），重跑仍失敗；再明確 `export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64` 後重跑，**依然是完全相同的 `NullPointerException`**。兩種修法皆無效，證明根因不是 JDK 版本或 `JAVA_HOME` 設定問題。使用者決定（2026-07-26）：忽略此引擎，後續所有計畫與實作皆不再包含它。
- Ollama + Qwen2.5:7b：**已完成安裝並驗證**（`sudo apt-get install -y zstd` 解決安裝腳本報錯後，`ollama pull qwen2.5:7b` 成功，`ollama run qwen2.5:7b` 測試輸出正確、通順的韓文回應，`nvidia-smi` 確認顯存用量由 1435MiB 升至 6058MiB，證實有吃到 GPU）。
- GPU / venv / pytest：`nvidia-smi` 正常顯示 RTX 4060（Driver 591.74、CUDA 13.1）；`.venv` 啟用正常；`pytest tests/ -q` 在使用者本機也是 **13 passed**。

**結論：Phase 5 環境建制階段全部完成，無待解決事項。** Channel 1 定案 4 個子通道（Okt/Komoran/Kkma/Mecab-ko）、Channel 2（Ollama+qwen2.5:7b）、Channel 3（固定用 Mecab-ko）所需執行環境皆已在使用者本機就緒。使用者已下令繼續下一步，開始 Phase 5 模組程式碼實作。

## 11. 已排除項目

- **Hannanum**：2026-07-26 正式排除，不列入 Channel 1 子通道，也不再追查根因。詳見第 10 節。

## 12. 模組實作進度

### 12.1 字典索引 + 查詢模組（第一步，已完成）

- `scripts/build_dictionary_index.py`：解析 `韩中字典xml/` 11 個 LMF XML 檔，建成 SQLite 索引。
- `src/nlp/dictionary.py`：`DictionaryIndex` 類別，依韓文寫法查詢所有同形詞／多義詞候選（`DictionaryCandidate`，定義於 `src/schemas.py`）。
- `config/settings.py`：新增 `DICTIONARY_CONFIG`（xml 目錄、索引檔路徑、目標翻譯語言、無對應詞彙佔位字串、例句類型優先序）。

**對全部 11 個真實檔案實測建立索引**：共 56,555 筆詞條、76,833 筆詞義、657,531 筆例句、826,505 筆多語翻譯（其中中文翻譯 75,145 筆，查無對應 4,174 筆），耗時約 20 秒。索引檔（`data/dictionary_index.sqlite3`，約 219MB）已建好並複製到專案 `data/` 目錄。

**實作過程中發現並修正兩個真實資料的品質問題**（皆非規劃階段能預見，透過實際解析真實 XML 才發現）：

1. **`LexicalEntry` 的 id 不是唯一值**：實測 11 個檔案中有 54 組 entry_id 被重複使用，最多一組（id=73278）被 28 個完全不同的詞條（如「한」「한 건 하다」「한 귀로 흘리다」等慣用語）共用同一個 id，研判是原始資料把「衍生慣用語」跟「基礎詞」歸在同一 id 底下所致。原本規劃用 entry_id 當資料庫主鍵，若真的這樣做，後面的詞條會把前面的覆寫掉、造成資料遺失。**已修正**：改用自動遞增的 `entry_pk` 當主鍵，原始 entry_id 僅保留為一般欄位供追溯，不影響任何一筆真實詞條。
2. **XML 檔內混有非法控制字元**：11 個檔案中有 4 個檔案共混入 7 個 `\x08`（backspace）控制字元（疑似原始匯出工具遺留），這類字元在 XML 1.0 規範中禁止出現，會讓標準函式庫直接拋出「not well-formed」解析錯誤而整個檔案讀不了。**已修正**：讀檔時先用正則清除這類非法控制字元（僅清除 0x00-0x1F 範圍內、tab/換行/回車以外的控制字元），不影響任何有意義的文字內容。

**一項待使用者確認的工程假設**（非明確規定，屬合理預設，若需調整可隨時修改）：同一詞義（Sense）底下可能有多筆例句，`dictionary.py` 目前只挑「一句代表性例句」而非全部回傳，優先序為完整句子「문장」> 詞組「구」> 對話「대화」（`config.settings.DICTIONARY_CONFIG["example_type_priority"]`）。真實資料驗證：查詢「가」「좋다」「오늘」等常見詞，皆正確回傳多筆同形詞/多義詞候選、正確的中文翻譯、合理的代表例句；查詢不存在的詞回傳空 list。

已撰寫測試：`tests/test_build_dictionary_index.py`（4 項，涵蓋控制字元清理、欄位解析、無對應詞彙正規化、entry_id 重複資料不遺失）、`tests/test_dictionary.py`（5 項，涵蓋多同形詞查詢、例句優先序、翻譯空值、未知詞查詢、索引檔不存在的錯誤處理）。全專案測試共 **22 項全過**（含原有 13 項）。

### 12.2 Regex 清理 + 執行報告 schema（第二步，已完成，2026-07-26）

- `src/nlp/text_cleaner.py`：`clean_ocr_text(raw_text: str) -> str`。只保留韓文字元（Hangul 音節 + 四個字母區塊）與空白，其餘（標點、數字、英文、其他語言）一律移除；連續空白收斂成一個。使用者確認：只留韓文字元 + 空白（不保留標點）。
- `src/nlp/stats.py`：`RunReport`（pydantic model，欄位對應第 5 節規劃）+ `RunReportBuilder`（累加器，`time_module()` context manager 可對同一模塊重複計時並自動加總、`record_word()`/`record_llm_call()`/`record_error()` 記錄計數、`build()` 結算、`write_csv()` 寫檔）。輸出格式依使用者確認：CSV，路徑規劃為 `data/output/<video>/stats/<channel>_report.csv`，巢狀的 `module_times` 寫檔時會攤平成 `module_time_<name>` 欄位。

新增測試 14 項（`test_text_cleaner.py` 7 項、`test_stats.py` 7 項），全專案測試共 **36 項全過**。

### 12.3 Channel 1 runner + 四引擎模擬測試（第三步，已完成，2026-07-26）

- `src/nlp/tokenizer.py`：統一斷詞介面 `get_tokenizer(engine_name)`，包住 Okt/Komoran/Kkma（konlpy.tag）與 Mecab-ko（python-mecab-ko）。每個 `Token` 同時保留斷詞原始文字（`word`）與嘗試還原辭典形後的查詢用文字（`dictionary_form`，對詞性為動詞/形容詞語幹者補回「다」）。
  - **實測發現的引擎間真實差異**：Komoran／Kkma／Mecab-ko 皆會把用言拆成「語幹＋語尾」（如「좋네요」→「좋」(VA)+「네요」），語幹補「다」可正確還原「좋다」；但 **Okt 不會拆開語幹與語尾**（整句「좋네요」視為一個 Adjective），此時補「다」無法得到正確辭典形，這是 Okt 斷詞風格本身的限制，刻意不用規則硬拆（需要完整韓文語尾清單，超出本次範圍），讓比較數據反映真實差異。
- `scripts/run_channel1.py`：串接「OCR 原文 → `text_cleaner` 清理 → `deduplicator` 去重 → 依 `--engine` 斷詞 → `dictionary.py` 查詢 → `ExportRecord` 結構化輸出」，並用 `RunReportBuilder` 記錄各模塊耗時與字典命中率，寫出 `data/output/<video>/channel1_<engine>/export.csv` 與 `data/output/<video>/stats/channel1_<engine>_report.csv`。
  - 字典查無結果時的處理（Channel 1 內部簡化重試，非 Channel 3 的 LLM fallback）：先用還原後的辭典形查，查無結果再退回斷詞原始文字查一次；兩次都查無結果則不輸出候選列，但仍計入 `word_count_total`（反映在命中率上）。

**四引擎模擬測試結果**（對真實素材 `data/output/001/ocr_on/ocr_results.csv`，3326 筆真實 OCR 辨識結果，denoise-on 版本）：

| 引擎 | 總耗時 | 處理詞彙數 | 字典命中率 | 斷詞初始化 | 斷詞耗時 | 查字典耗時 |
|---|---|---|---|---|---|---|
| Okt | 13.60s | 2523 | 88.7% | 0.31s | 3.07s | 9.71s |
| Komoran | 16.94s | 3005 | 88.1% | 2.12s | 0.32s | 13.88s |
| Kkma | 17.91s | 2948 | 90.0% | 0.29s | 4.70s | 12.35s |
| Mecab-ko | 11.45s | 2784 | 88.8% | 0.004s | 0.14s | 10.69s |

四個引擎命中率相近（88-90%），Mecab-ko 總耗時最短、斷詞本身也最快（符合官方基準測試結果），四者查字典耗時皆佔總耗時大部分（逐詞查詢 SQLite，屬預期現象，非 bug）。命中率偏高的原因：測試影片內容為單字卡形式（見第 9 節/PROJECT_NOTES.md 對 Phase 1 素材的觀察），多為單純名詞，Okt 的語幹/語尾不拆分限制在此批素材中影響不大，未來換用真正的自然字幕影片素材時，四引擎命中率差異可能會更明顯。

實測輸出範例（Okt，字幕「학원」「대학교」「학교」「학생」）：每個詞正確查到中文翻譯與韓文例句，同形詞/多義詞（如「학원」有「学院/学校」「补习班/培训班」兩個詞義）皆有個別列出。

新增測試 8 項（`test_tokenizer.py`，含真實引擎斷詞、未知引擎報錯、辭典形還原驗證）。全專案測試共 **44 項全過**。

### 12.4 Channel 2：llm_client.py + Channel 2 runner（第四步，已完成，2026-07-26）

- `src/nlp/llm_client.py`：`LLMClient` 抽象介面（`generate(prompt) -> str`）+ `OllamaClient` 實作，呼叫本地 Ollama REST API（預設 `http://localhost:11434/api/generate`，模型 `qwen2.5:7b`，`format="json"` 要求盡量輸出合法 JSON）。未來若要接外部 LLM API，只需新增一個實作同一介面的類別。
- `src/nlp/llm_annotator.py`：`PROMPT_TEMPLATE`（要求 LLM 一次完成錯字修正＋詞彙拆解＋詞性/例句/翻譯標註，回傳 JSON）+ `annotate_subtitle()`（呼叫 LLM、解析回應，容錯處理 markdown code fence 包裹、JSON 格式錯誤等情況，解析失敗回傳 `None` 而非拋例外中斷流程）。
- `scripts/run_channel2.py`：串接「OCR 原文 → `text_cleaner` 清理 → `deduplicator` 去重 → 整句交給 LLM 處理 → `ExportRecord` 結構化輸出」。與 Channel 1 共用清理／去重兩個前處理步驟（見第 1 節），差異在於 Channel 2 不斷詞、不查字典，由 LLM 一次完成分析。`dict_hit_rate` 欄位在 Channel 2 語境下重新定義為「LLM 有給出翻譯的比例」，方便沿用同一份 RunReport 欄位跨通道比較。
- `requirements.txt`：新增 `requests`（`llm_client.py` 呼叫 Ollama REST API 需要）。

**四引擎模擬測試（重要說明：本次為控制流程驗證，非真實模型品質驗證）**：沙盒沒有安裝 Ollama（`ollama.com` 被沙盒網路白名單擋下，見 13.5 節），因此比照先前 GPU 檢查邏輯測試的做法，寫了一個臨時的假 Ollama HTTP 伺服器（`_stub_ollama_server.py`，規則式產生假回應，測試完已刪除，非交付內容），讓 `run_channel2.py` 對真實 OCR 資料（同 Channel 1 測試用的 `data/output/001/ocr_on/ocr_results.csv`）跑一次完整流程。結果：2008 句字幕、2008 次「LLM」呼叫、0 次解析失敗、2209 個詞彙全部產生結構化輸出，證實「讀檔 → 清理 → 去重 → 呼叫 LLM client → 解析回應 → 寫檔」整條路徑銜接正確。**但輸出內容（翻譯、例句）皆為假伺服器規則生成的佔位文字，不代表真實 `qwen2.5:7b` 的輸出品質**，此模擬測試結果與資料未同步到專案資料夾（避免與真實資料混淆）；真實品質驗證需要使用者在已裝好 Ollama + qwen2.5:7b 的本機執行 `python scripts/run_channel2.py`。

新增測試 16 項（`test_results_io.py` 2 項、`test_llm_client.py` 4 項——用 mock 驗證 `OllamaClient` 的請求組裝與回應解析、`test_llm_annotator.py` 6 項——用 FakeLLMClient 驗證 prompt 組裝與 JSON 解析容錯邏輯，另因程式碼重構新增少量測試）。全專案測試共 **56 項全過**。

### 12.5 Channel 2 真實模型驗證結果（2026-07-26，使用者本機，真實 qwen2.5:7b）

使用者在本機（已裝好 `requests`、Ollama、qwen2.5:7b）實際執行 `scripts/run_channel2.py` 對真實資料（`data/output/001/ocr_on/ocr_results.csv`，2008 句去重後字幕），結果：

- 總耗時 **3591.24s**（約 60 分鐘），平均每次 LLM 呼叫約 1.79 秒（RTX 4060 8GB 執行 7B 模型的合理範圍）。
- 2008 次呼叫中 **2001 次成功解析**、**7 次解析失敗**（LLM 回應不是合法 JSON 或欄位不符，`llm_annotator.py` 的容錯機制正確接住，未讓整個流程中斷）。
- 共處理 4401 個詞彙，其中 3011 個有翻譯（**68.4%**），低於 Channel 1 四引擎的 88-90% 字典命中率——這是預期中的落差，Channel 2 完全依賴 LLM 自行判斷是否給出翻譯，沒有查證過真實字典，之後統計分析可比較兩種方式在品質上的實際差異（例如 LLM 翻譯是否正確、是否有幻覺）。
- 耗時遠高於 Channel 1（Channel 1 四引擎總耗時皆在 11-18 秒），符合預期：Channel 2 對每一句字幕都要跑一次完整的 LLM 推論，而 Channel 1 純本地運算不需要等待模型推論。

（原先沙盒的假伺服器模擬顯示 0 次解析失敗、100% 有翻譯，皆為假資料的人工結果，與這次真實資料相比，真實 LLM 呼叫確實存在耗時與解析失敗的真實變數，證實假伺服器模擬僅能驗證控制流程、不能取代真實執行。）

### 12.6 Channel 3：混合通道（第五步，已完成，2026-07-26）

- `src/nlp/llm_fallback.py`：`FALLBACK_PROMPT_TEMPLATE`（針對「單一查無結果的詞彙＋所在句子上下文」請 LLM 推測一個最可能的辭典詞彙，跟 Channel 2 `llm_annotator.py` 的「整句分析」prompt 不同）+ `guess_word()`（解析回應，同樣的容錯策略：解析失敗或 LLM 明確回傳空字串都算「猜不到」，回傳 `None`）。
- `scripts/run_channel3.py`：以 Channel 1 架構為基礎、**固定使用 Mecab-ko**（第 8 節已確認的選型），字典兩次本地查詢（辭典形、斷詞原文）都失敗後才呼叫 LLM fallback；猜到就用猜測結果重新查一次字典，回到原流程；猜不到（或猜的詞查字典依然沒有）則跳過該詞，記一筆 `llm_fallback_fail`。支援注入自訂 `llm_client`（測試用，不需要真正的 Ollama 伺服器）。

**測試驗證（三層）**：
1. `test_llm_fallback.py`（5 項）：FakeLLMClient 驗證 prompt 組裝、JSON 解析、markdown 包裹、明確放棄等情境。
2. `test_run_channel3.py`（3 項）：用小型合成字典 + 真實 Mecab-ko 斷詞 + 可控 FakeLLMClient，驗證「fallback 成功挽回」「fallback 確實失敗」「字典本身命中、不觸發 LLM」三種情境的統計數據與輸出內容皆正確。
3. **沙盒對真實資料的控制流程模擬**（同樣沒有真正 Ollama，用臨時假伺服器，一律回應「猜不到」以驗證最壞情境）：對 `data/output/001/ocr_on/ocr_results.csv` 執行，結果與 Channel 1 的 Mecab-ko 子通道基準完全一致（處理詞彙 2784、字典命中 2471、命中率 88.8%），另外新增 313 次 fallback 呼叫、全部失敗（313 = 2784 - 2471，數字吻合），證實：沒有 LLM 幫助時 Channel 3 退化為與 Channel 1 Mecab-ko 完全相同的結果，控制流程正確；**這次的「全部失敗」是假伺服器規則決定的，不代表真實 qwen2.5:7b 的推測能力**，真實推測成功率（能挽回多少原本查無結果的詞彙）需要使用者在本機執行才能得知，模擬用的假伺服器與這批模擬資料同樣未同步到專案資料夾。

新增測試 8 項。全專案測試共 **64 項全過**。

### 12.7 Channel 3 真實 fallback 挽回率（001，使用者本機，真實 qwen2.5:7b）

- 總耗時 **121.25s**，313 次 LLM fallback 呼叫中僅 **1 次成功挽回**、312 次仍失敗。
- 與後續 10 支影片全量測試（12.8 節）合併來看，真實挽回率長期落在 1-2% 區間，且成本很高（詳見 12.8 節②）。

### 12.8 Phase 0-5 全流程驗收（10 支真實影片，`scripts/_pipeline_smoke_test.py --skip-channel2`，2026-07-26）

使用者在本機對 `raw/` 目錄下全部 10 支影片，依序跑過 Phase 1→2（denoise on）→3（GPU OCR）→Channel 1（4 引擎）→Channel 3，共 **80 個階段紀錄，全數 `ok=True`**（Channel 2 因耗時過高，本次驗收先跳過，僅 001 有前次的真實驗證數據，見 12.5 節）。

**① 內部數據一致性檢查（確認統計邏輯無 bug）**：對全部 10 支影片逐一核對，channel3 的 `word_count` 皆與同一影片 channel1_mecab 的 `word_count` 完全相同；channel3 的 `dict_hit_count` 皆恰好等於「channel1_mecab 的 dict_hit_count + 該影片的 llm_fallback_success_count」，10 支影片無一例外——證實 RunReport 統計邏輯正確，非隨機巧合。另外對全部 55 萬筆匯出資料檢查「原文/中文/詞性/例句」完全重複列，數量很高（55.4 萬筆中 55.3 萬筆重複），但納入 `備註` 欄位的時間戳記後即不重複——這是預期行為：同一詞彙（如「다」「에」「가다」）在整部影片的字幕中本來就會反覆出現，每次出現各自成一列，並非匯出邏輯有誤。

**② Channel 3 LLM fallback 的真實成本效益（10 支影片加總）**：共 2930 次 fallback 呼叫，僅 **50 次成功挽回（1.7%）**，但為此多花了約 **912 秒**（相較純 Channel1-Mecab 的 147.7 秒）。這是後續「保留哪個通道」決策的具體數據：目前看來 Channel 3 用大量運算時間換取極少量的額外詞彙覆蓋率，是否值得取決於最終評估標準怎麼權衡「覆蓋率」與「時間成本」。

**③ Channel 1 四引擎加總命中率/耗時（10 支影片，依詞彙數加權平均）**：

| 引擎 | 加權命中率 | 總耗時 |
|---|---|---|
| Okt | 81.5% | 127.3s |
| Komoran | 86.5% | 193.9s |
| Kkma | 84.7% | 207.6s |
| Mecab | 85.2% | 147.7s |

Okt 命中率明顯偏低，與 12.3 節已知限制一致（Okt 不切分詞幹＋語尾，動詞/形容詞的辭典形還原對 Okt 較不利，其餘三引擎不受影響）。

**④ 影片 009／010 的字幕數量異常偏少（36、30 筆去重字幕，其餘影片為 300-2341 筆）**：實際檢視這兩支影片的 OCR 原始文字分布，發現內容由大量數字/片段符號（"1""2""3""4""5"、"["、"90 ]" 等，各出現 9-36 次）與少量真實詞彙（009：선생님／도서관／백화점／딸기／식당／모자／병원／바지／고양이／비행기；010：냉장고／젓가락／공원／당근／교회／양말／의사／돼지／옷장，各出現約 9-13 次）交錯組成——研判這兩支素材本身是「編號詞彙卡」格式（可能是基礎詞彙教學影片），與其餘影片的連續對話字幕格式不同，屬於素材內容差異、而非管線缺陷。但仍建議使用者實際看過這兩支影片，確認不是這兩支素材的畫面風格導致 OCR/前處理效果特別差。

**⑤ 影片 008**：詞彙量最大（9218-11933字，各引擎皆同一數量級）、命中率各引擎最低（73-89%）、Channel 3 fallback 次數最多（2262 次）、總耗時最長（781.56s）——是這批素材中語言內容最豐富、對系統最具挑戰性的一支，適合作為之後品質比較的重點案例。

**Phase 0-5 完成度結論**：依使用者訂下的驗收標準（全部檔案跑過 1/2/3 通道且成功即算完成），本次 80/80 階段成功，**Phase 0-5 可視為功能上已完成**。仍在範圍外、尚未處理的項目：
- Anki 匯出模組（`src/export/anki_exporter.py`）尚未被納入驗收流程實際測試過。
- 目前沒有「正式、永久」的單一指令入口串接全部 Phase，`_pipeline_smoke_test.py` 明確標註為臨時驗收工具、非正式交付模組。
- Phase 6/7/9 尚未開始。
- 最終保留哪個通道/引擎、denoise on/off 的決策，依先前共識，仍留到專案尾聲、依累積的真實數據決定（本次新增的 10 支影片數據已可作為決策依據之一）。
- Channel 2 尚未對 10 支影片全部跑過真實資料（僅 001 有完整真實驗證），因單支影片耗時近 1 小時，全部跑完預估需要一天左右，待使用者安排時間執行。
