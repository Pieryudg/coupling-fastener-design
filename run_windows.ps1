$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" qt_fastener_app.py
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -c "import PySide6" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PySide6 is required for the native desktop app."
        Write-Host "Run: .\setup_windows.ps1"
        exit 1
    }
    & py -3 qt_fastener_app.py
} else {
    & python -c "import PySide6" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PySide6 is required for the native desktop app."
        Write-Host "Run: .\setup_windows.ps1"
        exit 1
    }
    & python qt_fastener_app.py
}
