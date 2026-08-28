#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="$ROOT/test-results/e2e"
mkdir -p "$RESULTS"
(cd "$ROOT" && uv run pytest e2e -vv 2>&1) | tee "$RESULTS/pytest.txt"
