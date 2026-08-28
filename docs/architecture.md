# Architecture

Topo 0.1 is one Python package and one command-line process. It has no server,
database, queue, container, port, or required network service.

```text
user/agent -> CLI -> contracts -> EngineCore -> storage adapter -> .topo package
                         |             |
                         |             +-> module catalog / domain constraints
                         +-> versioned JSON request and response envelopes
```

## Responsibilities

- `cli.py` parses commands, reads request JSON, maps errors, and writes a stable
  JSON envelope. It contains no domain decisions.
- `contracts.py` owns discoverable input/output schemas and request validation.
- `engine.py` owns mutations, authorization, idempotency, generations, history,
  and replay. This is the semantic transaction boundary.
- `models.py` contains typed canonical records; `canonical_validation.py` checks a
  complete stored snapshot.
- `modules.py` defines the extension contract. `builtin_modules.py` supplies the
  versioned universal and Dutch capabilities.
- `storage.py` is a meaning-free adapter: locking, staging, durable writes,
  atomic publication, and crash recovery.

## Dependency direction

Foundation modules (`identifiers`, `models`, `errors`) must not import orchestration
or persistence. Contracts and semantic modules may depend on the foundation but
not on the CLI, engine, or storage. The engine composes semantic and persistence
boundaries. The CLI is the outermost adapter.

`scripts/check_architecture.py` enforces this direction and reports the concrete
remediation when a forbidden import appears.

## Persistence transaction

Every mutation loads and validates the current generation, applies the complete
change in memory, validates the proposed publication, writes a new immutable
generation, durably updates the journal, and atomically switches `CURRENT`.
Operation IDs make retries safe. Expected-generation checks prevent stale writers.
