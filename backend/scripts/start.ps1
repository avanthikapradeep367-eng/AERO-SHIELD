# AERO-SHIELD X — Windows PowerShell Startup Script
# Run from the backend/ directory: .\scripts\start.ps1

param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$Reload,
    [switch]$Prod
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Split-Path -Parent $ScriptDir

Write-Host "=== AERO-SHIELD X Backend ===" -ForegroundColor Cyan

# Activate virtual environment if present
$VenvActivate = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
    & $VenvActivate
} else {
    Write-Host "[!] No .venv found — using system Python" -ForegroundColor Yellow
}

# Verify .env exists
$EnvFile = Join-Path $BackendDir ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "[!] .env not found. Copy deployment/.env.example to backend/.env and fill in values." -ForegroundColor Red
    exit 1
}

# Build uvicorn command
$UvicornArgs = @(
    "app.main:app",
    "--host", $Host,
    "--port", $Port,
    "--log-level", "info"
)

if ($Reload -or -not $Prod) {
    $UvicornArgs += "--reload"
    Write-Host "[*] Starting in DEVELOPMENT mode (hot reload enabled)" -ForegroundColor Green
} else {
    $UvicornArgs += "--workers"
    $UvicornArgs += "2"
    Write-Host "[*] Starting in PRODUCTION mode (2 workers)" -ForegroundColor Green
}

Write-Host "[*] Listening on http://${Host}:${Port}" -ForegroundColor Cyan
Write-Host "[*] API docs: http://localhost:${Port}/docs" -ForegroundColor Cyan
Write-Host ""

Set-Location $BackendDir
& python -m uvicorn @UvicornArgs
