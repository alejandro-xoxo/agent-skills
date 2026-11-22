#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-Proprietary - Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Linux/macOS equivalent of prepare.ps1: turns on automatic retrieval (local RAG) for this project.
# Looks for Python 3.10-3.14 (python3.X, then python3, then uv), creates .rag/.venv, installs fastembed and numpy,
# builds the index, registers the Claude Code hooks in .claude/settings.local.json and starts the local server.
# Tested on Linux (Arch) with Python 3.14 and fastembed 0.9.1. Usage: bash .rag/prepare.sh
set -euo pipefail
RAG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$RAG/rag.py" ] || { echo "Cannot find rag.py in $RAG" >&2; exit 1; }

echo "1/5 Looking for a compatible Python (3.10 to 3.14)..."
PY=""
for v in 3.12 3.13 3.11 3.10 3.14; do
  if command -v "python$v" >/dev/null 2>&1; then PY="$(command -v "python$v")"; echo "    Python $v: $PY"; break; fi
done
VENV="$RAG/.venv"
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1; then PY="$(command -v python3)"; echo "    Using the system python3: $PY"; fi
if [ -z "$PY" ] && [ ! -x "$VENV/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then
    echo "    No system Python: using uv to create the environment with 3.12"
    uv venv --python 3.12 "$VENV"
  else
    echo "No Python 3.10 to 3.14 and no uv. Install one and run this again." >&2
    exit 1
  fi
fi

echo "2/5 Python environment and library installation (fastembed, numpy)..."
if [ ! -x "$VENV/bin/python" ]; then "$PY" -m venv "$VENV"; fi
if command -v uv >/dev/null 2>&1 && ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  uv pip install --quiet --python "$VENV/bin/python" fastembed numpy
else
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check fastembed numpy
fi

export PYTHONUTF8=1
echo "3/5 Building the index (the first time it downloads the model, about 0.6 GB)..."
"$VENV/bin/python" "$RAG/rag.py" index
echo "4/5 Registering the Claude Code hooks..."
"$VENV/bin/python" "$RAG/rag.py" hooks
echo "5/5 Starting the local server..."
"$VENV/bin/python" "$RAG/rag.py" start
echo
echo "Done. Open /hooks once or restart the agent session so it loads the hooks. To turn it off: RAG_DISABLE=1."
