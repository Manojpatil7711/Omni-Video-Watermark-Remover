#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

INPUT_VIDEO="${1:-input.mp4}"
OUTPUT_VIDEO="${2:-clean_output.mp4}"
MODE="${3:-static}"
ENGINE="${4:-fast}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "=== Installing FFmpeg ==="
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq ffmpeg
  elif command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "ERROR: FFmpeg is required. Install it manually." >&2
    exit 1
  fi
fi

PYTHON="${PYTHON:-python3}"
"$PYTHON" -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

if [[ ! -f "$INPUT_VIDEO" ]]; then
  echo "ERROR: Input video not found: $INPUT_VIDEO" >&2
  exit 2
fi

python -m omni_watermark.cli --input "$INPUT_VIDEO" --output "$OUTPUT_VIDEO" --mode "$MODE" --engine "$ENGINE"
echo "=== Complete: $OUTPUT_VIDEO ==="
