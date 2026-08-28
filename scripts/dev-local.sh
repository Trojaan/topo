#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
ok() { printf 'ok: %s\n' "$*"; }

require_uv() {
  command -v uv >/dev/null 2>&1 || die "uv is required; install it from https://docs.astral.sh/uv/"
}

require_environment() {
  require_uv
  [ -x "$ROOT/.venv/bin/python" ] || die "environment missing; run: scripts/dev-local.sh setup"
}

cmd_setup() {
  require_uv
  (cd "$ROOT" && uv sync --frozen)
  ok "dependencies synced"
  printf '%s\n' "optional local hook: git config core.hooksPath .githooks"
}

cmd_up() {
  require_environment
  (cd "$ROOT" && uv run topo contract describe --json >/dev/null)
  ok "Topo CLI is ready (no background services or ports)"
}

cmd_down() { ok "nothing to stop; Topo is a short-lived CLI"; }

cmd_status() {
  require_uv
  printf 'uv: %s\n' "$(uv --version)"
  if [ -x "$ROOT/.venv/bin/python" ]; then
    printf 'environment: ready\n'
    if (cd "$ROOT" && uv run topo contract describe --json >/dev/null 2>&1); then
      printf 'cli: ready\n'
    else
      printf 'cli: failed (run scripts/dev-local.sh setup)\n'
      return 1
    fi
  else
    printf 'environment: missing (run scripts/dev-local.sh setup)\n'
  fi
  printf 'services: none\nports: none\ninfra: none\n'
}

cmd_logs() {
  [ "${1:-cli}" = "cli" ] || die "unknown service '$1'; only 'cli' is valid"
  ok "Topo writes JSON to stdout and diagnostics to stderr; no persistent service log exists"
}

cmd_restart() {
  [ "${1:-cli}" = "cli" ] || die "unknown service '$1'; only 'cli' is valid"
  cmd_up
}

cmd_attach() { ok "nothing to attach to; run CLI commands with: uv run topo ..."; }

usage() {
  printf '%s\n' "usage: scripts/dev-local.sh {setup|up|down|status|logs [cli]|restart [cli]|attach}"
}

case "${1:-up}" in
  setup) cmd_setup ;;
  up) cmd_up ;;
  down) cmd_down ;;
  status) cmd_status ;;
  logs) cmd_logs "${2:-cli}" ;;
  restart) cmd_restart "${2:-cli}" ;;
  attach) cmd_attach ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
