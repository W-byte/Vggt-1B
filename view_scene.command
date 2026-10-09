#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ $# -lt 1 ]]; then echo 'Usage: bash view_scene.command /absolute/path/demo.rrd'; exit 2; fi
exec "$ROOT/.venv/bin/python" -m rerun "$@"
