@echo off
chcp 65001 >nul
echo [啟動中] 正在呼叫 PowerShell 啟動韓文學習字幕擷取系統...
powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [提示] 若啟動失敗，請先以管理員身份執行部署腳本 deploy.ps1
    pause
)
