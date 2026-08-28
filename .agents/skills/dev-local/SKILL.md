---
name: dev-local
description: Set up or inspect Topo locally; use for "start dev", "dev local", "run the stack", or "local setup".
---

# Topo local development

Topo is a short-lived CLI. It has no server, port, container, or infrastructure.

| Component | Command | Port | Depends on |
| --- | --- | --- | --- |
| Topo CLI | `uv run topo …` | none | Python 3.12+, uv |

Run `scripts/dev-local.sh setup` once. Use `up` for preflight and a CLI smoke test;
`status`, `logs cli`, `restart cli`, `down`, and `attach` provide the common
launcher interface. If status reports a missing environment, rerun `setup`. CLI
output is stdout/stderr; there is no background window or persistent log.
