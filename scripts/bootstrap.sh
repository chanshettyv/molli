#!/usr/bin/env bash
# Bootstrap a fresh local clone of the Molli repo.
# Run from the repo root: bash scripts/bootstrap.sh

set -euo pipefail

echo "==> Checking for uv"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install from https://docs.astral.sh/uv/ and re-run."
  exit 1
fi

echo "==> Installing Python deps"
uv sync --all-packages

echo "==> Installing pre-commit hooks"
uv run pre-commit install

echo "==> Copying .env.example -> .env (if missing)"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    Edit .env to fill in your local config."
fi

echo "==> Done. Next steps:"
echo "    1. gcloud auth application-default login"
echo "    2. cd chat-service && uv run uvicorn app.main:app --reload --port 8080"
