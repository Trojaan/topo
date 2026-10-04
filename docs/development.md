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

Status, workflow, and analysis commands use the fully validated current
generation for interactive reads. Run an explicit full-history integrity check
with:

```bash
uv run topo context verify --package /tmp/example-finances/context.topo --json
```

For a short current view, choose an explicit date:

```bash
uv run topo context summary --package /tmp/example-finances/context.topo --as-of 2026-09-29 --json
```

The result contains entity and current confirmed assertion counts, the number of
open proposals, known account balances, and net-worth diagnostics per household.
Missing or conflicting balances have no amount. A diagnostic `explain_ref` is
opened with `topo explain --ref <ref_type>:<id>`; old derived explanation files
remain historical and are not treated as diagnostics for the current generation.

Every command that consumes JSON accepts `--request PATH` or stdin. Use
`topo <group> <command> --help` for the exact contract ID and transport; use
`topo contract describe --json` for the complete mapping of financial-context
commands. `topo upgrade` and `topo --version` are installation commands outside
those context contracts.
`contract describe` and `contract schema` describe the CLI itself and do not
need `--package`. With `--json`, usage errors include `INVALID_USAGE` and a hint.

The result reports the current generation plus the numbers of retained
generations and raw evidence records checked. Mutating commands perform this
full-history validation automatically.

## Preparing a mutation wave

Keep request payloads and generated requests in a private temporary directory or
the workspace's ignored `imports/` directory. The tracked helper lives in
`scripts/`, because `imports/` is ignored. It creates the UUIDv7 operation ID,
actor and reason shell, reads `context_id` and `expected_generation` from the
validated current package, and checks the published request schema. It never
calls a mutating Topo command. For example:

```bash
uv run python scripts/topo_helpers.py build \
  --package /tmp/example.topo --command source.import \
  --payload /tmp/import-payload.json --output /tmp/import-request.json \
  --actor-type source_adapter --actor-id demo-adapter --reason 'Import reviewed records'
uv run python scripts/topo_helpers.py validate \
  --command source.import --request /tmp/import-request.json
uv run python scripts/topo_helpers.py refresh \
  --package /tmp/example.topo --command source.import \
  --request /tmp/import-request.json
```

The payload contains the command-specific fields; the helper supplies
`authorization: null` and a `batch_id` when the contract requires them. It rejects
payloads that override generated shell fields. Prepare all requests in a wave
after one substantive read of the state. Execute them sequentially, refreshing
each pending request immediately before use and inspecting each result before
continuing. A refresh keeps the request's operation ID and changes only its
expected generation. Do not refresh a request that already ran or one with
authorization filled in.

For an authorization-required operation, preview it with `authorization: null`,
have a person authorize the returned `preview_ref`, and submit the authorized
copy immediately in the same generation and with the same operation ID. Confirm
each proposal after its preview before starting the next mutation; collecting
many previews first makes them stale. `proposal.submit` has no effect-free preview.
Check its shape with the helper's `validate` command, never by submitting a
trial request. Shape validation cannot guarantee domain validity; the actual
submit can still reject an invalid assertion or evidence reference.

For reviewed source classifications, use `source classify-batch` rather than one
decision per transaction; it publishes thousands of classifications as one
generation. `discover run` is effect-free. Prefer `workflow next` and
`workflow respond` when a typed action is available, then return to
`workflow next` after a successful mutation.

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

To move an existing package to delta storage, first choose a new destination path:

```bash
uv run topo context storage-migrate --package ./context.topo --output ./context-delta.topo --json
uv run topo context verify --package ./context-delta.topo --json
```

The source package is left intact. The command preserves `CURRENT`, identifiers,
evidence and journal history and refuses to overwrite an existing destination.
Continue using the destination path after checking it. Storage migration does not
publish a financial generation and is separate from `context migrate`, which
changes the versioned financial context schema. If a later privacy-scrub must also
cover the old copy, remove or scrub that copy separately; it is outside the new
package's managed boundary.

Run effect-free recurring cashflow discovery with a `discover.run` request that
contains `context_id`, `analysis_scope`, and `as_of_date`:

```bash
uv run topo discover run --package /tmp/example.topo --request /tmp/discover.json --json
```

Use `--compact --json` to omit the embedded proposal and reference lists, or
`--table` for a readable candidate table. The compact field
`projected_next_period` predicts the next occurrence; discovery only reads
source transactions on or before the explicit `as_of_date`. Use the full JSON
view when copying a selected candidate's `proposal` into `proposal submit`.

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

Use `--compact --json` for component statuses, values, diagnostics and domain
counts without assertion-ref lists; omit `--compact` for the complete trace.
When the package has one household, these shorter forms derive the context ID,
household scope and fixed analysis version. The date is always explicit; provide
`--scope HOUSEHOLD_ID` if the package has multiple households:

```bash
uv run topo analyze run --package /tmp/example.topo --analysis context_inventory --as-of 2026-09-29 --compact --json
uv run topo discover run --package /tmp/example.topo --as-of 2026-09-29 --compact --json
uv run topo workflow next --package /tmp/example.topo --as-of 2026-09-29 --json
```

The analysis shortcut accepts `context_inventory`, `net_worth`,
`normalized_monthly_cashflow`, and `realized_monthly_cashflow`. For realized
cashflow the month containing `--as-of` becomes the half-open period. Scenario
comparison still uses an explicit JSON request because its assumptions and
reporting currency must be supplied.

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

When imported accounts are known but their balances are missing, the returned
`topo.workflow-action/0.2` action is executable without inspecting package files
or Topo's implementation. It includes the question, literal adapter/source
identity for each account, separate user and agent input paths, and a complete
`proposal.submit` request template. Fill only those declared paths. Submitting
the `workflow_response` records the normalized batch once as `workflow_answer`
evidence and atomically creates one open balance proposal per account. It does
not confirm those proposals; confirmation still requires explicit human
authorization. Do not substitute transaction evidence for the user's balance
statement.

For the proactive cycle, call `workflow.next` with
`workflow_contract_version: topo.workflow/0.2`, `include_basis_context: true`, and
the prior generation as `since_generation`. Execute its effect-free steps, submit
typed user information through `workflow.respond`, preview and authorize a pending
batch once, then call `workflow.next` again. Stop only when the returned action asks
for user information, conflict resolution, or authorization. Human output uses the
fixed headings `Zojuist gewijzigd`, `Bevestigde context`, `Openstaand en onzeker`,
`Actuele inzichten`, and `Volgende vraag`.

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

## Canonical record schemas

`topo contract record-schema entities|assertions|evidence|proposals --json`
returns the exact JSON Schema for one `topo.context/0.2` collection. A collection
has `schema_version` and `records`. An assertion indexes its subject with
`subject_ref.id`; it carries either `object_ref` or `object_value`, never both.
For money, `object_value` has `value_type: "money"` and a `value` object such as
`{"amount":"-5.00","currency":"EUR"}`. `valid_time` records when a fact
applies, `recorded_at` when it entered Topo, `verification_status` whether it is
confirmed or unverifiable, `provenance` its evidence, and `supersedes` its
predecessor. Corrections add a successor rather than editing the old assertion.

## Synthetic end-to-end CLI example

This example uses `/tmp/topo-demo.topo` and invented records. Create a package,
then read its context and generation IDs from the JSON result:

```bash
uv run topo context init --package /tmp/topo-demo.topo --json > /tmp/topo-init.json
uv run topo context summary --package /tmp/topo-demo.topo --as-of 2026-08-31 --json
```

Write `/tmp/topo-import.json` with `contract_version: "topo.cli/0.1"`, a fresh
UUIDv7 `operation_id`, `context_id` and `expected_generation` from
`/tmp/topo-init.json`, `actor` set to a source adapter, `authorization: null`,
and one invented source record such as:

```json
{"source_id":"demo-account","record_id":"demo-1","booking_date":"2026-08-31","money":{"amount":"-12.50","currency":"EUR"},"description":"Synthetic groceries"}
```

Get the complete import request shape with
`topo contract schema source.import --json`. Preview, have a person authorize the
returned `preview_ref`, and rerun **the same request** with its `authorization`
filled; no import occurs before that authorization:

```bash
uv run topo source import --package /tmp/topo-demo.topo --request /tmp/topo-import.json --json
uv run topo analyze run --package /tmp/topo-demo.topo --analysis context_inventory --as-of 2026-08-31 --compact --json
uv run topo discover run --package /tmp/topo-demo.topo --as-of 2026-08-31 --table
uv run topo workflow next --package /tmp/topo-demo.topo --as-of 2026-08-31 --json
```

Discovery needs enough dated observations to propose a recurring pattern. If a
candidate appears, retrieve the full JSON result, copy its `proposal` into a
versioned `proposal.submit` request with a fresh operation ID and current
generation, then call `proposal submit`. Preview and have a person authorize a
`proposal confirm` request before repeating it with the returned `preview_ref`.
This is the same human decision boundary as source import.

For a `workflow.next` action whose `command` is `workflow.respond`, copy its
`request_template` to `/tmp/topo-answer.json`. For an accounts question, this is
the user-owned part of the response, validated against its `user_input_schema`:

```json
{"coverage":"complete","items":[{"item_id":"01991a00-0000-7000-8000-000000000001","label":"Demo account","entity_type":"account","classification":"payment_account","money":{"amount":"1250.25","currency":"EUR"},"household_share":"1","source":{"adapter_id":"demo-adapter","source_id":"demo-account"}}]}
```

Set those `coverage` and `items` paths in the copied template, plus only the
declared agent input paths (`actor.actor_id` and the producer ID/version). Submit
with `topo workflow respond --package /tmp/topo-demo.topo --request
/tmp/topo-answer.json --json`. This creates open proposals. Call `workflow next`
again, preview and authorize its `proposal.confirm-batch` action, then repeat
until the next action requests more user information or reports no remaining
action. An older account-balance action may instead say `proposal.submit`; use
its own `request_template` and `user_input_schema` in the same way.

For clarity, a *filled* `workflow.respond` template for the same invented
accounts question looks like this. The action, context, generation and household
IDs below are illustrative: copy those four values from the actual
`workflow.next` output instead of reusing them literally.

```json
{
  "contract_version": "topo.cli/0.1",
  "operation_id": "01991a00-0000-7000-8000-000000000010",
  "context_id": "01991a00-0000-7000-8000-000000000011",
  "expected_generation": "01991a00-0000-7000-8000-000000000012",
  "actor": {"actor_type": "agent", "actor_id": "local-agent"},
  "reason": "Answer basis-context action 01991a00-0000-7000-8000-000000000010",
  "workflow_response": {
    "action_id": "01991a00-0000-7000-8000-000000000010",
    "response_type": "context_inventory",
    "section_id": "accounts",
    "analysis_scope": {"scope_type": "household", "entity_id": "01991a00-0000-7000-8000-000000000013"},
    "as_of_date": "2026-08-31",
    "producer": {"producer_type": "agent", "producer_id": "local-agent", "producer_version": "0.1.0"},
    "coverage": "complete",
    "items": [{
      "item_id": "01991a00-0000-7000-8000-000000000001",
      "label": "Demo account",
      "entity_type": "account",
      "classification": "payment_account",
      "money": {"amount": "1250.25", "currency": "EUR"},
      "household_share": "1",
      "source": {"adapter_id": "demo-adapter", "source_id": "demo-account"}
    }]
  }
}
```

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
against the public release. A standalone install can run `topo upgrade` to
download the latest published release for its platform. The command checks the
downloaded executable's version before replacing the current binary. On Windows,
replacement is scheduled for immediately after the CLI exits because Windows
locks the running executable. Python and `uv` installations use their package
manager to upgrade instead.

### Bulk proposal submission and performance reproduction

Use `topo proposal submit-batch --package PACKAGE --json` with the usual mutation
metadata, a `proposals` array of 1–1,000 ordinary assertion-proposal inputs, and
optional `authorization`. Without authorization the command returns a preview;
a person authorizes its exact `preview_ref` before the same request is executed.
One operation ID covers all items. The result's `items` array maps every input
index to its open proposal ID. A batch never confirms those proposals as facts.
Inspect its published contract with `topo contract schema proposal.submit-batch`.

Run `uv run python scripts/benchmark_mutations.py --submit-round --output /tmp/topo-performance.json`
for an isolated synthetic 7,500-record, 21-generation fixture, complete verify,
three daily reads, ten authorized single-record source mutations and peak memory.
The reference disables record/fragment reuse and supplied change sets while
preserving the same invariants; it is not an archived pre-change executable.
Ordinary elapsed times and instrumented exclusive-function timings are separate.
See [Performance measurements](performance.md) for the recorded results.
