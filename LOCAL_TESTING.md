# 本機測試流程（Local Testing Guide）

適用對象：在你自己的電腦上（偵測到你是用 Windows + WSL2，且專案資料夾內已有一個 WSL 建立的 `.venv`），從零開始把整個 pipeline 跑起來，用真正的 GPU 驗證 Step 1-4（影片匯入 → 影格採樣 → 前處理 → OCR），並產生 Phase 2 遺留的 denoise on/off 比較數據。

沙盒（Claude 的開發環境）沒有 GPU，無法執行這一段，所以以下步驟都要在你自己的機器上做。完成後把結果告訴我，我可以幫你把設定值（例如 denoise 預設開關）寫回專案。

---

## 0. 前置需求確認

- Windows 已安裝**最新的 NVIDIA 顯示卡驅動**（一般顯示卡驅動即包含 WSL2 CUDA 支援，不需要另外在 WSL 內裝 Linux 版驅動）。
- 已啟用 WSL2，且以下指令都在 WSL2 的終端機（Ubuntu 等）內執行，不是 Windows PowerShell。
- 專案路徑：WSL 內是 `/mnt/c/Users/LinKJ/Desktop/專題資料/ocr_subtitle_system`，對應 Windows 的 `C:\Users\LinKJ\Desktop\專題資料\ocr_subtitle_system`。

## 1. 確認 WSL2 內看得到 GPU

```bash
nvidia-smi
```

應該會列出 GPU 型號、驅動版本、右上角的 CUDA Version。若指令找不到或報錯，代表 WSL2 GPU 直通沒設定好——先去 Windows 更新 NVIDIA 驅動（https://www.nvidia.com/Download/index.aspx），WSL2 本身不需要再裝一份驅動。這一步沒過，後面全部會卡住，先解決這裡。

## 2. 啟用 Python 環境

專案資料夾內已經有一個 `.venv`，直接啟用即可：

```bash
cd /mnt/c/Users/LinKJ/Desktop/專題資料/ocr_subtitle_system
source .venv/bin/activate
```

如果想重新建立乾淨環境：

```bash
bash scripts/setup_env.sh
source .venv/bin/activate
```

## 3. 安裝支援 CUDA 的 torch / easyocr

`requirements.txt` 內的 `easyocr` 會連帶安裝 torch，但不一定會裝到跟你 CUDA 版本相符的建置版本。建議先明確指定安裝支援 CUDA 的 torch：

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

（`cu121` 是範例，實際版本依 `nvidia-smi` 右上角顯示的 CUDA Version 對照 https://pytorch.org/get-started/locally/ 選擇。）

再安裝其他依賴：

```bash
pip install -r requirements.txt
```

`konlpy`（韓文斷詞）需要額外安裝 JDK 11+ 並設定 `JAVA_HOME`，那是 Phase 5 才會用到，Phase 3 驗證 OCR 可以先跳過，若安裝失敗不影響本次測試。

## 4. 驗證 torch 真的抓到 GPU

```bash
python3 -c "import torch; print('cuda available:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

必須看到 `cuda available: True`。如果是 `False`，先解決這個問題再往下走——專案裡所有需要 OCR 的腳本，偵測不到 GPU 時都會直接終止（這是你要求的行為，不是 bug）。常見原因是裝到了 CPU-only 版本的 torch，回第 3 步重新指定 CUDA 版本安裝。

## 5. 用專案內建的 GPU 檢查腳本再確認一次

```bash
python3 scripts/check_gpu.py
```

正常會印出偵測到的 GPU 名稱、顯示記憶體、CUDA capability。這跟 `run_phase3.py` 執行前做的檢查是同一段程式碼（`src/ocr/gpu_check.py`），先在這裡單獨確認過，之後跑 OCR 才不會跑到一半才發現環境有問題。

## 6. 跑完整測試套件，確認環境沒問題

```bash
python3 -m pytest tests/ -q
```

目前共 13 項測試，應該全數通過。這些測試設計成不需要真的有 GPU 也能跑（用假的 torch 模組測邏輯），所以不管有沒有 GPU 都該全過；如果這裡就失敗，代表環境本身有問題（例如套件版本衝突），要先解決再往下。

## 7. Phase 1：影片匯入 + 影格採樣

```bash
python3 scripts/run_phase1.py --video raw/001.mkv --sample-rate 1.0
```

輸出在 `data/output/001/frames/`（影格圖片 + `manifest.csv`）。可以先加 `--max-frames 20` 跑少量測試，確認沒問題後再跑整支影片（不加這個參數就是處理整支影片）。

## 8. Phase 2：前處理（denoise 兩版比較）

```bash
python3 scripts/run_phase2.py --frames-dir data/output/001/frames
```

預設會同時輸出 `data/output/001/processed/denoise_on/` 與 `denoise_off/` 兩份影像＋各自的 `manifest.csv`，並印出兩者耗時。

## 9. Phase 3：OCR（真正需要 GPU 的一步）

分別對兩個版本跑 OCR，才能比較辨識率，記得用 `--out-dir` 把兩次結果分開存（否則會互相覆寫）：

```bash
python3 scripts/run_phase3.py --processed-dir data/output/001/processed/denoise_on  --out-dir data/output/001/ocr_on
python3 scripts/run_phase3.py --processed-dir data/output/001/processed/denoise_off --out-dir data/output/001/ocr_off
```

每個指令會輸出對應的 `ocr_results.csv`（欄位：frame_id, timestamp_sec, text, bbox, confidence）。

第一次執行 EasyOCR 會下載韓文語言模型（數百 MB，需要網路連線），之後執行就不用再下載。

如果這一步出現「未偵測到可用的 GPU」並終止，回頭檢查第 3-4 步。

## 10. 比較 denoise on/off 辨識率，回報結果

打開 `data/output/001/ocr_on/ocr_results.csv` 和 `data/output/001/ocr_off/ocr_results.csv`，比較：

- 辨識出的文字筆數（有沒有漏字／多字）
- confidence 平均值
- 文字內容是否正確（對照畫面實際文字）

依 2026-07-25 的最新決議：denoise 開關的最終決定，**留到專案尾聲跟 Phase 5 三通道比較一起決定**，兩版本數據都已保留，這裡不用再重新比較。

---

## Phase 5 環境建制（三通道 NLP 架構，見 `PHASE5_MULTI_CHANNEL_PLAN.md`）

沙盒已驗證 KoNLPy 的四個純 Java 引擎（Okt/Komoran/Kkma/Hannanum）可直接 `pip install` 使用，不需要額外編譯；只有 Mecab-ko 和 Ollama 需要在你自己機器上安裝（沙盒連不到 bitbucket.org 和 ollama.com，這兩個網域被沙盒的網路白名單擋下）。

### A. KoNLPy 四個 Java 引擎（Okt / Komoran / Kkma / Hannanum）

```bash
# 確認 JDK 已安裝（沙盒測試環境已內建 openjdk-11，WSL2 若沒有需自行安裝）
java -version
# 若沒有：sudo apt-get install -y openjdk-11-jdk

# 安裝 Python 套件
pip install konlpy JPype1

# 驗證四個引擎（沙盒已實測全部正常運作，同一套指令你的機器上應該也會通過）
python3 scripts/check_konlpy_engines.py
```

正常會看到 Okt / Komoran / Kkma / Hannanum 四個都印出 `[OK]` 及斷詞結果，Mecab-ko 會印出 `[未安裝]`（下一步處理）。

**已知問題：Hannanum 可能會丟出 `NullPointerException`。**（`kr.lucypark.jhannanum` 底層套件在 `WorkflowFactory.getPredefinedWorkflow` 內部尋找自身資源路徑時失敗。）原先懷疑純粹是 JDK 17/21 相容性問題，但實測發現：用 `sudo update-alternatives --config java` 把預設 `java` 切到 11.0.31 之後，`java -version` 已顯示 11，Hannanum 卻**仍然失敗、錯誤一模一樣**。代表問題不只是 `/usr/bin/java` 指向哪個版本——KoNLPy 底層透過 JPype 啟動 JVM 時，未必是照 `java` 指令的 symlink 走，很可能是用別的邏輯（例如 `JAVA_HOME` 環境變數，或自動掃描 `/usr/lib/jvm/` 目錄後選到的版本）找到實際載入的 JVM 函式庫，因此只切 `update-alternatives` 不夠。

**已確定（2026-07-26）：放棄此引擎，不再追查。** 實測結果：切換 `update-alternatives` 到 JDK 11、以及明確 `export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64` 兩種方式重跑，Hannanum 都是完全相同的 `NullPointerException`，代表根因不是 JDK 版本或 `JAVA_HOME` 設定問題（可能與專案路徑含中文字元「專題資料」有關，或 jhannanum 本身其他限制）。鑑於 Hannanum 在 Channel 1 五個引擎中原本就非最快也非最準（見 `PHASE5_MULTI_CHANNEL_PLAN.md` 第 2 節速度/特性比較表），Channel 3 固定用 Mecab-ko 也不受影響，**已正式排除此引擎，Channel 1 定案為 4 個子通道（Okt/Komoran/Kkma/Mecab-ko）**，後續實作與測試不再包含 Hannanum。

### B. Mecab-ko（優先用 pip 安裝，不需編譯）

實測發現 `python-mecab-ko` 這個 PyPI 套件是完全自包含的：純 pip 安裝、自帶已編譯好的字典（`python-mecab-ko-dic`），**不需要**另外編譯 mecab 引擎或下載字典檔，比社群常見的 bitbucket 原始碼編譯方式簡單很多：

```bash
pip install python-mecab-ko

# 驗證，這次應該 Mecab-ko 也是 [OK]（走 python-mecab-ko 路徑）
python3 scripts/check_konlpy_engines.py
```

`scripts/check_konlpy_engines.py` 會優先嘗試 `python-mecab-ko` 的原生 API（`from mecab import MeCab`），成功就直接回報 `[OK]`；只有這個套件不存在時才會退回嘗試舊的 `konlpy.tag.Mecab`（那個路徑才需要下面的手動編譯）。

<details>
<summary>備用方案：手動編譯系統版 mecab + mecab-ko-dic（僅在 python-mecab-ko 不可用時才需要，一般不建議）</summary>

```bash
sudo apt-get update && sudo apt-get install -y g++ curl git make automake autoconf libtool

# 1) 安裝 mecab 核心引擎
cd /tmp && curl -LO https://bitbucket.org/eunjeon/mecab-ko/downloads/mecab-0.996-ko-0.9.2.tar.gz
tar zxfv mecab-0.996-ko-0.9.2.tar.gz && cd mecab-0.996-ko-0.9.2
./configure && make && sudo make install && sudo ldconfig

# 2) 安裝韓文字典 mecab-ko-dic
cd /tmp && curl -LO https://bitbucket.org/eunjeon/mecab-ko-dic/downloads/mecab-ko-dic-2.1.1-20180720.tar.gz
tar zxfv mecab-ko-dic-2.1.1-20180720.tar.gz && cd mecab-ko-dic-2.1.1-20180720
./autogen.sh && ./configure && make && sudo make install
```

> 這幾個網址是 KoNLPy 社群長期使用的來源，實測這條路徑容易因終端機貼上內容錯亂、或字典編譯步驟不完整而失敗，難以除錯。**建議一律優先使用上面的 `pip install python-mecab-ko`**，只有在該套件本身無法安裝的極端情況下才考慮這個備用方案。

</details>

### C. Ollama + Qwen2.5:7b（Channel 2/3 用）

```bash
sudo apt-get install -y zstd   # Ollama 安裝腳本解壓縮需要 zstd，先裝好避免安裝失敗
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama run qwen2.5:7b "안녕하세요, 테스트입니다."   # 驗證模型可正常輸出韓文回應
```

第一次 `ollama pull` 會下載約 4.7GB，需要網路且花一些時間，屬正常現象。跑完後可以用 `nvidia-smi` 確認推論時有吃到 GPU（`GPU-Util` 欄位會跳動）。

---

## 疑難排解

| 狀況 | 排解方向 |
|---|---|
| WSL2 內 `nvidia-smi` 找不到指令或報錯 | 更新 Windows NVIDIA 驅動，WSL2 本身不需要另外裝驅動 |
| `torch.cuda.is_available()` 是 `False`，但 `nvidia-smi` 正常 | 通常是裝到 CPU-only 版 torch，回第 3 步重新指定 CUDA 版本安裝 |
| `pip install easyocr` 或第一次執行很久 | 會連帶安裝 torch、第一次執行會下載語言模型，都需要網路，是正常現象 |
| `konlpy` 安裝失敗 | Phase 5 才需要，Phase 3 驗證 OCR 可以先不裝，不影響本次測試 |
| `run_phase3.py` 印出「未偵測到可用的 GPU」後終止 | 這是設計行為（依你的要求），回第 3-5 步確認 torch/GPU 設定 |
| Mecab-ko 的 `curl -LO` 抓不到檔案 | 這是備用的手動編譯方案才會遇到的問題；改用 `pip install python-mecab-ko`（見 B 節），不需要這些網址 |
| `check_konlpy_engines.py` 顯示 Mecab-ko `[未安裝]`，即使已 `pip install python-mecab-ko` | 確認套件確實裝在目前啟用的 venv 內（`pip show python-mecab-ko`），並確認腳本是最新版本（會優先呼叫 `from mecab import MeCab`，不是舊版只試 `konlpy.tag.Mecab` 的邏輯） |
| Hannanum 失敗，錯誤訊息含 `NullPointerException` | 已確定放棄此引擎（切 JDK 版本、設定 `JAVA_HOME` 皆實測無效），不需再花時間除錯；Channel 1 定案為 4 個子通道（Okt/Komoran/Kkma/Mecab-ko），不影響其餘引擎與 Channel 3 |
| `ollama` 安裝腳本報錯 `ERROR: This version requires zstd for extraction` | 先執行 `sudo apt-get install -y zstd`，再重跑安裝腳本 |
| `ollama run` 沒有反應或很慢 | 確認 `ollama pull` 已完整下載完成；純 CPU 執行也能跑但會很慢，需確認有吃到 GPU（已於使用者本機驗證正常：`nvidia-smi` 顯示記憶體用量從閒置的 1435MiB 升到 6058MiB） |
