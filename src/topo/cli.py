from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn, cast

from jsonschema import ValidationError
from pydantic import JsonValue, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from topo import __version__
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
    ExplanationReferenceError,
    PackageIntegrityError,
    ProposalDecisionError,
    SemanticModulesUnavailableError,
    StaleGenerationError,
)
from topo.identifiers import uuid7
from topo.models import (
    AnalyzeRunRequest,
    ContextInitRequest,
    ContextMigrateRequest,
    ContextPrivacyScrubRequest,
    ContextRestoreRequest,
    ContextRetentionRequest,
    ContextStatusRequest,
    Diagnostic,
    DiscoveryRequest,
    JsonObject,
    MutationOutcome,
    Outcome,
    ProposalConfirmRequest,
    ProposalCorrectRequest,
    ProposalRejectRequest,
    ProposalSubmitRequest,
    Ref,
    ResponseEnvelope,
    RuleActivateRequest,
    RulePackageRequest,
    SourceImportRequest,
    Trace,
    WorkflowNextRequest,
    WorkspaceInitRequest,
    model_to_json_object,
)
from topo.rules import RulePackageError
from topo.storage import FileSystemStorageAdapter
from topo.workspace import initialize_workspace


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
    if command == "workspace.init":
        normalized["directory"] = str(args.directory)
    if command == "context.status":
        normalized["package"] = str(args.package)
    if command == "source.import" and args.records_csv is not None:
        if "records" in normalized:
            raise ValueError("provide records in JSON or --records-csv, not both")
        normalized["records"] = _records_from_csv(args.records_csv)
    if command.startswith("rule.") and args.rules is not None:
        if "rule_package_yaml" in normalized:
            raise ValueError("provide rule_package_yaml in JSON or --rules, not both")
        normalized["rule_package_yaml"] = args.rules.read_text(encoding="utf-8")
    if command == "explain" and args.ref is not None:
        if "ref" in normalized and normalized["ref"] != args.ref:
            raise ValueError("provide the same ref in JSON and --ref, or only one")
        normalized["ref"] = args.ref
    return normalized


def _records_from_csv(path: Path) -> list[JsonValue]:
    required = {
        "source_id",
        "record_id",
        "booking_date",
        "amount",
        "currency",
        "description",
    }
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not required <= set(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or ()))
            raise ValueError(f"normalized CSV is missing columns: {', '.join(missing)}")
        records: list[JsonValue] = []
        for row in reader:
            source_classification: JsonObject | None = None
            classification_values = (
                row.get("category", ""),
                row.get("rule_version", ""),
                row.get("explanation", ""),
            )
            if any(classification_values):
                if not all(classification_values):
                    raise ValueError(
                        "CSV classification requires category, rule_version, and explanation"
                    )
                source_classification = {
                    "category": classification_values[0],
                    "rule_version": classification_values[1],
                    "explanation": classification_values[2],
                }
            record: JsonObject = {
                "source_id": row["source_id"],
                "record_id": row["record_id"],
                "booking_date": row["booking_date"],
                "money": {"amount": row["amount"], "currency": row["currency"]},
                "description": row["description"],
            }
            if source_classification is not None:
                record["source_classification"] = source_classification
            records.append(record)
    return records


def _write_json(value: JsonObject) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _write_explanation_text(result: JsonObject, locale: str) -> None:
    labels = (
        {
            "reference": "Referentie",
            "meaning": "Betekenis",
            "generation": "Generatie",
            "requirements": "Vereisten",
            "assumptions": "Aannames",
            "steps": "Rekenstappen",
        }
        if locale == "nl-NL"
        else {
            "reference": "Reference",
            "meaning": "Meaning",
            "generation": "Generation",
            "requirements": "Requirements",
            "assumptions": "Assumptions",
            "steps": "Calculation steps",
        }
    )
    lines = (
        f"{labels['reference']}: {result['ref']}",
        f"{labels['meaning']}: {result['meaning']}",
        f"{labels['generation']}: {result['generation_id']}",
        f"{labels['requirements']}: {len(cast(list[JsonValue], result['requirements']))}",
        f"{labels['assumptions']}: {len(cast(list[JsonValue], result['assumptions']))}",
        f"{labels['steps']}: {len(cast(list[JsonValue], result['calculation_steps']))}",
    )
    sys.stdout.write("\n".join(lines) + "\n")


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
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    commands = parser.add_subparsers(dest="group", required=True)

    workspace_init = commands.add_parser("init")
    workspace_init.add_argument("directory", nargs="?", type=Path, default=Path("."))

    contract = commands.add_parser("contract")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    contract_commands.add_parser("describe")
    schema = contract_commands.add_parser("schema")
    schema.add_argument("command", choices=COMMANDS)

    context = commands.add_parser("context")
    context_commands = context.add_subparsers(dest="context_command", required=True)
    initialize = context_commands.add_parser("init")
    initialize.add_argument("--package", type=Path, required=True)
    status = context_commands.add_parser("status")
    status.add_argument("--package", type=Path, required=True)
    for name in ("migrate", "restore", "compact", "privacy-scrub"):
        lifecycle = context_commands.add_parser(name)
        lifecycle.add_argument("--package", type=Path, required=True)

    proposal = commands.add_parser("proposal")
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    for name in ("submit", "confirm", "correct", "reject"):
        proposal_command = proposal_commands.add_parser(name)
        proposal_command.add_argument("--package", type=Path, required=True)

    source = commands.add_parser("source")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    source_import = source_commands.add_parser("import")
    source_import.add_argument("--package", type=Path, required=True)
    source_import.add_argument("--records-csv", type=Path)

    discover = commands.add_parser("discover")
    discover_commands = discover.add_subparsers(dest="discover_command", required=True)
    discover_run = discover_commands.add_parser("run")
    discover_run.add_argument("--package", type=Path, required=True)

    analyze = commands.add_parser("analyze")
    analyze_commands = analyze.add_subparsers(dest="analyze_command", required=True)
    analyze_run = analyze_commands.add_parser("run")
    analyze_run.add_argument("--package", type=Path, required=True)

    workflow = commands.add_parser("workflow")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_next = workflow_commands.add_parser("next")
    workflow_next.add_argument("--package", type=Path, required=True)
    workflow_next.add_argument(
        "--request",
        type=Path,
        metavar="PATH",
        help="read the workflow.next JSON request from PATH (defaults to stdin)",
    )
    rule = commands.add_parser("rule")
    rule_commands = rule.add_subparsers(dest="rule_command", required=True)
    for name in ("validate", "preview", "activate"):
        rule_command = rule_commands.add_parser(name)
        rule_command.add_argument("--package", type=Path, required=True)
        rule_command.add_argument("--rules", type=Path)
    explain = commands.add_parser("explain")
    explain.add_argument("--package", type=Path, required=True)
    explain.add_argument("--ref")
    explain.add_argument("--locale", choices=("nl-NL", "en"), default="nl-NL")
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
        request_template: JsonObject = {
            "authorization": {"preview_ref": outcome.result["preview_ref"]}
        }
        reason_code = "SOURCE_IMPORT_REQUIRES_AUTHORIZATION"
        if command.startswith("proposal."):
            request_template["proposal_ref"] = request.get("proposal_ref")
            reason_code = "PROPOSAL_DECISION_REQUIRES_AUTHORIZATION"
        if command == "rule.activate":
            reason_code = "RULE_ACTIVATION_REQUIRES_AUTHORIZATION"
        next_actions = (
            {
                "action_id": uuid7(),
                "action_type": "authorize_preview",
                "action_contract_version": "topo.workflow-action/0.1",
                "priority": "blocking",
                "reason_code": reason_code,
                "affected_component": None,
                "related_refs": [],
                "command": command,
                "request_template": request_template,
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


def _write_workspace_text(result: JsonObject, outcome: Outcome) -> None:
    action = "Initialized" if outcome == "succeeded" else "Workspace already current at"
    print(f"{action}: {result['workspace']}")
    print(f"Context: {result['package']}")
    print(f"Context ID: {result['context_id']}")
    print(f"Generation: {result['generation_id']}")
    print()
    print("Next steps:")
    print(f"  cd {result['workspace']}")
    print("  topo context status --package ./context.topo --json")


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
    if args.group == "init":
        command = "workspace.init"
    elif args.group == "contract":
        command = f"contract.{args.contract_command}"
    elif args.group == "context":
        command = f"context.{args.context_command.replace('-', '_')}"
    elif args.group == "source":
        command = f"source.{args.source_command}"
    elif args.group == "discover":
        command = f"discover.{args.discover_command}"
    elif args.group == "analyze":
        command = f"analyze.{args.analyze_command}"
    elif args.group == "workflow":
        command = f"workflow.{args.workflow_command}"
    elif args.group == "rule":
        command = f"rule.{args.rule_command}"
    elif args.group == "explain":
        command = "explain"
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
        if command == "workspace.init":
            workspace_request = WorkspaceInitRequest.model_validate(
                request, strict=True
            )
            initialized_workspace = initialize_workspace(workspace_request)
            workspace_result_json = model_to_json_object(initialized_workspace.result)
            workspace_outcome: Outcome = (
                "succeeded" if initialized_workspace.changed else "no_change"
            )
            envelope = _success_envelope(
                command,
                request,
                workspace_result_json,
                context_id=initialized_workspace.result.context_id,
                generation_before=initialized_workspace.generation_before,
                generation_after=initialized_workspace.result.generation_id,
                operation_id=initialized_workspace.operation_id,
                outcome=workspace_outcome,
            )
            if json_output:
                _write_json(envelope)
            else:
                _write_workspace_text(workspace_result_json, workspace_outcome)
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
        if command == "context.status":
            status_request = ContextStatusRequest.model_validate(request, strict=True)
            status_result = EngineCore(
                FileSystemStorageAdapter(Path(status_request.package))
            ).context_status()
            status_result_json = model_to_json_object(status_result)
            _write_json(
                _success_envelope(
                    command,
                    request,
                    status_result_json,
                    context_id=status_result.context_id,
                    generation_before=status_result.generation_id,
                    generation_after=status_result.generation_id,
                )
            )
            return 0
        if command.startswith("context."):
            engine = EngineCore(FileSystemStorageAdapter(args.package))
            if command == "context.migrate":
                outcome = engine.migrate_context(
                    ContextMigrateRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            elif command == "context.restore":
                outcome = engine.restore_context(
                    ContextRestoreRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            elif command == "context.compact":
                outcome = engine.apply_retention(
                    ContextRetentionRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            else:
                outcome = engine.scrub_privacy(
                    ContextPrivacyScrubRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            _write_json(_mutation_envelope(command, request, outcome))
            return 0
        if command == "source.import":
            outcome = EngineCore(FileSystemStorageAdapter(args.package)).import_source(
                SourceImportRequest.model_validate_json(
                    json.dumps(request), strict=True
                )
            )
            _write_json(_mutation_envelope(command, request, outcome))
            return 0
        if command == "discover.run":
            discovery_outcome = EngineCore(
                FileSystemStorageAdapter(args.package)
            ).discover_recurring_cashflows(
                DiscoveryRequest.model_validate_json(json.dumps(request), strict=True)
            )
            _write_json(
                _success_envelope(
                    command,
                    request,
                    discovery_outcome.result,
                    context_id=discovery_outcome.context_id,
                    generation_before=discovery_outcome.generation_id,
                    generation_after=discovery_outcome.generation_id,
                )
            )
            return 0
        if command == "analyze.run":
            analyze_request: AnalyzeRunRequest = TypeAdapter(
                AnalyzeRunRequest
            ).validate_json(json.dumps(request), strict=True)
            analysis_result = EngineCore(
                FileSystemStorageAdapter(args.package)
            ).analyze(analyze_request)
            generation = str(analysis_result["used_generation"])
            _write_json(
                _success_envelope(
                    command,
                    request,
                    analysis_result,
                    context_id=analyze_request.context_id,
                    generation_before=generation,
                    generation_after=generation,
                    refs=(Ref(ref_type="generation", id=generation),),
                )
            )
            return 0
        if command == "workflow.next":
            workflow_request = WorkflowNextRequest.model_validate_json(
                json.dumps(request), strict=True
            )
            workflow_result, generation = EngineCore(
                FileSystemStorageAdapter(args.package)
            ).workflow_next(workflow_request)
            _write_json(
                _success_envelope(
                    command,
                    request,
                    workflow_result,
                    context_id=workflow_request.context_id,
                    generation_before=generation,
                    generation_after=generation,
                    refs=(Ref(ref_type="generation", id=generation),),
                )
            )
            return 0
        if command == "explain":
            engine = EngineCore(FileSystemStorageAdapter(args.package))
            explanation = engine.explain(str(request["ref"]))
            generation = str(explanation["generation_id"])
            _, context_id = engine.current_identity()
            envelope = _success_envelope(
                command,
                request,
                explanation,
                context_id=context_id,
                generation_before=generation,
                generation_after=generation,
            )
            if json_output:
                _write_json(envelope)
            else:
                _write_explanation_text(explanation, args.locale)
            return 0
        if command in {"rule.validate", "rule.preview"}:
            rule_request = RulePackageRequest.model_validate_json(
                json.dumps(request), strict=True
            )
            engine = EngineCore(FileSystemStorageAdapter(args.package))
            rule_result = (
                engine.validate_rules(rule_request)
                if command == "rule.validate"
                else engine.preview_rules(rule_request)
            )
            generation = str(rule_result["validated_generation"])
            _write_json(
                _success_envelope(
                    command,
                    request,
                    rule_result,
                    context_id=rule_request.context_id,
                    generation_before=generation,
                    generation_after=generation,
                )
            )
            return 0
        if command == "rule.activate":
            outcome = EngineCore(FileSystemStorageAdapter(args.package)).activate_rules(
                RuleActivateRequest.model_validate_json(
                    json.dumps(request), strict=True
                )
            )
            _write_json(_mutation_envelope(command, request, outcome))
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
        package_argument = getattr(args, "package", None)
        if package_argument is None:
            package_argument = Path(args.directory) / "context.topo"
        _write_json(
            _error_envelope(
                command,
                request,
                code="CONTEXT_ALREADY_EXISTS",
                message_key="diagnostic.context_already_exists",
                path="/package",
                params={"package": str(package_argument)},
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
    except SemanticModulesUnavailableError as error:
        return _write_error(
            command,
            request,
            code="SEMANTIC_MODULE_UNAVAILABLE",
            message_key="diagnostic.semantic_module_unavailable",
            path="/package",
            reason=f"missing pinned modules: {', '.join(error.module_ids)}",
            json_output=json_output,
        )
    except ProposalDecisionError as error:
        _write_json(_proposal_rejection_envelope(command, request, error))
        return 0
    except ExplanationReferenceError as error:
        engine = EngineCore(FileSystemStorageAdapter(args.package))
        generation, context_id = engine.current_identity()
        response = ResponseEnvelope(
            contract_version=CONTRACT_VERSION,
            command=command,
            operation_id=None,
            context_id=context_id,
            generation_before=generation,
            generation_after=generation,
            outcome="rejected",
            result={},
            diagnostics=(
                Diagnostic(
                    code=error.code,
                    message_key=f"diagnostic.{error.code.lower()}",
                    severity="error",
                    path="/ref",
                    params={"ref": error.ref, "reason": error.reason},
                    retryable=False,
                ),
            ),
            trace=Trace(normalized_request=request),
        )
        value = model_to_json_object(response)
        validate_response(command, value)
        _write_json(value)
        return 0
    except RulePackageError as error:
        _write_json(
            _error_envelope(
                command,
                request,
                code=error.code,
                message_key=f"diagnostic.{error.code.lower()}",
                path=error.path,
                params={"reason": error.reason},
                retryable=False,
            )
        )
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
