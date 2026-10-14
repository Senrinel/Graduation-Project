<#
.SYNOPSIS
    韓文學習字幕擷取專案 - 一鍵快速啟動腳本 (Windows PowerShell)
.DESCRIPTION
    此腳本用於已部署完成之環境，自動：
    1. 驗證虛擬環境與必要字典資料庫
    2. 自動啟動 FastAPI 後端伺服器 (uvicorn)
    3. 自動開啟預設瀏覽器至 http://localhost:8000 操作介面
#>

[CmdletBinding()]
param(
    [string]$HostIP = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$venvDir = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPythonLinux = Join-Path $venvDir "bin/python"
    if (Test-Path $venvPythonLinux) {
        $venvPython = $venvPythonLinux
    }
}

if (-not (Test-Path $venvPython)) {
    # 若無 .venv，嘗試系統全域 python
    $systemPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($systemPython) {
        $venvPython = $systemPython
        Write-Host "[提示] 未檢測到 .venv，使用系統 Python ($systemPython) 嘗試啟動..." -ForegroundColor Yellow
    } else {
        Write-Host "[錯誤] 尚未檢測到虛擬環境 (.venv) 或 Python。" -ForegroundColor Red
        Write-Host "請先執行環境部署腳本： .\deploy.ps1" -ForegroundColor Yellow
        exit 1
    }
}

$dictDbPath = Join-Path $PSScriptRoot "data\dictionary_index.sqlite3"
if (-not (Test-Path $dictDbPath)) {
    Write-Host "[警告] 未檢測到辭典資料庫 ($dictDbPath)。" -ForegroundColor Yellow
    Write-Host "正在為您自動建置辭典索引（需時約 10 秒）..." -ForegroundColor Gray
    & $venvPython (Join-Path $PSScriptRoot "scripts\build_dictionary_index.py")
}

$url = "http://$HostIP`:$Port"
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "🚀 正在啟動 韓文學習字幕擷取系統 (FastAPI + Web UI)" -ForegroundColor Cyan
Write-Host "服務網址: $url" -ForegroundColor Green
Write-Host "提示: 按 Ctrl + C 可隨時中斷並關閉服務" -ForegroundColor DarkGray
Write-Host "============================================================`n" -ForegroundColor Cyan

# 於背景稍微延遲啟動瀏覽器，確保伺服器監聽埠已就緒
Start-Job -ScriptBlock {
    param($targetUrl)
    Start-Sleep -Seconds 2
    Start-Process $targetUrl
} -ArgumentList $url | Out-Null

# 啟動 Uvicorn 伺服器
& $venvPython -m uvicorn src.api.main:app --host $HostIP --port $Port
