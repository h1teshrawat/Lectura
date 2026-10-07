# Lectura: one-time setup on Windows.
#
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# Needs: Python 3.11, Node.js 20+, ffmpeg (see README). Safe to run again.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Require($command, $hint) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        Write-Host "  Missing: $command. $hint" -ForegroundColor Red
        exit 1
    }
}

Step "Checking requirements"
Require "py" "Install Python 3.11 from https://www.python.org/downloads/ (tick 'Add to PATH')."
Require "node" "Install Node.js LTS from https://nodejs.org/"
Require "ffmpeg" "Install it with:  winget install Gyan.FFmpeg  then open a NEW terminal."
& py -3.11 --version
if ($LASTEXITCODE -ne 0) { Write-Host "  Python 3.11 not found (py -3.11)." -ForegroundColor Red; exit 1 }
node --version

Step "Backend: virtual environment and Python packages (first time: ~10 min, PyTorch is large)"
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { & py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install -r "$root\evaluation\requirements.txt" --quiet
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created backend\.env - open it and paste your GROQ_API_KEY." -ForegroundColor Yellow
}

Step "Frontend: npm packages"
Set-Location "$root\frontend"
npm install

Step "Running the backend tests"
Set-Location "$root\backend"
& .\.venv\Scripts\python.exe -m pytest -q

Set-Location $root
Write-Host ""
Write-Host "Setup complete. Start Lectura by double-clicking start.bat" -ForegroundColor Green
