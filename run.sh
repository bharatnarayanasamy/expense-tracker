#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if ! python -c "import fastapi" 2>/dev/null; then
  echo "Missing Python packages. Run: ./scripts/bootstrap.sh" >&2
  exit 1
fi

exec python -m expense_tracker "$@"
