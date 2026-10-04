"""Prepare and validate Topo mutation requests without executing them."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import cast

from jsonschema import ValidationError

from topo.contracts import (
    CONTRACT_VERSION,
    MUTATING_COMMANDS,
    input_schema,
    validate_request,
)
from topo.engine import EngineCore
from topo.identifiers import uuid7
from topo.models import Journal, JsonObject
from topo.storage import FileSystemStorageAdapter

SHELL_FIELDS = frozenset(
    {
        "contract_version",
        "operation_id",
        "context_id",
        "expected_generation",
        "actor",
        "reason",
    }
)
BATCH_COMMANDS = frozenset(
    {"source.classify-batch", "proposal.confirm-batch", "proposal.reject-batch"}
)


def _read_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected a JSON object")
    return cast(JsonObject, value)


def _write_object(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _identity(package: Path) -> tuple[str, str]:
    generation, context_id = EngineCore(
        FileSystemStorageAdapter(package)
    ).current_identity()
    return context_id, generation


def _validate(command: str, request: JsonObject) -> None:
    if command not in MUTATING_COMMANDS:
        raise ValueError(f"unsupported mutation command: {command}")
    validate_request(command, request)


def build(
    package: Path,
    command: str,
    payload: JsonObject,
    *,
    actor_type: str,
    actor_id: str,
    reason: str,
) -> JsonObject:
    if command not in MUTATING_COMMANDS:
        raise ValueError(f"unsupported mutation command: {command}")
    reserved = SHELL_FIELDS | ({"batch_id"} if command in BATCH_COMMANDS else set())
    supplied = reserved.intersection(payload)
    if supplied:
        raise ValueError(
            f"payload overrides generated fields: {', '.join(sorted(supplied))}"
        )
    if payload.get("authorization") is not None:
        raise ValueError("build requires authorization: null; preview first")
    context_id, generation = _identity(package)
    request: JsonObject = {
        "contract_version": CONTRACT_VERSION,
        "operation_id": uuid7(),
        "context_id": context_id,
        "expected_generation": generation,
        "actor": {"actor_type": actor_type, "actor_id": actor_id},
        "reason": reason,
        **({"batch_id": uuid7()} if command in BATCH_COMMANDS else {}),
        **payload,
    }
    properties = cast(dict[str, object], input_schema(command)["properties"])
    if "authorization" in properties and "authorization" not in request:
        request["authorization"] = None
    _validate(command, request)
    return request


def refresh(package: Path, command: str, request: JsonObject) -> JsonObject:
    _validate(command, request)
    if request.get("authorization") is not None:
        raise ValueError("cannot refresh an authorized request; preview again first")
    context_id, generation = _identity(package)
    if request["context_id"] != context_id:
        raise ValueError("request context_id does not match the package")
    journal = Journal.model_validate_json(
        (package / "history" / "journal.json").read_bytes()
    )
    if any(entry.operation_id == request["operation_id"] for entry in journal.entries):
        raise ValueError("cannot refresh an already executed operation_id")
    refreshed = {**request, "expected_generation": generation}
    _validate(command, refreshed)
    return refreshed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    build_parser = subcommands.add_parser(
        "build", help="build a complete request from a payload"
    )
    build_parser.add_argument("--package", type=Path, required=True)
    build_parser.add_argument("--command", required=True)
    build_parser.add_argument("--payload", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--actor-type", default="agent")
    build_parser.add_argument("--actor-id", required=True)
    build_parser.add_argument("--reason", required=True)
    refresh_parser = subcommands.add_parser(
        "refresh", help="update a pending request's generation"
    )
    refresh_parser.add_argument("--package", type=Path, required=True)
    refresh_parser.add_argument("--command", required=True)
    refresh_parser.add_argument("--request", type=Path, required=True)
    refresh_parser.add_argument("--output", type=Path)
    validate_parser = subcommands.add_parser(
        "validate", help="check request shape without mutation"
    )
    validate_parser.add_argument("--command", required=True)
    validate_parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            request = build(
                args.package,
                args.command,
                _read_object(args.payload),
                actor_type=args.actor_type,
                actor_id=args.actor_id,
                reason=args.reason,
            )
            _write_object(args.output, request)
        elif args.action == "refresh":
            request = refresh(args.package, args.command, _read_object(args.request))
            _write_object(args.output or args.request, request)
        else:
            _validate(args.command, _read_object(args.request))
    except (OSError, TypeError, ValueError, ValidationError) as error:
        print(f"topo_helpers: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
