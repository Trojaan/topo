---
name: pr
description: Verify and ship a Topo change; use for "open a PR", "ship this", "raise a PR", or "/pr".
---

# Verify and ship Topo

1. Require a non-default branch and committed changes.
2. Run `scripts/dev-local.sh up` once.
3. Ask a fresh read-only verifier agent to exercise the changed CLI behavior with
   synthetic data in a temporary directory. It must report expected behavior,
   observed behavior, and transcript/evidence paths; it must not edit code.
4. If broken, fix and repeat with a fresh verifier, up to three rounds.
5. Run `scripts/verify.sh` yourself. Never weaken an assertion to get green.
6. Open the PR only when both the independent verdict and codified gate are green.
   Lead the description with the observed CLI proof and reproduction command.

Topo has no login or running service. There is therefore no session helper; if an
authenticated adapter is introduced, add a reusable sandbox-only helper before
shipping it.
