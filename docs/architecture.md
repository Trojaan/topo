# Architecture

Topo 0.1 is one Python package and one command-line process. It has no server,
database, queue, container, port, or required network service.

```text
user/agent -> CLI -> contracts -> EngineCore -> storage adapter -> .topo package
               |         |             |
               |         |             +-> module catalog / domain constraints
               |         +-> versioned JSON request and response envelopes
               +-> workspace adapter -> agent files / privacy ignore rules
```

## Responsibilities

- `cli.py` parses commands, reads request JSON, maps errors, and writes a stable
  JSON envelope. It contains no domain decisions.
- `workspace.py` scaffolds an agent-ready directory and merges explicitly marked
  instruction and ignore blocks. It delegates canonical context creation and
  validation to `EngineCore`; it never writes inside a package itself.
- `contracts.py` owns discoverable input/output schemas and request validation.
- `engine.py` owns mutations, authorization, idempotency, generations, history,
  replay, and orchestration of effect-free analyses. This is the semantic
  transaction boundary.
- `context_inventory.py` evaluates goal-bound requirements against validated
  context and selects typed follow-up actions without publishing a generation.
- `models.py` contains typed canonical records; `canonical_validation.py` checks a
  complete stored snapshot.
- `realized_cashflow.py` is an effect-free analysis module. It reads validated
  generations and emits traceable decimal calculations.
- `normalized_cashflow.py` is an effect-free analysis module. It selects only
  confirmed recurring cashflows valid on the requested date and publishes exact
  frequency factors, unrounded decimal intermediates, and presented totals.
- `net_worth.py` is an effect-free analysis module. It resolves current values by
  economic interest and explicit scope allocation, keeps restricted pension and
  original currencies separate, and localizes valuation and conversion gaps.
- `scenario.py` is an effect-free analysis module that composes the public
  normalized-cashflow and net-worth calculations. It applies only closed,
  explicitly dated assumptions in memory and publishes baseline, scenario, and
  delta components without creating a canonical generation.
- `modules.py` defines the extension contract. `builtin_modules.py` supplies the
  versioned universal and Dutch capabilities.
- `rules.py` parses safe YAML into a closed typed model and owns the trusted
  registry of versioned input views, predicates, arguments, and outcome
  capabilities. It cannot import the engine or storage.
- `storage.py` is a meaning-free adapter: locking, staging, durable writes,
  atomic publication, and crash recovery. Its checksummed evidence inventory
  contains opaque paths only; canonical validation remains an engine concern.
  Retention and privacy operations receive a complete EngineCore-approved rewrite;
  the adapter only validates, stages, swaps, and removes opaque artifacts.
- `explanations.py` projects already-decided proposals, decisions, diagnostics,
  rule traces, and analysis components into one locale-independent explanation
  shape. `EngineCore` may cache those opaque bytes under `derived/explanations`;
  the cache is outside canonical generations and never changes financial state.

## Dependency direction

Foundation modules (`identifiers`, `models`, `errors`) must not import orchestration
or persistence. Contracts and semantic modules may depend on the foundation but
not on the CLI, engine, or storage. The engine composes semantic and persistence
boundaries. Workspace scaffolding and the CLI are outer adapters.

`scripts/check_architecture.py` enforces this direction and reports the concrete
remediation when a forbidden import appears.

## Persistence transaction

Every mutation loads and semantically validates the current and all retained
generations, applies the complete change in memory, validates the proposed
publication, writes a new immutable generation, durably updates the journal, and
atomically switches `CURRENT`.
Operation IDs make retries safe. Expected-generation checks prevent stale writers.
Packages created before opaque evidence inventories are bootstrapped only when
their external evidence directory is empty; non-empty ambiguous state fails closed.

Effect-free daily reads (`context status`, workflow, analyses, discovery,
explanations, and rule validation/preview) load and fully validate the current
generation without semantically materializing retained generations. The storage
adapter still validates the current evidence inventory. If staging or temporary
publication artifacts are present, the current-only path first falls back to full
recovery. `context status` projects only current identity, initialization
identities, schema versions, and module pins; it never publishes a generation.

`context verify` explicitly loads and semantically validates the current and all
retained generations plus their raw evidence. Mutations use that same full-history
boundary, so corruption in a retained generation cannot be carried into a new
publication. Historical corruption may therefore leave an effect-free current
read available while verification and mutation fail closed.

Rule-package validation and preview load the current generation but never publish.
Activation is an ordinary EngineCore mutation: a human authorization is bound to
the package checksum and expected generation, the complete normalized package is
checksummed into the new generation, and the manifest switches its module's whole
package pin atomically. Later mutations carry active rule artifacts forward.

Source imports derive one stable local account entity from the adapter and literal
source-account identity. The literal posting remains preserved in evidence; the
entity is the subject for separately confirmed allocation and coverage assertions.
When exactly one unlinked manual account can collide with one new source account,
the import preview exposes a `merge_external_account_identity` effect. Only the
checksum-bound human authorization confirms that identity and imports the source
records atomically. A previously confirmed external identity always wins on later
imports; the engine never merges multiple candidates by guesswork.

Bulk source classification is also owned by `EngineCore`. It resolves exact
selectors against open adapter proposals, validates canonical targets through the
module catalog, computes the authorization preview, and publishes all confirmed
assertions plus proposal decisions as one transaction. The CLI only validates and
translates the `source classify-batch` request.

`context_inventory.py` owns the effect-free `workflow.next` decision module. It
reads only a validated immutable generation, composes domain inventory projections
with active analyses, and returns one closed action type. It never publishes.
`EngineCore` alone translates `workflow.respond` into proposals and confirms or
rejects a complete batch atomically. The CLI and managed agent instructions only
localize and render the engine's already-decided result.

## Context lifecycle

`context migrate` supports only named target versions known by this engine. It
builds and validates a complete successor generation before publication; unknown
package or context-schema versions return a rejected mutation without changing
`CURRENT`. `context restore` validates a retained generation and copies its state
into a new generation whose `based_on` remains the generation that was current.

Packages using `topo.context/0.1` remain readable. A proactive workflow on such a
package returns only an executable migration-preview action. The authorized
migration publishes `topo.context/0.2`, preserves identifiers and journal history,
and does not infer inventory coverage.

`context compact` publishes a value-free retention decision before pruning. Its
bounded `retain_latest` value counts the new compact generation, while explicit
restore generations are protected in addition. Missing historical parents remain
explained by the compact journal entry and are never silently accepted.

`context privacy-scrub` is the sole immutability exception. EngineCore removes the
selected evidence from every retained generation and raw evidence record, removes
dependent proposals, marks surviving dependent assertions `unverifiable`, scrubs
the identifier from mutation fields, rewrites checksums and inventories, clears
derived explanations, and validates the resulting package again.
