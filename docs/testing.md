# Testing and verification

The gate has three layers:

1. `tests/` exercises typed units and in-process integration boundaries.
2. `e2e/` invokes `python -m topo` as a real subprocess and verifies both the JSON
   contract and the durable package a user receives.
3. `scripts/verify.sh` runs architecture rules, Ruff, mypy, unit/integration tests,
   and the black-box journey in a stable order.

Run the complete gate with `scripts/verify.sh`. Run only the e2e journey with
`scripts/e2e.sh`; its terminal transcript is saved under
`test-results/e2e/pytest.txt`. Generated evidence is ignored by Git.

The opt-in read-performance gate builds a temporary synthetic package with 7,500
source records, about 30,000 assertions, and six immutable generations. After one
warm-up per command it requires the median of three separate CLI processes for
status, workflow-next, and net-worth analysis to remain below two seconds:

```bash
uv run python scripts/benchmark_reads.py
```

The fixture is deleted after the run and never contains personal financial data.
Keep this benchmark separate from the ordinary correctness gate because building
the large immutable history is intentionally expensive.

The initial journey proves contract discovery, first context publication, the
client-visible success envelope, canonical persisted state, empty-context
inventory, deterministic effect-free workflow guidance, unknown major-version
refusal, checksum write blocking, and refusal to replace an already-published
package. There is no auth or external service in v0.1, so an
auth/session helper and sandbox credential guard would be theatre; add them when
such a boundary actually exists.

The workspace journey proves a new directory receives one canonical
`context.topo/`, private import and package ignore rules, automatically discovered
Codex and Claude instructions, a read-only status projection, and an idempotent
second initialization without a new generation. Unit tests additionally prove
managed-block preservation, CRLF handling, safe updates, and fail-closed marker
or package conflicts.

The source journey also proves recurring discovery leaves `CURRENT` and proposals
unchanged, reports insufficient history, and produces a candidate that can be
selected through the ordinary proposal workflow. It also proves two known source
accounts can be answered as one workflow batch, with one new user-statement
evidence record, one open proposal per account, atomic rejection, replay, and no
transaction evidence reused as balance evidence.

The realized-cashflow journey proves half-open month selection, explicit account
allocation and coverage, paired-transfer exclusion, unclassified net movement,
component-local provisional status, and effect-free generation reuse.

The normalized-cashflow journey proves confirmed-current selection, candidate and
expired-fact exclusion, all five frequency factors, decimal intermediates, range
bounds, explicit typical amounts, and effect-free generation reuse.

The net-worth journey proves explicit allocation, per-interest deduplication,
account-plus-asset-minus-debt arithmetic, restricted-pension separation,
original-currency subtotal survival, missing-rate isolation, missing valuation
visibility, conflict localization, and an unavailable empty result without a zero
default.

The rule-package journey proves safe-YAML and capability validation, effect-free
preview traces, explicit human authorization, atomic full-package activation,
checksum-bound manifest pins, and stale-manifest conflict handling.

The context-lifecycle journey proves compatible migration, new-generation restore,
bounded retention with an explicit restore point, package-wide privacy scrub, and
explicit full-history verification through the public CLI. Unit integration tests
additionally prove incompatible migration has no effect, scrubbed assertions are
marked unverifiable, current-only reads omit retained snapshots, recovery artifacts
trigger full recovery, and retained corruption still blocks verification and
mutation.

The proactive-workflow journey validates every generated request against its
published schema, proposes manual accounts plus balances, allocation and coverage
as one batch, verifies checksum-bound authorization and atomic confirmation,
recomputes provisional net worth, and proves that the next missing basis domain is
asked immediately. Separate fixtures cover explicit empty coverage, stale
generations, rejection, replay and all-or-nothing invalid batches.

Together, `tests/` and `e2e/` are the reproducible v0.2 acceptance suite invoked by
`scripts/verify.sh`. They cover the three normative handoff journeys—empty context,
transactions to monthly cashflow, and net worth plus scenario—as well as the
minimum safety fixtures for replay, authorization, correction, stale generations,
constraints, currencies, normalization, restricted pension, explanation,
tampering, and contract-version refusal.

When an e2e test fails, classify it as a product defect, an intentionally changed
contract, or an environment problem. Never remove an assertion just to get green.
For a CLI-visible feature, update the journey and keep evidence synthetic.

CI also builds one Linux standalone executable on every change. A release tag
expands this to the five supported platform artifacts and smoke-tests each binary;
only after publication do installer jobs download and execute the released zips.
