@echo off
setlocal
title Korean Learning Subtitle Extractor
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 (
    echo.
    echo [ERROR] System failed to start.
    echo Please make sure you have executed deploy.ps1 first.
    echo.
    pause
)
endlocal
