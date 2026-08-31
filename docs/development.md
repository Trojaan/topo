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

To exercise the end-user bootstrap instead, create an agent-ready workspace. The
second invocation is idempotent and may update only Topo-managed marker blocks:

```bash
uv run topo init /tmp/example-finances
uv run topo init /tmp/example-finances --json
uv run topo context status --package /tmp/example-finances/context.topo --json
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

Context lifecycle commands accept their versioned JSON request through stdin or
`--request`, like every other mutating command:

```bash
uv run topo context migrate --package /tmp/example.topo --request /tmp/migrate.json --json
uv run topo context restore --package /tmp/example.topo --request /tmp/restore.json --json
uv run topo context compact --package /tmp/example.topo --request /tmp/compact.json --json
uv run topo context privacy-scrub --package /tmp/example.topo --request /tmp/scrub.json --json
```

Migration names the target package version, context-schema version, and complete
`target_module_versions` mapping. Restore names one retained generation. Compaction
requires `retain_latest` between 1 and 100 and may
protect additional `restore_generations`. Privacy scrub requires one or more
unique `evidence_ids`; it permanently removes them from the Topo-managed package,
but cannot erase SSD remnants, operating-system snapshots, synchronized copies,
or external backups.

Run effect-free recurring cashflow discovery with a `discover.run` request that
contains `context_id`, `analysis_scope`, and `as_of_date`:

```bash
uv run topo discover run --package /tmp/example.topo --request /tmp/discover.json --json
```

The response keeps `generation_before` and `generation_after` equal. To retain a
selected candidate, copy its `proposal` object into an explicit `proposal submit`
request.

Run an effect-free realized cashflow analysis with an `analyze.run` request. Use
`analysis_id` `analysis.realized_monthly_cashflow`, contract version `0.1`, an
explicit scope, a calendar-month `period` with exclusive `end_date`, and a
reporting currency:

```bash
uv run topo analyze run --package /tmp/example.topo --request /tmp/analyze.json --json
```

The source import result exposes stable `account_refs`. Confirm household
allocation and `domain.accounts/transaction_coverage` assertions on those account
entities before expecting complete month totals.

For the current structural month view, use analysis ID
`analysis.normalized_monthly_cashflow`, set `period` to `null`, and provide the
peildatum in `as_of_date`. Only confirmed recurring-cashflow assertions that are
valid on that date contribute. Fixed amounts produce exact values; ranges keep
minimum and maximum values, while `typical_money` produces an expected value only
when it was explicitly confirmed with the range.

For conservative net worth, use `analysis.net_worth`, set `period` and `scenario`
to `null`, and provide the valuation date in `as_of_date`. Confirmed values use
`domain.accounts/balance`, `domain.assets/value`,
`jurisdiction.nl/valuation/woz`, `domain.debts/balance`, or
`domain.pensions/value`, with a `money` object plus `economic_interest_ref` and
the matching `valuation_basis` in `module_data`. Pass only explicitly allowed,
date-matching `topo.core/exchange_rate` assertion refs in `reporting_currency`.
Without such a rate, original-currency subtotals remain usable and the converted
total is unavailable.

Ask for the next net-worth workflow action with an explicit `workflow.next`
request. The request file contains the package's `context_id`, the selected
`analysis_scope`, and an explicit `as_of_date`; `analysis_id` is currently
`analysis.net_worth`:

```bash
uv run topo workflow next --package /tmp/example.topo --request /tmp/workflow-next.json --json
```

The same JSON may be supplied through stdin. `--package` selects storage; it does
not silently choose the analysis scope or valuation date.

For an effect-free scenario comparison, use `analysis.scenario_comparison`, a
future `as_of_date`, one reporting currency, and a non-empty `scenario` with a
stable `scenario_id`. The only accepted assumption types are
`recurring_cashflow_change`, `one_off_cashflow`, and `value_override`; each has an
entity target, money, effective date, and reason. A value override must be dated
exactly on the scenario date. The response returns separate `baseline`, `scenario`,
and `delta` views and never changes `CURRENT`.

Validate and preview a declarative package with `rule validate` and `rule preview`.
Pass its YAML through the JSON field `rule_package_yaml`, or use `--rules` with a
local YAML file. Both requests include the current `context_id` and
`expected_generation`. Activation uses `rule activate` with mutation metadata;
first send `authorization: null`, then bind explicit human authorization to the
returned `preview_ref`. Only the authorized call may advance `CURRENT`.

Explain any returned `explain_ref` by joining its `ref_type` and `id` with a
colon. Proposal IDs use `proposal:<id>` and successful proposal decisions return
their complete `decision:<mutation-id>` reference directly:

```bash
uv run topo explain --package /tmp/example.topo \
  --ref analysis_component:0198f1a0-0000-7000-8000-000000000001 --json
```

The response repeats the used generation, CLI and analysis contract versions,
module versions, assertion and evidence refs, requirements, assumptions,
calculation steps, unrounded intermediates, and rounding. Unknown or damaged
derived references return an explicit diagnostic with an empty result.

Never use real financial data in tests or committed fixtures.

## Standalone builds and releases

The package version has one source of truth in `src/topo/__about__.py`; Hatchling,
the wheel, `topo --version`, and PyInstaller all consume it. Build a local
standalone executable with:

```bash
uv sync --frozen --no-dev --group build
uv run pyinstaller --clean topo.spec
dist/topo --version
```

Pushing a tag matching `v<package-version>` runs the release matrix for macOS
x64/arm64, glibc Linux x64/arm64, and Windows x64. Each executable completes the
contract, workspace-init, and context-status smoke flow before upload. After all
artifacts are published, the same workflow runs `install.sh` or `install.ps1`
against the public release. Re-run an installer to upgrade; there is no in-CLI
self-update command in v0.1.
