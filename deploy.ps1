<#
.SYNOPSIS
    韓文學習字幕擷取專案 - 自動化環境部署與驗證腳本 (Windows PowerShell)
.DESCRIPTION
    此腳本專為專案開發者與部署者設計，提供具備真實例外捕捉與診斷能力之部署流程：
    1. Python 3.10+ 版本與執行環境偵測
    2. 建立並配置專屬虛擬環境 (.venv)
    3. 自動安裝/升級依賴套件 (requirements.txt)
    4. 硬體運算環境偵測 (優先檢測 NVIDIA CUDA GPU，無則提示 CPU 降級)
    5. Java JDK 11+ 環境檢測 (KoNLPy 斷詞引擎依賴)
    6. 國立國語院韓中辭典索引庫自動建置 (XML -> SQLite)
    7. 執行回歸測試驗證系統完整度
#>

[CmdletBinding()]
param(
    [switch]$SkipTests = $false
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function Write-Step {
    param([string]$Title)
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "[步驟] $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Msg)
    Write-Host "[成功] $Msg" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Msg)
    Write-Host "[警告] $Msg" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Msg, [System.Exception]$Exception = $null)
    Write-Host "`n[錯誤中斷] $Msg" -ForegroundColor Red
    if ($Exception) {
        Write-Host ">>> 例外類型: $($Exception.GetType().FullName)" -ForegroundColor Red
        Write-Host ">>> 詳細原因: $($Exception.Message)" -ForegroundColor Red
        if ($Exception.StackTrace) {
            Write-Host ">>> 堆疊追蹤:`n$($Exception.StackTrace)" -ForegroundColor DarkGray
        }
    }
    Write-Host "請依上方錯誤訊息進行排查後重試。`n" -ForegroundColor Red
    exit 1
}

# 1. 偵測 Python
Write-Step "1/7 偵測 Python 執行環境"
try {
    $pythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonCmd) {
        $pythonCmd = (Get-Command py -ErrorAction SilentlyContinue).Source
    }
    if (-not $pythonCmd) {
        throw [System.IO.FileNotFoundException]"系統找不到 python 或 py 指令，請確認已安裝 Python 3.10+ 並加入 PATH 環境變數。"
    }
    $pyVerRaw = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    $pyMajorMinor = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ([double]$pyMajorMinor -lt 3.10) {
        throw [System.NotSupportedException]"偵測到的 Python 版本為 $pyVerRaw，本專案要求 Python 3.10 以上版本。"
    }
    Write-Success "偵測到 Python $pyVerRaw ($pythonCmd)"
} catch {
    Write-Fail "Python 環境檢驗失敗" $_.Exception
}

# 2. 建立或檢查虛擬環境
Write-Step "2/7 建立與配置虛擬環境 (.venv)"
$venvDir = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPythonLinux = Join-Path $venvDir "bin/python"
    if (Test-Path $venvPythonLinux) {
        $venvPython = $venvPythonLinux
    }
}

try {
    if (-not (Test-Path $venvPython)) {
        Write-Host "正在建立虛擬環境於 $venvDir ..." -ForegroundColor Gray
        & $pythonCmd -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            throw [System.InvalidOperationException]"venv 建立失敗，結束碼為 $LASTEXITCODE"
        }
        Write-Success "虛擬環境建立完成"
    } else {
        Write-Success "既有虛擬環境已就緒 ($venvDir)"
    }
} catch {
    Write-Fail "虛擬環境初始化異常" $_.Exception
}

# 3. 安裝依賴套件
Write-Step "3/7 安裝專案依賴套件 (requirements.txt)"
try {
    Write-Host "升級 pip 工具庫..." -ForegroundColor Gray
    & $venvPython -m pip install --upgrade pip -q
    
    $reqFile = Join-Path $PSScriptRoot "requirements.txt"
    if (-not (Test-Path $reqFile)) {
        throw [System.IO.FileNotFoundException]"找不到 requirements.txt 依賴清單檔案 ($reqFile)"
    }
    
    Write-Host "正在安裝套件（包含 EasyOCR、KoNLPy、FastAPI 等），初次執行可能需要數分鐘..." -ForegroundColor Gray
    & $venvPython -m pip install --prefer-binary --extra-index-url https://download.pytorch.org/whl/cu126 -r $reqFile
    if ($LASTEXITCODE -ne 0) {
        throw [System.InvalidOperationException]"pip install 執行失敗，結束碼為 $LASTEXITCODE。若缺少特定 C/C++ 編譯環境，請優先使用官方預編譯二進位 Wheel 套件或推薦之 Python 3.10-3.12 版本。"
    }
    Write-Success "所有相依套件安裝完畢"
} catch {
    Write-Fail "套件依賴安裝失敗" $_.Exception
}

# 4. 硬體運算環境檢測 (GPU/CPU) 與自動修復
Write-Step "4/7 偵測硬體運算加速裝置 (GPU / CPU)"
try {
    $gpuProbeScript = "from src.ocr.gpu_check import check_nvidia_hardware, detect_compute_device; has_hw, hw = check_nvidia_hardware(); use_gpu, _, _ = detect_compute_device(verbose=False); print(f'HAS_HW={has_hw};HW={hw};USE_GPU={use_gpu}')"
    $probeOutput = & $venvPython -c $gpuProbeScript
    $hasHw = $probeOutput -match "HAS_HW=True"
    $useGpu = $probeOutput -match "USE_GPU=True"
    if ($hasHw -and -not $useGpu) {
        Write-Warn "偵測到本機具有實體 NVIDIA 顯示卡，但目前 PyTorch 缺少 CUDA 支援（為 CPU 版）。"
        Write-Host "正在為您自動下載並修復安裝 NVIDIA CUDA 12.6 加速版 PyTorch..." -ForegroundColor Cyan
        & $venvPython -m pip install --force-reinstall --no-deps torch torchvision --index-url https://download.pytorch.org/whl/cu126
        if ($LASTEXITCODE -eq 0) {
            Write-Success "已成功修復 PyTorch CUDA GPU 加速支援！"
        } else {
            Write-Warn "CUDA 版 PyTorch 安裝失敗，系統將維持 CPU 降級相容模式。"
        }
    }
    $gpuCheckScript = "from src.ocr.gpu_check import detect_compute_device; detect_compute_device(verbose=True)"
    & $venvPython -c $gpuCheckScript
} catch {
    Write-Warn "硬體檢測引發例外，系統將自動以 CPU 模式執行: $($_.Exception.Message)"
}

# 5. Java JDK 檢測 (KoNLPy / Komoran 斷詞依賴)
Write-Step "5/7 檢測 Java JDK 執行環境"
try {
    $javaCmd = (Get-Command java -ErrorAction SilentlyContinue).Source
    if ($javaCmd) {
        $javaVer = (cmd.exe /c "java -version 2>&1" | Select-Object -First 1)
        Write-Success "偵測到 Java 執行環境: $javaVer"
        if ($env:JAVA_HOME) {
            Write-Success "JAVA_HOME 變數已配置: $env:JAVA_HOME"
        } else {
            Write-Warn "未偵測到 JAVA_HOME 環境變數，若 KoNLPy JVM 啟動異常，請確認設定 JAVA_HOME。"
        }
    } else {
        Write-Warn "未偵測到 java 指令。Channel 1 之 Komoran/Kkma 引擎需要 OpenJDK 11+；建議安裝 Java JDK。"
    }
} catch {
    Write-Warn "Java 檢驗異常: $($_.Exception.Message)"
}

# 6. 建置國立國語院辭典資料庫索引
Write-Step "6/7 國立國語院辭典資料庫索引 (SQLite) 檢查與建置"
$dictDbPath = Join-Path $PSScriptRoot "data\dictionary_index.sqlite3"
$xmlDir = Join-Path $PSScriptRoot "韩中字典xml"
try {
    if (Test-Path $dictDbPath) {
        $dbSize = (Get-Item $dictDbPath).Length / 1MB
        Write-Success "辭典資料庫已存在 ($([Math]::Round($dbSize, 1)) MB)，略過建置步驟。"
    } else {
        if (-not (Test-Path $xmlDir)) {
            throw [System.IO.DirectoryNotFoundException]"未找到辭典來源 XML 目錄 ($xmlDir)，無法建置字典索引庫！"
        }
        Write-Host "正在解析韓中辭典 XML 並建置高效能 SQLite 索引（約 5.6 萬詞條）..." -ForegroundColor Gray
        $buildScript = Join-Path $PSScriptRoot "scripts\build_dictionary_index.py"
        & $venvPython $buildScript
        if ($LASTEXITCODE -ne 0) {
            throw [System.InvalidOperationException]"辭典建置腳本失敗，結束碼為 $LASTEXITCODE"
        }
        Write-Success "辭典資料庫索引建置成功 -> $dictDbPath"
    }
} catch {
    Write-Fail "辭典索引建置失敗" $_.Exception
}

# 7. 系統完整度自動回歸測試
Write-Step "7/7 執行系統自動化回歸測試"
if ($SkipTests) {
    Write-Warn "使用者指定 -SkipTests，略過自動化測試。"
} else {
    try {
        Write-Host "正在執行 pytest 核心測試套件..." -ForegroundColor Gray
        & $venvPython -m pytest tests/ -q
        if ($LASTEXITCODE -ne 0) {
            throw [System.InvalidOperationException]"單元測試未完全通過，請檢視上方錯誤日誌以確保環境一致性。"
        }
        Write-Success "核心測試套件驗證通過！"
    } catch {
        Write-Fail "回歸測試驗證失敗" $_.Exception
    }
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "🎉 專案環境部署全部完成！" -ForegroundColor Green
Write-Host "您現在可以執行 .\start.ps1 啟動後端服務與網頁操作介面。" -ForegroundColor Green
Write-Host "============================================================`n" -ForegroundColor Green
