# Development

## Prerequisites

- Python 3.12 or newer (the project pins its preferred version in `.python-version`)
- [`uv`](https://docs.astral.sh/uv/)

There are no services, ports, containers, environment files, or secrets.

## First run

```bash
scripts/dev-local.sh setup
```

This performs a frozen `uv sync`. It is kept separate from `up`, so starting the
local environment never changes locked dependencies. CI enforces a conventional
PR title; opt into the matching local hook with
`git config core.hooksPath .githooks` when this checkout is not sharing Git config
with another worktree.

## Daily commands

```bash
scripts/dev-local.sh up       # preflight and CLI smoke check
scripts/dev-local.sh status   # tool, environment, and CLI status
scripts/dev-local.sh logs cli # explain where CLI output is written
scripts/dev-local.sh restart cli
scripts/dev-local.sh down
scripts/verify.sh             # architecture, format, types, unit, e2e
```

Because Topo is a short-lived CLI, `up`, `down`, `attach`, and `restart` do not
manage a background process. They deliberately preserve the same launcher
interface an agent can use across repositories without inventing an idle server.

For an isolated manual run, create packages below a temporary directory:

```bash
uv run topo context init --package /tmp/example.topo --json
```

After initialization, an adapter can submit the versioned `source.import` JSON
contract through stdin (or `--request`) with:

```bash
uv run topo source import --package /tmp/example.topo --request /tmp/import.json --json
```

Set `authorization` to `null` for the effect-free preview, then repeat the request
with the returned `preview_ref` and explicit human authorization. A normalized CSV
can replace the JSON `records` array with `--records-csv /tmp/transactions.csv`.
Its required columns are `source_id`, `record_id`, `booking_date`, `amount`,
`currency`, and `description`; the optional classification is supplied as the
complete trio `category`, `rule_version`, and `explanation`.

Never use real financial data in tests or committed fixtures.
