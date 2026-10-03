#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "環境建置完成。若使用 KoNLPy，請確認已安裝 JDK 11+ 並設定 JAVA_HOME。"
