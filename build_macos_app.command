#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ ! -x ".venv/bin/python" ]; then
  ./setup_macos.command
fi
.venv/bin/python -m pip install pyinstaller
.venv/bin/python -m PyInstaller --windowed --name CouplingFastenerDesign qt_fastener_app.py
echo "Built dist/CouplingFastenerDesign.app"
