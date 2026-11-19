#!/usr/bin/env bash
# Start backend (port 8000) and frontend (port 5173). Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
(cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT
cd frontend && npm run dev
