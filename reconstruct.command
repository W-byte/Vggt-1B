#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT/vendor/vggt:$ROOT/humanoid-video-to-3D${PYTHONPATH:+:$PYTHONPATH}"
export MPLCONFIGDIR="$ROOT/.cache/matplotlib"
export HF_HOME="$ROOT/.cache/huggingface"
export PYTORCH_ENABLE_MPS_FALLBACK=1
export VGGT_CHECKPOINT="$ROOT/models/VGGT-1B/model.safetensors"
if [[ $# -lt 1 ]]; then echo 'Usage: bash reconstruct.command /absolute/path/video.mp4 [--output outputs/run]'; exit 2; fi
VIDEO="$1"
shift
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -u "$ROOT/humanoid-video-to-3D/run.py" "$VIDEO" --model vggt --frames 16 --image-size 392 --no-viewer --no-turntable "$@"
