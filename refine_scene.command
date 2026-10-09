#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTORCH_ENABLE_MPS_FALLBACK=1
export MPLCONFIGDIR="$ROOT/.cache/matplotlib"
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -u scripts/refine_scene.py "$@"
