#!/usr/bin/env bash
# ============================================================
# 韓文學習字幕擷取專案 - 快速啟動腳本 (Linux / WSL / macOS)
# ============================================================
set -e

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

if [ ! -f "data/dictionary_index.sqlite3" ]; then
    echo "未偵測到辭典資料庫，自動執行建置..."
    python scripts/build_dictionary_index.py
fi

URL="http://127.0.0.1:8000"
echo "============================================================"
echo "🚀 正在啟動 韓文學習字幕擷取系統 (FastAPI + Web UI)"
echo "服務網址: $URL"
echo "============================================================"

# 若環境支援 xdg-open 則自動開啟瀏覽器
if command -v xdg-open >/dev/null 2>&1; then
    (sleep 2 && xdg-open "$URL") &
elif command -v open >/dev/null 2>&1; then
    (sleep 2 && open "$URL") &
fi

python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
