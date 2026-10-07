# Lectura: start the backend and frontend, each in its own window, then open the app.
#
#   Double-click start.bat, or run:  powershell -ExecutionPolicy Bypass -File start.ps1
#
# A server that is already running is not started twice.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

function Test-Port([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host ""
Write-Host "  Lectura - starting..." -ForegroundColor Cyan
Write-Host ""

# --- First-time setup check ---------------------------------------------------
if (-not (Test-Path $python)) {
    Write-Host "  The backend is not installed yet. Run setup first:" -ForegroundColor Yellow
    Write-Host "    powershell -ExecutionPolicy Bypass -File setup.ps1"
    Read-Host "  Press Enter to close"
    exit 1
}
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "  The frontend is not installed yet. Run setup first:" -ForegroundColor Yellow
    Write-Host "    powershell -ExecutionPolicy Bypass -File setup.ps1"
    Read-Host "  Press Enter to close"
    exit 1
}
if (-not (Test-Path (Join-Path $root "backend\.env"))) {
    Write-Host "  backend\.env is missing: copy backend\.env.example to backend\.env and add your GROQ_API_KEY." -ForegroundColor Yellow
}

# --- Backend (FastAPI on port 8000) -------------------------------------------
if (Test-Port 8000) {
    Write-Host "  Backend already running on http://127.0.0.1:8000"
} else {
    $backendCmd = "`$Host.UI.RawUI.WindowTitle = 'Lectura backend (keep open)'; " +
                  "Set-Location '$root\backend'; & '$python' -m uvicorn app.main:app --reload"
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd
    Write-Host "  Backend starting in a new window..."
}

# --- Frontend (Vite on port 5173) ---------------------------------------------
if (Test-Port 5173) {
    Write-Host "  Frontend already running on http://localhost:5173"
} else {
    $frontendCmd = "`$Host.UI.RawUI.WindowTitle = 'Lectura frontend (keep open)'; " +
                   "Set-Location '$root\frontend'; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCmd
    Write-Host "  Frontend starting in a new window..."
}

# --- Wait until both answer, then open the browser ----------------------------
Write-Host "  Waiting for the servers" -NoNewline
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline -and -not ((Test-Port 8000) -and (Test-Port 5173))) {
    Start-Sleep -Milliseconds 700
    Write-Host "." -NoNewline
}
Write-Host ""

if ((Test-Port 8000) -and (Test-Port 5173)) {
    Write-Host "  Ready! Opening http://localhost:5173" -ForegroundColor Green
    Start-Process "http://localhost:5173"
    Write-Host ""
    Write-Host "  To stop Lectura, close the two server windows (or press Ctrl+C in them)."
} else {
    Write-Host "  The servers did not start within 90 seconds. Check the two new windows for errors." -ForegroundColor Yellow
}
