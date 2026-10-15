# Topo agent map

Topo is a local-first Python CLI that stores an immutable, auditable financial
context package. It is an engine, not an adviser or a web application.

## Start here

- Set up once: `scripts/dev-local.sh setup`
- Check the workspace: `scripts/dev-local.sh status`
- Run all ship gates: `scripts/verify.sh`
- Inspect CLI contracts: `uv run topo contract describe --json`
- Know what Topo can do: `docs/capabilities.md`
- Domain vocabulary: `CONTEXT.md`
- Documentation map: `docs/index.md`

## Project tree

```text
src/topo/              Historical engine, CLI, contracts, modules, storage
src/topo_v2/           Current-state engine and topo2 CLI
tests/                 Unit and integration tests
e2e/                   Black-box CLI journeys
docs/                  Maintainer system of record
scripts/               Local launcher, lints, and verification entry points
.agents/skills/        Repo-local agent workflows
.githooks/             Opt-in lightweight commit checks
.scratch/              Historical design work; not the current source of truth
```

## Version boundary

`src/topo/` remains the historical engine; its generation, provenance and proposal
rules below apply there. `src/topo_v2/` is a separate current-state engine, exposed
as `topo2`. Read `docs/topo2.md` for its records, CLI and agent confirmation flow.
Topo 2 never imports the old engine and overwrites only its own current JSON
context after one explicitly human-approved preview. Transactions are ordinary
records: use import-transactions and filtered/paginated transactions queries.
They never adjust stored balances. Use aggregate-transactions for compact realized totals, and filtered transactions
for details. Optional transaction kind is explicit human-approved meaning, never
inferred by the engine. Signed refunds reduce expenses; transfers and unknowns
remain separate from classified economic cashflow. A transfer half proves no pair.
Coverage declarations and classification completeness are independent. Import
preserves omitted kind/category/source; JSON null clears. Keep at most three short
clarification bundles and one joint human confirmation per coherent change.
Mechanical test tokens never count as human approval.
For monthly questions, use aggregate-transactions to prepare a few explicit cashflows,
not a second spending ledger. Frequency/ranges require source support or clarification;
a short export proves no recurrence. Document the selection behind a combined expense
and exclude separately recorded costs from it. Internal transfers are not consumption;
never deduct goal contributions twice. monthly-room uses only expectations at an
explicit reference date. Discuss known_room.lower as cautious room among known items,
with missing amounts and inventory visible; never assume a range midpoint.
Optional cashflow_settings hold a minimum balance reserve per currency and a free note;
the reserve is not deducted monthly. Imports preserve expectations/settings; transactions
never rewrite expectations, debts or balances. Plan 6's human usage gate remains open;
technical authorization does not confirm classifications or expectations.
Goals accept a short message without inventory, allocation or preference questions.
Optional reserved_amount is a confirmed destination, never proof of funds or exclusivity.
remaining_amount uses only explicit reserved_amount; missing is unknown, explicit zero
is known. Legacy linked_value stays separate and is never added to the reservation.
monthly_contribution is intention only; no payment or second monthly deduction.
priority low/normal/high and note are optional, not allocation rules. Preserve goal
enrichments on full updates and export reimports. reservation_comparison compares
known destinations per currency with known free value; possible excess and unknown
coverage never block goals or value falls and never prove joint/exclusive coverage.
minimum_reserve remains a separate balance threshold. No required contribution,
achievement month or joint feasibility yet. Human usage gates for plans 3 and 6
remain open; technical implementation confirms no financial facts or intentions.
Use report with an explicit output path and reference date for early offline HTML
insight, without financial confirmation or mandatory inventory questions. Optional
from-date/to-date are supplied together; omitted means all stored transactions,
never inferred period coverage. Report reads one snapshot and changes no context;
keep reports outside Git. Reuse shared outcomes: realized totals and expectations,
legacy linked value and goal reservations, and minimum reserve stay separate.
Never deduct goal contributions again or claim joint/exclusive coverage.
Human usage gates for plans 3, 4 and 6 remain open; report generation confirms no facts.
Topo 2 has no mutation history or proposals; transaction records from prior
years remain available. Always use synthetic fixtures and keep personal contexts
outside Git.

## Golden rules (historical Topo)

1. Only `EngineCore` owns context mutation, generation, replay, and history
   semantics. CLI and adapters translate or persist; they do not decide meaning.
2. Published generations are immutable. Validate a complete staged generation
   before atomically switching `CURRENT`; never repair canonical data silently.
3. User-interpreted meaning enters as a proposal. Only explicit human
   authorization can promote it to a confirmed fact.
4. Technical identifiers and JSON contracts are stable English and explicitly
   versioned. Human-facing domain documentation is Dutch.
5. The engine must remain deterministic and local-first. Network access and live
   external credentials are not runtime assumptions.
6. Financial calculations are ordinary typed, tested Python—not agent-editable
   declarative expressions.
7. Preserve provenance, valid time, recorded time, and prior evidence. Corrections
   supersede; they do not erase history.
8. Add a black-box e2e journey when a CLI-visible contract changes. Do not weaken
   assertions merely to make a gate green.

## Where to look

| Question | Source of truth |
| --- | --- |
| Architecture and dependency direction | `docs/architecture.md` |
| Domain boundaries and safety policy | `docs/domain.md`, then `CONTEXT.md` |
| Local commands and prerequisites | `docs/development.md` |
| Test layers and release gate | `docs/testing.md` |
| Public command schemas | `src/topo/contracts.py` |
| Mutation and replay semantics | `src/topo/engine.py` |
| Durable filesystem mechanics | `src/topo/storage.py` |
| Module ownership and constraints | `src/topo/modules.py`, `src/topo/builtin_modules.py` |
| Historical rationale | `.scratch/financial-context-engine-v0-1/` |

## Change discipline

- Use `uv`; keep `uv.lock` frozen in CI.
- Run `scripts/verify.sh` before shipping.
- Keep commits conventional: `type(scope): description` or `type: description`.
- Update the relevant `docs/` page in the same change when an invariant, command,
  package boundary, or verification flow changes.
- Treat personal financial fixtures as sensitive: generate synthetic data in
  temporary directories and never commit context packages.
