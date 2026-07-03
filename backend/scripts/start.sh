#!/usr/bin/env bash
# AERO-SHIELD X — Linux/macOS Startup Script
# Usage: bash scripts/start.sh [--prod] [--host 0.0.0.0] [--port 8000]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

HOST="0.0.0.0"
PORT="8000"
PROD=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prod)   PROD=true; shift ;;
        --host)   HOST="$2"; shift 2 ;;
        --port)   PORT="$2"; shift 2 ;;
        *)        echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "=== AERO-SHIELD X Backend ==="

# Activate virtual environment if present
if [[ -f "$BACKEND_DIR/.venv/bin/activate" ]]; then
    echo "[*] Activating virtual environment..."
    source "$BACKEND_DIR/.venv/bin/activate"
fi

# Verify .env exists
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
    echo "[!] .env not found. Copy deployment/.env.example to backend/.env and fill in values."
    exit 1
fi

cd "$BACKEND_DIR"

if $PROD; then
    echo "[*] Starting in PRODUCTION mode (2 workers)"
    exec python -m uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers 2 \
        --log-level info \
        --access-log
else
    echo "[*] Starting in DEVELOPMENT mode (hot reload enabled)"
    exec python -m uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        --log-level info
fi
