$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (Test-Path ".venv\Scripts\python.exe") {
    $Python = ".venv\Scripts\python.exe"
    $PythonArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .venv
    $Python = ".venv\Scripts\python.exe"
    $PythonArgs = @()
} else {
    python -m venv .venv
    $Python = ".venv\Scripts\python.exe"
    $PythonArgs = @()
}

& $Python @PythonArgs -m pip install --upgrade pip
& $Python @PythonArgs -m pip install -r requirements-desktop.txt
& $Python @PythonArgs -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    & $Python @PythonArgs -m pip install pyinstaller
}

& $Python @PythonArgs -m PyInstaller `
    --noconsole `
    --onefile `
    --name CouplingFastenerDesign `
    qt_fastener_app.py

Write-Host "Built dist\CouplingFastenerDesign.exe"
