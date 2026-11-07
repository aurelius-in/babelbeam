#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/services/backend:$ROOT/services/worker:$ROOT/packages/runtime"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi
python="${ROOT}/.venv/bin/python"
if [[ ! -x "$python" ]]; then
  python="$(command -v python3)"
fi
"$python" -m uvicorn app.main:app --app-dir "$ROOT/services/backend" --reload --port 8000 &
api_pid=$!
"$python" -m worker.main &
worker_pid=$!
cleanup() {
  kill "$api_pid" "$worker_pid" 2>/dev/null || true
}
trap cleanup EXIT
cd "$ROOT/apps/web"
npm run dev -- --host 0.0.0.0 --port 5173
