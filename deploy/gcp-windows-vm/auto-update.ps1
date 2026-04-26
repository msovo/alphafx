# Pulls latest from the deployed branch and restarts the AlphaBot service
# if anything changed. Triggered every 15 min by Task Scheduler.
param(
    [string]$InstallDir = "C:\alphabot-fx",
    [string]$Branch     = "feature/multi-user-platform",
    [string]$ServiceName = "AlphaBotFX"
)

$ErrorActionPreference = "Stop"
Push-Location $InstallDir

git fetch origin $Branch | Out-Null
$local  = git rev-parse HEAD
$remote = git rev-parse "origin/$Branch"

if ($local -eq $remote) {
    Write-Host "$(Get-Date -Format s)  up to date ($local)"
    Pop-Location
    exit 0
}

Write-Host "$(Get-Date -Format s)  updating $local -> $remote"
git reset --hard "origin/$Branch"

# Re-install deps if requirements.txt changed in this pull
$diff = git diff --name-only $local $remote
if ($diff -match "requirements\.txt") {
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host "$(Get-Date -Format s)  restarting $ServiceName"
Restart-Service $ServiceName -Force
Pop-Location
