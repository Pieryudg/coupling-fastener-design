#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-desktop.txt
echo "Ready. Run ./run_macos.command"
