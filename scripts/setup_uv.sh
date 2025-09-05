#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/setup_uv.sh [keyword] [limit] [export]
#   export: none|excel|media|all|media-image|media-video (default: excel)

KEYWORD=${1:-榴莲}
LIMIT=${2:-50}
EXPORT=${3:-excel}

echo "[1/4] uv sync"
uv sync

echo "[2/4] npm ci (using global Node)"
npm ci

echo "[3/4] running env check + search"
uv run python scripts/check_env.py --keyword "$KEYWORD" --limit "$LIMIT" --export "$EXPORT"

echo "[4/4] done"

