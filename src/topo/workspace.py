from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from topo.contracts import CONTRACT_VERSION
from topo.engine import EngineCore
from topo.identifiers import uuid7
from topo.models import (
    Actor,
    ContextInitRequest,
    WorkspaceInitRequest,
    WorkspaceInitResult,
)
from topo.storage import FileSystemStorageAdapter

TOPO_START = "<!-- topo:start -->"
TOPO_END = "<!-- topo:end -->"

AGENT_BLOCK = f"""{TOPO_START}
## Topo financial context

This directory contains a local, auditable financial context in `context.topo/`.

- Never edit files inside `context.topo/` directly; use the `topo` CLI.
- Start with `topo context status --package ./context.topo --json` and
  `topo contract describe --json`.
- Inspect an exact command contract with
  `topo contract schema <command> --json` before composing requests.
- Treat agent-interpreted meaning as a proposal. Only explicit human
  authorization may promote it to a confirmed fact.
- Use `topo workflow next --package ./context.topo --json` for deterministic
  next-action guidance once its required request fields are known.
- Keep financial source files in `imports/`; both it and `context.topo/` are
  intentionally excluded from Git.
{TOPO_END}"""

GITIGNORE_BLOCK = f"""{TOPO_START}
# Sensitive local Topo data
context.topo/
imports/
{TOPO_END}"""


@dataclass(frozen=True)
class WorkspaceInitialization:
    result: WorkspaceInitResult
    operation_id: str | None
    generation_before: str | None
    changed: bool


def merge_managed_block(existing: str, block: str) -> str:
    start_count = existing.count(TOPO_START)
    end_count = existing.count(TOPO_END)
    if start_count != end_count or start_count > 1:
        raise ValueError("file contains incomplete or duplicate Topo managed markers")

    newline = "\r\n" if "\r\n" in existing else "\n"
    rendered = block.replace("\n", newline)
    if start_count == 1:
        start = existing.index(TOPO_START)
        end = existing.index(TOPO_END, start) + len(TOPO_END)
        return existing[:start] + rendered + existing[end:]

    if not existing:
        return rendered + newline
    separator = newline if existing.endswith(("\n", "\r")) else newline * 2
    if existing.endswith(newline * 2):
        separator = ""
    return existing + separator + rendered + newline


def _planned_file(path: Path, block: str) -> tuple[str, str]:
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"managed path is not a regular file: {path}")
        with path.open("r", encoding="utf-8", newline="") as stream:
            existing = stream.read()
        updated = merge_managed_block(existing, block)
        return updated, "unchanged" if updated == existing else "updated"
    return merge_managed_block("", block), "created"


def _atomic_write(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def initialize_workspace(request: WorkspaceInitRequest) -> WorkspaceInitialization:
    workspace = Path(request.directory).expanduser().resolve()
    if workspace.exists() and (workspace.is_symlink() or not workspace.is_dir()):
        raise ValueError(f"workspace is not a regular directory: {workspace}")
    workspace.mkdir(parents=True, exist_ok=True)

    planned = {
        workspace / "AGENTS.md": _planned_file(workspace / "AGENTS.md", AGENT_BLOCK),
        workspace / "CLAUDE.md": _planned_file(workspace / "CLAUDE.md", AGENT_BLOCK),
        workspace / ".gitignore": _planned_file(
            workspace / ".gitignore", GITIGNORE_BLOCK
        ),
    }
    imports = workspace / "imports"
    if imports.exists() and (imports.is_symlink() or not imports.is_dir()):
        raise ValueError(f"imports path is not a regular directory: {imports}")

    package = workspace / "context.topo"
    if package.exists():
        if package.is_symlink() or not package.is_dir():
            raise ValueError(f"context package is not a regular directory: {package}")
        required_package_paths = ("CURRENT", "generations", "history")
        if any(not (package / name).exists() for name in required_package_paths):
            raise ValueError(
                f"existing context.topo is not a Topo context package: {package}"
            )
    engine = EngineCore(FileSystemStorageAdapter(package))
    operation_id: str | None = None
    generation_before: str | None = None
    context_created = not package.exists()
    if context_created:
        operation_id = uuid7()
        initialized = engine.initialize(
            ContextInitRequest(
                contract_version=CONTRACT_VERSION,
                package=str(package),
                operation_id=operation_id,
                expected_generation=None,
                actor=Actor(actor_type="human", actor_id="local-user"),
                reason="Initialize local Topo workspace",
            )
        )
        status = engine.context_status()
        if initialized.replayed:
            raise RuntimeError("new workspace initialization unexpectedly replayed")
    else:
        status = engine.context_status()
        generation_before = status.generation_id

    imports_created = not imports.exists()
    imports.mkdir(exist_ok=True)
    for path, (content, state) in planned.items():
        if state != "unchanged":
            _atomic_write(path, content)

    states: dict[str, list[str]] = {"created": [], "updated": [], "unchanged": []}
    for path, (_, state) in planned.items():
        states[state].append(path.name)
    states["created" if imports_created else "unchanged"].append("imports/")
    states["created" if context_created else "unchanged"].append("context.topo/")
    changed = bool(states["created"] or states["updated"])
    result = WorkspaceInitResult(
        workspace=str(workspace),
        package=str(package),
        context_id=status.context_id,
        generation_id=status.generation_id,
        person_id=status.person_id,
        household_id=status.household_id,
        context_created=context_created,
        created_paths=tuple(sorted(states["created"])),
        updated_paths=tuple(sorted(states["updated"])),
        unchanged_paths=tuple(sorted(states["unchanged"])),
    )
    return WorkspaceInitialization(
        result=result,
        operation_id=operation_id,
        generation_before=generation_before,
        changed=changed,
    )
