# 專案架構概覽與模組速查索引 (Quick Reference & Index)

歡迎使用本專案架構解析目錄！本專案旨在透過電腦視覺（OCR）與自然語言處理（NLP），從任意韓文教學或對話影片中自動化抽取字幕並生成結構化單字學習卡片。

---

## 📚 說明文件導覽

本獨立資料夾包含完整的專案分析與技術指南，為具備 **Python、OCR、LLM** 基礎之開發者與研究人員設計：

1. **[核心技術深度解析指南 (ARCHITECTURE_DEEP_DIVE.md)](ARCHITECTURE_DEEP_DIVE.md)**：
   * **全域架構圖**：展示 Web 前端、FastAPI 調度器、8 階段非同步管線之交互關係。
   * **程式碼靜態分析**：基於 `codebase-memory-mcp` 萃取之 830 個節點與 2,475 條調用鏈結構。
   * **核心技術決策剖析**：
     * 為何影像前處理採用 CLAHE 且預設**關閉 Denoise**（去雜訊耗時多 31.2%，辨識率僅增 2.0%）。
     * 時序去重演算法如何由「逐影比對」演進為「**滑動時間窗與狀態機生命週期管理**」（解決多單字共存時切碎成 43 筆 0 秒字卡的 Bug，壓縮率由 4.9% 提升至 91.2%）。
     * 為何 **Channel 1 (Komoran 斷詞 + 5.6 萬詞權威字典)** 擊敗了本地 LLM (Ollama Qwen2.5:7b)（Channel 2 長片崩潰且留白率 37.8%、Channel 3 耗時膨脹 8 倍僅換取 +0.3% 增益）。
   * **RESTful API 介面規格**：詳細列出上傳、狀態輪詢、結果讀取、時間戳記截圖映射、CSV 匯出端點。
   * **本機快速啟動指南**：環境相依（Python/CUDA/JDK）與測試驗證命令。

---

## 🔍 系統核心管線速查 (8-Stage Pipeline)

```
[Phase 1: 採樣] ──> [Phase 2: 前處理] ──> [Phase 3: OCR] ──> [Phase 4: 時序去重] ──> [Phase 5: 語意解析] ──> [Phase 8: 匯出]
  OpenCV 定頻         灰階 + CLAHE          EasyOCR + CUDA       滑動時間窗生命週期      Channel 1 (Komoran)      Anki / CSV
  frames/ 輸出        denoise OFF           BBox/信心值提取        多文字並行合併        5.6萬詞條字典精確檢索    單字/例句/截圖
```

*若有任何擴充需求或架構疑問，請參閱各模組原始碼或相關單元測試。*
