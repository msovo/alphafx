# --------------------------------------------------------------------------
# AlphaBot FX — Windows Server startup / first-time provisioning script
# Run as Administrator on a fresh Windows Server 2022 GCE VM.
# Usage:   PowerShell -ExecutionPolicy Bypass -File startup.ps1
# --------------------------------------------------------------------------
param(
    [string]$RepoUrl    = "https://github.com/msovo/alphafx.git",
    [string]$Branch     = "feature/multi-user-platform",
    [string]$InstallDir = "C:\alphabot-fx",
    [string]$PythonVer  = "3.13.0"
)

$ErrorActionPreference = "Stop"
Write-Host "==> AlphaBot FX VM bootstrap" -ForegroundColor Cyan

# ---- 1. Chocolatey -------------------------------------------------------
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing Chocolatey"
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = `
        [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString(
        "https://community.chocolatey.org/install.ps1"))
}

# ---- 2. Core tooling -----------------------------------------------------
Write-Host "==> Installing git, python, gcloud, nssm"
choco install -y git python --version=$PythonVer gcloudsdk nssm

# Refresh PATH
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + `
            [System.Environment]::GetEnvironmentVariable("Path","User")

# ---- 3. MetaTrader 5 (silent install) ------------------------------------
$mt5Url = "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
$mt5Exe = "$env:TEMP\mt5setup.exe"
if (-not (Test-Path "C:\Program Files\MetaTrader 5\terminal64.exe")) {
    Write-Host "==> Downloading & installing MetaTrader 5"
    Invoke-WebRequest -Uri $mt5Url -OutFile $mt5Exe
    Start-Process -FilePath $mt5Exe -ArgumentList "/auto" -Wait
}

# ---- 4. Clone repo -------------------------------------------------------
if (Test-Path $InstallDir) {
    Write-Host "==> Repo exists — pulling latest"
    Push-Location $InstallDir
    git fetch origin
    git checkout $Branch
    git pull origin $Branch
    Pop-Location
} else {
    Write-Host "==> Cloning $RepoUrl ($Branch)"
    git clone --branch $Branch $RepoUrl $InstallDir
}

# ---- 5. Python venv + deps -----------------------------------------------
Push-Location $InstallDir
if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating venv"
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location

# ---- 6. Firewall: open Streamlit port ------------------------------------
if (-not (Get-NetFirewallRule -Name "AlphaBotStreamlit" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name "AlphaBotStreamlit" `
        -DisplayName "AlphaBot Streamlit (8501)" `
        -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow | Out-Null
}

# ---- 7. Install run-streamlit as a Windows service via NSSM --------------
$svcName  = "AlphaBotFX"
$venvPy   = "$InstallDir\.venv\Scripts\python.exe"
$runArgs  = "-m streamlit run dashboard\app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"

if (-not (Get-Service -Name $svcName -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing $svcName Windows service"
    nssm install $svcName $venvPy $runArgs
    nssm set     $svcName AppDirectory $InstallDir
    nssm set     $svcName Start SERVICE_AUTO_START
    nssm set     $svcName AppStdout "$InstallDir\logs\service-stdout.log"
    nssm set     $svcName AppStderr "$InstallDir\logs\service-stderr.log"
} else {
    Write-Host "==> $svcName service already installed — updating"
    nssm set     $svcName Application $venvPy
    nssm set     $svcName AppParameters $runArgs
}
Start-Service $svcName

# ---- 8. Scheduled auto-update (git pull every 15 min) --------------------
$updaterPath = "$InstallDir\deploy\gcp-windows-vm\auto-update.ps1"
if (Test-Path $updaterPath) {
    if (-not (Get-ScheduledTask -TaskName "AlphaBotAutoUpdate" -ErrorAction SilentlyContinue)) {
        Write-Host "==> Registering auto-update task"
        $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
                   -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$updaterPath`""
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
                   -RepetitionInterval (New-TimeSpan -Minutes 15)
        Register-ScheduledTask -TaskName "AlphaBotAutoUpdate" -Action $action `
            -Trigger $trigger -RunLevel Highest -User "SYSTEM"
    }
}

Write-Host ""
Write-Host "==> Done. Streamlit running on http://<VM_EXTERNAL_IP>:8501" -ForegroundColor Green
Write-Host "==> Service: Get-Service $svcName     Logs: $InstallDir\logs\"
