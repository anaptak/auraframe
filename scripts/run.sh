#!/usr/bin/env bash
set -euo pipefail

# Always run relative to repo root
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# Optional: load env vars from .env (do NOT commit .env)
if [[ -f ".env" ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^\s*#' .env | xargs -d '\n' 2>/dev/null || true)
fi

# Ensure runtime dirs exist
mkdir -p data/cache data/logs slideshow

# Prefer the project venv; fall back to system python if not found
PY="$REPO_DIR/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

exec "$PY" "$REPO_DIR/auraframe.py"

