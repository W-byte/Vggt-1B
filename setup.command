#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3.12}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ is required; 3.12 is tested"'
command -v git >/dev/null
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/fetch_upstream.py
printf '\nSources and dependencies ready. Download weights next; see README.md.\n'
