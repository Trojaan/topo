from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from jsonschema import ValidationError
from pydantic import JsonValue
from pydantic import ValidationError as PydanticValidationError

from topo.contracts import (
    COMMANDS,
    CONTRACT_VERSION,
    describe_result,
    schema_result,
    validate_request,
    validate_response,
)
from topo.engine import EngineCore
from topo.errors import (
    ContextAlreadyExistsError,
    PackageIntegrityError,
    ProposalDecisionError,
    StaleGenerationError,
)
from topo.identifiers import uuid7
from topo.models import (
    ContextInitRequest,
    Diagnostic,
    JsonObject,
    MutationOutcome,
    Outcome,
    ProposalConfirmRequest,
    ProposalCorrectRequest,
    ProposalRejectRequest,
    ProposalSubmitRequest,
    Ref,
    ResponseEnvelope,
    Trace,
    model_to_json_object,
)
from topo.storage import FileSystemStorageAdapter


class IncompatibleContractVersion(Exception):
    def __init__(self, requested: JsonValue) -> None:
        self.requested = requested
        super().__init__(str(requested))


def _request_from_source(request_path: Path | None) -> JsonObject:
    if request_path is not None:
        payload = request_path.read_text(encoding="utf-8")
    elif sys.stdin.isatty():
        return {"contract_version": CONTRACT_VERSION}
    else:
        payload = sys.stdin.read()
    if not payload.strip():
        return {"contract_version": CONTRACT_VERSION}
    value: JsonValue = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("request must be a JSON object")
    return value


def _normalize_request(
    command: str, args: argparse.Namespace, request: JsonObject
) -> JsonObject:
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


def _write_json(value: JsonObject) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _require_supported_contract(request: JsonObject) -> None:
    requested = request.get("contract_version")
    if requested != CONTRACT_VERSION:
        raise IncompatibleContractVersion(requested)


def _error_envelope(
    command: str,
    request: JsonObject,
    *,
    code: str,
    message_key: str,
    path: str,
    params: JsonObject,
    retryable: bool,
) -> JsonObject:
    response = ResponseEnvelope(
        contract_version=CONTRACT_VERSION,
        command=command,
        operation_id=None,
        context_id=None,
        generation_before=None,
        generation_after=None,
        outcome="rejected",
        result={},
        diagnostics=(
            Diagnostic(
                code=code,
                message_key=message_key,
                severity="error",
                path=path,
                params=params,
                retryable=retryable,
            ),
        ),
        next_actions=(),
        trace=Trace(normalized_request=request),
    )
    value = model_to_json_object(response)
    validate_response(command, value)
    return value


def _success_envelope(
    command: str,
    request: JsonObject,
    result: JsonObject,
    *,
    context_id: str | None = None,
    generation_before: str | None = None,
    generation_after: str | None = None,
    operation_id: str | None = None,
    refs: tuple[Ref, ...] = (),
    outcome: Outcome = "succeeded",
) -> JsonObject:
    response = ResponseEnvelope(
        contract_version=CONTRACT_VERSION,
        command=command,
        operation_id=operation_id,
        context_id=context_id,
        generation_before=generation_before,
        generation_after=generation_after,
        outcome=outcome,
        result=result,
        diagnostics=(),
        next_actions=(),
        trace=Trace(normalized_request=request, refs=refs),
    )
    value = model_to_json_object(response)
    validate_response(command, value)
    return value


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

    proposal = commands.add_parser("proposal")
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    for name in ("submit", "confirm", "correct", "reject"):
        proposal_command = proposal_commands.add_parser(name)
        proposal_command.add_argument("--package", type=Path, required=True)
    return parser


def _mutation_envelope(
    command: str, request: JsonObject, outcome: MutationOutcome
) -> JsonObject:
    diagnostics: tuple[Diagnostic, ...] = ()
    next_actions: tuple[JsonObject, ...] = ()
    if outcome.outcome == "conflict":
        diagnostics = (
            Diagnostic(
                code="STALE_GENERATION",
                message_key="diagnostic.stale_generation",
                severity="error",
                path="/expected_generation",
                params={
                    "expected": outcome.result["expected_generation"],
                    "actual": outcome.result["actual_generation"],
                },
                retryable=True,
                related_refs=(
                    Ref(ref_type="generation", id=outcome.generation_before),
                ),
            ),
        )
    elif outcome.outcome == "requires_authorization":
        next_actions = (
            {
                "action_id": uuid7(),
                "action_type": "authorize_preview",
                "action_contract_version": "topo.workflow-action/0.1",
                "priority": "blocking",
                "reason_code": "PROPOSAL_DECISION_REQUIRES_AUTHORIZATION",
                "affected_component": None,
                "related_refs": [],
                "command": command,
                "request_template": {
                    "proposal_ref": request.get("proposal_ref"),
                    "authorization": {"preview_ref": outcome.result["preview_ref"]},
                },
                "input_schema_ref": f"topo://schema/{command.replace('.', '-')}-request/0.1",
                "requires_user_input": False,
                "requires_authorization": True,
            },
        )
    response = ResponseEnvelope(
        contract_version=CONTRACT_VERSION,
        command=command,
        operation_id=str(request["operation_id"]),
        context_id=outcome.context_id,
        generation_before=outcome.generation_before,
        generation_after=outcome.generation_after,
        outcome=outcome.outcome,
        result=outcome.result,
        diagnostics=diagnostics,
        next_actions=next_actions,
        trace=Trace(normalized_request=request),
    )
    value = model_to_json_object(response)
    validate_response(command, value)
    return value


def _proposal_rejection_envelope(
    command: str,
    request: JsonObject,
    error: ProposalDecisionError,
) -> JsonObject:
    generation = str(request["expected_generation"])
    response = ResponseEnvelope(
        contract_version=CONTRACT_VERSION,
        command=command,
        operation_id=str(request["operation_id"]),
        context_id=str(request["context_id"]),
        generation_before=generation,
        generation_after=generation,
        outcome="rejected",
        result={},
        diagnostics=(
            Diagnostic(
                code=error.code,
                message_key=f"diagnostic.{error.code.lower()}",
                severity="error",
                path=error.path,
                params={"reason": error.reason},
                retryable=True,
            ),
        ),
        trace=Trace(normalized_request=request),
    )
    value = model_to_json_object(response)
    validate_response(command, value)
    return value


def _validation_pointer(error: ValidationError) -> str:
    return "".join(f"/{part}" for part in error.absolute_path)


def _write_error(
    command: str,
    request: JsonObject,
    *,
    code: str,
    message_key: str,
    path: str,
    reason: str,
    json_output: bool,
) -> int:
    if json_output:
        _write_json(
            _error_envelope(
                command,
                request,
                code=code,
                message_key=message_key,
                path=path,
                params={"reason": reason},
                retryable=False,
            )
        )
    else:
        print(reason, file=sys.stderr)
    return 2


def _missing_request_path(parser: argparse.ArgumentParser) -> NoReturn:
    parser.error("--request requires a file path")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    json_output = "--json" in arguments
    arguments = [argument for argument in arguments if argument != "--json"]
    request_path: Path | None = None
    if "--request" in arguments:
        request_index = arguments.index("--request")
        if request_index + 1 >= len(arguments):
            _missing_request_path(_parser())
        request_path = Path(arguments[request_index + 1])
        del arguments[request_index : request_index + 2]
    args = _parser().parse_args(arguments)
    if args.group == "contract":
        command = f"contract.{args.contract_command}"
    elif args.group == "context":
        command = f"context.{args.context_command}"
    else:
        command = f"proposal.{args.proposal_command}"
    request: JsonObject = {}
    try:
        request = _normalize_request(command, args, _request_from_source(request_path))
        _require_supported_contract(request)
        validate_request(command, request)

        if command == "contract.describe":
            _write_json(_success_envelope(command, request, describe_result()))
            return 0
        if command == "contract.schema":
            _write_json(
                _success_envelope(command, request, schema_result(args.command))
            )
            return 0
        if command == "context.init":
            init_request = ContextInitRequest.model_validate(request, strict=True)
            initialization = EngineCore(
                FileSystemStorageAdapter(Path(init_request.package))
            ).initialize(init_request)
            result = initialization.result
            _write_json(
                _success_envelope(
                    command,
                    request,
                    model_to_json_object(result),
                    context_id=result.context_id,
                    generation_before=(
                        result.generation_id if initialization.replayed else None
                    ),
                    generation_after=result.generation_id,
                    operation_id=init_request.operation_id,
                    refs=(
                        Ref(ref_type="generation", id=result.generation_id),
                        Ref(ref_type="entity", id=result.person_id),
                        Ref(ref_type="entity", id=result.household_id),
                    ),
                    outcome="no_change" if initialization.replayed else "succeeded",
                )
            )
            return 0
        if command.startswith("proposal."):
            engine = EngineCore(FileSystemStorageAdapter(args.package))
            if command == "proposal.submit":
                outcome = engine.submit_proposal(
                    ProposalSubmitRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            elif command == "proposal.confirm":
                outcome = engine.confirm_proposal(
                    ProposalConfirmRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            elif command == "proposal.correct":
                outcome = engine.correct_proposal(
                    ProposalCorrectRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            else:
                outcome = engine.reject_proposal(
                    ProposalRejectRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            _write_json(_mutation_envelope(command, request, outcome))
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
    except (ContextAlreadyExistsError, FileExistsError):
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
    except PackageIntegrityError as error:
        return _write_error(
            command,
            request,
            code="PACKAGE_INTEGRITY_FAILED",
            message_key="diagnostic.package_integrity_failed",
            path="/package",
            reason=error.reason,
            json_output=json_output,
        )
    except ProposalDecisionError as error:
        _write_json(_proposal_rejection_envelope(command, request, error))
        return 0
    except StaleGenerationError as error:
        stale = MutationOutcome(
            context_id=str(request["context_id"]),
            generation_before=error.actual_generation,
            generation_after=error.actual_generation,
            outcome="conflict",
            result={
                "expected_generation": request["expected_generation"],
                "actual_generation": error.actual_generation,
            },
        )
        _write_json(_mutation_envelope(command, request, stale))
        return 0
    except ValidationError as error:
        return _write_error(
            command,
            request,
            code="INVALID_REQUEST",
            message_key="diagnostic.invalid_request",
            path=_validation_pointer(error),
            reason=error.message,
            json_output=json_output,
        )
    except PydanticValidationError as error:
        return _write_error(
            command,
            request,
            code="INVALID_REQUEST",
            message_key="diagnostic.invalid_request",
            path="",
            reason=str(error),
            json_output=json_output,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        return _write_error(
            command,
            request,
            code="COMMAND_NOT_EXECUTABLE",
            message_key="diagnostic.command_not_executable",
            path="",
            reason=str(error),
            json_output=json_output,
        )
    return 2
