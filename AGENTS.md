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
src/topo/              Engine, CLI, contracts, modules, storage
tests/                 Unit and integration tests
e2e/                   Black-box CLI journeys
docs/                  Maintainer system of record
scripts/               Local launcher, lints, and verification entry points
.agents/skills/        Repo-local agent workflows
.githooks/             Opt-in lightweight commit checks
.scratch/              Historical design work; not the current source of truth
```

## Golden rules

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
