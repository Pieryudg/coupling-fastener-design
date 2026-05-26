#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

"$PYTHON" -c "import PySide6" >/dev/null 2>&1
if [ "$?" -ne 0 ]; then
  echo "PySide6 is required for the native desktop app."
  echo "Run: ./setup_macos.command"
  exit 1
fi

"$PYTHON" qt_fastener_app.py
