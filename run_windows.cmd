@echo off
setlocal

set "APP_DIR=%~dp0"
pushd "%APP_DIR%" >nul

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" qt_fastener_app.py
) else (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        py -3 -c "import PySide6" >nul 2>nul
        if errorlevel 1 (
            echo PySide6 is required for the native desktop app.
            echo Run: setup_windows.ps1
            popd >nul
            exit /b 1
        )
        py -3 qt_fastener_app.py
    ) else (
        python -c "import PySide6" >nul 2>nul
        if errorlevel 1 (
            echo PySide6 is required for the native desktop app.
            echo Run: setup_windows.ps1
            popd >nul
            exit /b 1
        )
        python qt_fastener_app.py
    )
)

popd >nul
