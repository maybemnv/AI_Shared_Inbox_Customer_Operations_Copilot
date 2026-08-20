[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js and npm are required."
}

if (-not (Test-Path -LiteralPath (Join-Path $Root "apps\web\node_modules"))) {
    & npm.cmd --prefix (Join-Path $Root "apps\web") ci
}

function Start-Terminal {
    param([string]$Title, [string]$WorkingDirectory, [string]$Command)
    $safeTitle = $Title.Replace("'", "''")
    $safeDirectory = $WorkingDirectory.Replace("'", "''")
    $script = "`$Host.UI.RawUI.WindowTitle = '$safeTitle'; Set-Location -LiteralPath '$safeDirectory'; $Command"
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $script
    )
}

$apiCommand = "uv run --with-requirements requirements.txt python -m uvicorn app.main:app --host 127.0.0.1 --port 8103"
$webDirectory = Join-Path $Root "apps\web"
$webCommand = "`$env:NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8103'; npm.cmd run dev -- --hostname 127.0.0.1 --port 3103"
Start-Terminal "Shared Inbox API" $Root $apiCommand
Start-Terminal "Shared Inbox Web" $webDirectory $webCommand

Write-Host "Shared Inbox starting at http://127.0.0.1:3103/inbox"
Write-Host "API readiness: http://127.0.0.1:8103/readyz"
