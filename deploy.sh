#!/usr/bin/env bash
# ============================================================
# 韓文學習字幕擷取專案 - 自動化環境部署腳本 (Linux / WSL / macOS)
# ============================================================
set -e

echo "============================================================"
echo "[步驟 1/5] 檢查 Python 3.10+ 環境..."
echo "============================================================"
PYTHON_BIN=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_BIN="$cmd"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[錯誤] 找不到 python3 或 python，請先安裝 Python 3.10 以上版本。" >&2
    exit 1
fi

PY_VER=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[成功] 偵測到 Python 版本: $PY_VER ($PYTHON_BIN)"

echo "============================================================"
echo "[步驟 2/5] 配置虛擬環境 (.venv)..."
echo "============================================================"
if [ ! -d ".venv" ]; then
    echo "正在建立 .venv ..."
    $PYTHON_BIN -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q

echo "============================================================"
echo "[步驟 3/5] 安裝專案依賴 (requirements.txt)..."
echo "============================================================"
pip install -r requirements.txt

echo "============================================================"
echo "[步驟 4/5] 檢查辭典索引庫 (data/dictionary_index.sqlite3)..."
echo "============================================================"
if [ ! -f "data/dictionary_index.sqlite3" ]; then
    echo "正在建置 SQLite 辭典索引..."
    python scripts/build_dictionary_index.py
else
    echo "[成功] 辭典資料庫已就緒。"
fi

echo "============================================================"
echo "[步驟 5/5] 執行回歸測試驗證..."
echo "============================================================"
python -m pytest tests/ -q

echo "============================================================"
echo "🎉 部署完成！可執行 ./start.sh 啟動系統。"
echo "============================================================"
