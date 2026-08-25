from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Sequence

from jsonschema import ValidationError

from topo.contracts import (
    COMMANDS,
    CONTRACT_VERSION,
    describe_result,
    schema_result,
    validate_request,
    validate_response,
)
from topo.identifiers import uuid7
from topo.storage import initialize_package


class IncompatibleContractVersion(Exception):
    def __init__(self, requested: Any) -> None:
        self.requested = requested
        super().__init__(str(requested))


def _request_from_source(request_path: Optional[Path]) -> Dict[str, Any]:
    if request_path is not None:
        payload = request_path.read_text(encoding="utf-8")
    elif sys.stdin.isatty():
        return {"contract_version": CONTRACT_VERSION}
    else:
        payload = sys.stdin.read()
    if not payload.strip():
        return {"contract_version": CONTRACT_VERSION}
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def _normalize_request(
    command: str, args: argparse.Namespace, request: Dict[str, Any]
) -> Dict[str, Any]:
    normalized = dict(request)
    if command == "context.init":
        normalized["package"] = str(args.package)
        normalized.setdefault("operation_id", uuid7())
        normalized.setdefault("expected_generation", None)
        normalized.setdefault(
            "actor", {"actor_type": "human", "actor_id": "local-user"}
        )
        normalized.setdefault("reason", "Initialize local Topo context")
    return normalized


def _write_json(value: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _require_supported_contract(request: Dict[str, Any]) -> None:
    requested = request.get("contract_version")
    if requested != CONTRACT_VERSION:
        raise IncompatibleContractVersion(requested)


def _error_envelope(
    command: str,
    request: Dict[str, Any],
    *,
    code: str,
    message_key: str,
    path: str,
    params: Dict[str, Any],
    retryable: bool,
) -> Dict[str, Any]:
    response = {
        "contract_version": CONTRACT_VERSION,
        "command": command,
        "operation_id": None,
        "context_id": None,
        "generation_before": None,
        "generation_after": None,
        "outcome": "rejected",
        "result": {},
        "diagnostics": [
            {
                "code": code,
                "message_key": message_key,
                "severity": "error",
                "path": path,
                "params": params,
                "retryable": retryable,
                "effect": "none",
                "related_refs": [],
            }
        ],
        "next_actions": [],
        "trace": {"normalized_request": request, "refs": []},
    }
    validate_response(command, response)
    return response


def _success_envelope(
    command: str,
    request: Dict[str, Any],
    result: Dict[str, Any],
    *,
    context_id: Optional[str] = None,
    generation_before: Optional[str] = None,
    generation_after: Optional[str] = None,
    operation_id: Optional[str] = None,
    refs: Optional[list[Dict[str, str]]] = None,
    outcome: str = "succeeded",
) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "command": command,
        "operation_id": operation_id,
        "context_id": context_id,
        "generation_before": generation_before,
        "generation_after": generation_after,
        "outcome": outcome,
        "result": result,
        "diagnostics": [],
        "next_actions": [],
        "trace": {
            "normalized_request": request,
            "refs": refs or [],
        },
    }
    validate_response(command, response)
    return response


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="topo")
    parser.add_argument("--json", action="store_true", dest="json_output")
    commands = parser.add_subparsers(dest="group", required=True)

    contract = commands.add_parser("contract")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    contract_commands.add_parser("describe")
    schema = contract_commands.add_parser("schema")
    schema.add_argument("command", choices=COMMANDS)

    context = commands.add_parser("context")
    context_commands = context.add_subparsers(dest="context_command", required=True)
    initialize = context_commands.add_parser("init")
    initialize.add_argument("--package", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    json_output = "--json" in arguments
    arguments = [argument for argument in arguments if argument != "--json"]
    request_path: Optional[Path] = None
    if "--request" in arguments:
        request_index = arguments.index("--request")
        try:
            request_path = Path(arguments[request_index + 1])
        except IndexError:
            _parser().error("--request requires a file path")
        del arguments[request_index : request_index + 2]
    args = _parser().parse_args(arguments)
    args.json_output = json_output
    command = (
        f"contract.{args.contract_command}"
        if args.group == "contract"
        else f"context.{args.context_command}"
    )
    request: Dict[str, Any] = {}
    try:
        request = _normalize_request(command, args, _request_from_source(request_path))
        _require_supported_contract(request)
        if args.group == "contract" and args.contract_command == "describe":
            validate_request(command, request)
            _write_json(_success_envelope(command, request, describe_result()))
            return 0
        if args.group == "contract" and args.contract_command == "schema":
            validate_request(command, request)
            _write_json(_success_envelope(command, request, schema_result(args.command)))
            return 0
        if args.group == "context" and args.context_command == "init":
            validate_request(command, request)
            initialization = initialize_package(
                args.package,
                operation_id=request["operation_id"],
                actor=request["actor"],
                reason=request["reason"],
            )
            result = initialization.result
            response = _success_envelope(
                command,
                request,
                result,
                context_id=result["context_id"],
                generation_before=(
                    result["generation_id"] if initialization.replayed else None
                ),
                generation_after=result["generation_id"],
                operation_id=request["operation_id"],
                refs=[
                    {"ref_type": "generation", "id": result["generation_id"]},
                    {"ref_type": "entity", "id": result["person_id"]},
                    {"ref_type": "entity", "id": result["household_id"]},
                ],
                outcome="no_change" if initialization.replayed else "succeeded",
            )
            _write_json(response)
            return 0
    except IncompatibleContractVersion as error:
        _write_json(
            _error_envelope(
                command,
                request,
                code="INCOMPATIBLE_CONTRACT_VERSION",
                message_key="diagnostic.incompatible_contract_version",
                path="/contract_version",
                params={
                    "requested": error.requested,
                    "supported": [CONTRACT_VERSION],
                },
                retryable=False,
            )
        )
        return 2
    except FileExistsError:
        _write_json(
            _error_envelope(
                command,
                request,
                code="CONTEXT_ALREADY_EXISTS",
                message_key="diagnostic.context_already_exists",
                path="/package",
                params={"package": str(args.package)},
                retryable=False,
            )
        )
        return 2
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as error:
        if args.json_output:
            _write_json(
                _error_envelope(
                    command,
                    request,
                    code="COMMAND_NOT_EXECUTABLE",
                    message_key="diagnostic.command_not_executable",
                    path="",
                    params={"reason": str(error)},
                    retryable=False,
                )
            )
        else:
            print(str(error), file=sys.stderr)
        return 2
    return 2
