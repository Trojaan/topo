#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

uv run python scripts/check_architecture.py
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests
scripts/e2e.sh
