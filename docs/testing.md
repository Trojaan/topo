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

The initial journey proves contract discovery, first context publication, the
client-visible success envelope, canonical persisted state, and refusal to replace
an already-published package. There is no auth or external service in v0.1, so an
auth/session helper and sandbox credential guard would be theatre; add them when
such a boundary actually exists.

The source journey also proves recurring discovery leaves `CURRENT` and proposals
unchanged, reports insufficient history, and produces a candidate that can be
selected through the ordinary proposal workflow.

The realized-cashflow journey proves half-open month selection, explicit account
allocation and coverage, paired-transfer exclusion, unclassified net movement,
component-local provisional status, and effect-free generation reuse.

The normalized-cashflow journey proves confirmed-current selection, candidate and
expired-fact exclusion, all five frequency factors, decimal intermediates, range
bounds, explicit typical amounts, and effect-free generation reuse.

When an e2e test fails, classify it as a product defect, an intentionally changed
contract, or an environment problem. Never remove an assertion just to get green.
For a CLI-visible feature, update the journey and keep evidence synthetic.
