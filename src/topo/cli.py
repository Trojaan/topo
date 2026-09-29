from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import NoReturn, cast

from jsonschema import ValidationError
from pydantic import JsonValue, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from topo import __version__
from topo.canonical_validation import record_collection_schema
from topo.contracts import (
    CLI_COMMANDS,
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
    ContextVerifyRequest,
    Diagnostic,
    DiscoveryRequest,
    JsonObject,
    MutationOutcome,
    Outcome,
    ProposalBatchConfirmRequest,
    ProposalBatchRejectRequest,
    ProposalConfirmRequest,
    ProposalCorrectRequest,
    ProposalRejectRequest,
    ProposalSubmitRequest,
    Ref,
    ResponseEnvelope,
    RuleActivateRequest,
    RulePackageRequest,
    SourceClassificationBatchRequest,
    SourceImportRequest,
    Trace,
    WorkflowNextRequest,
    WorkflowRespondRequest,
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


class UsageError(Exception):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


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
    if command in {"context.status", "context.verify", "context.summary"}:
        normalized["package"] = str(args.package)
    if command == "context.summary":
        normalized["as_of_date"] = args.as_of
    if command == "contract.record_schema":
        normalized["record_type"] = args.record_type
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


def _apply_shorthand(
    command: str, args: argparse.Namespace, request: JsonObject
) -> JsonObject:
    if command not in {"analyze.run", "discover.run", "workflow.next"}:
        return request
    as_of = getattr(args, "as_of", None)
    analysis = getattr(args, "analysis", None)
    scope = getattr(args, "scope", None)
    if as_of is None and analysis is None and scope is None:
        return request
    if as_of is None:
        raise ValueError("shorthand requires --as-of DATE")
    date.fromisoformat(as_of)
    engine = EngineCore(FileSystemStorageAdapter(args.package))
    context_id, household_id = engine.household_scope_identity(scope)
    normalized = dict(request)
    defaults: JsonObject = {
        "context_id": context_id,
        "analysis_scope": {"scope_type": "household", "entity_id": household_id},
        "as_of_date": as_of,
    }
    if command == "analyze.run":
        analysis_id = analysis or normalized.get("analysis_id")
        if not isinstance(analysis_id, str):
            raise ValueError(
                "use --analysis NAME or provide analysis_id in --request JSON"
            )
        if not analysis_id.startswith("analysis."):
            analysis_id = "analysis." + analysis_id
        defaults.update(
            {
                "analysis_id": analysis_id,
                "analysis_contract_version": "0.1",
                "scenario": None,
                "period": None,
            }
        )
        if analysis_id == "analysis.realized_monthly_cashflow":
            start = date.fromisoformat(as_of).replace(day=1)
            end = (
                date(start.year + 1, 1, 1)
                if start.month == 12
                else date(start.year, start.month + 1, 1)
            )
            defaults["period"] = {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
    elif command == "workflow.next":
        defaults["analysis_id"] = "analysis.net_worth"
    for key, value in defaults.items():
        if key in normalized and normalized[key] != value:
            raise ValueError(
                f"--as-of/--analysis/--scope conflicts with request field {key}"
            )
        normalized.setdefault(key, value)
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


def _compact_component(value: JsonObject) -> JsonObject:
    keys = (
        "component_id",
        "status",
        "value",
        "minimum_value",
        "maximum_value",
        "expected_value",
        "next_question",
        "explain_ref",
    )
    result: JsonObject = {key: value[key] for key in keys if key in value}
    for kind in ("blockers", "warnings"):
        result[kind] = [
            {
                key: item[key]
                for key in ("code", "message_key", "severity", "explain_ref")
                if key in item
            }
            for item in cast(list[JsonObject], value.get(kind, []))
        ]
    return result


def _compact_analysis(value: JsonObject) -> JsonObject:
    result: JsonObject = {
        key: value[key]
        for key in (
            "analysis_id",
            "analysis_contract_version",
            "analysis_scope",
            "as_of_date",
            "period",
            "used_generation",
            "result_id",
            "scenario_id",
            "knowledge_type",
        )
        if key in value
    }
    result["view"] = "compact"
    if "components" in value:
        result["components"] = [
            _compact_component(item)
            for item in cast(list[JsonObject], value["components"])
        ]
    if "domain_counts" in value:
        result["domain_counts"] = [
            {"domain_id": item["domain_id"], "count": item["count"]}
            for item in cast(list[JsonObject], value["domain_counts"])
        ]
    for view_name in ("baseline", "scenario", "delta"):
        view = value.get(view_name)
        if isinstance(view, dict):
            result[view_name] = {
                key: _compact_component(cast(JsonObject, component))
                for key, component in view.items()
            }
    return result


def _compact_discovery(value: JsonObject) -> JsonObject:
    candidates = cast(list[JsonObject], value["candidates"])
    return {
        "view": "compact",
        "candidates": [
            {
                "candidate_id": item["candidate_id"],
                "frequency": item["frequency"],
                "direction": item["direction"],
                "projected_next_period": item["expected_period"],
                "money": item["money"],
                "amount_range": item["amount_range"],
                "score": cast(JsonObject, item["detection"])["score"],
                "transaction_count": len(
                    cast(list[JsonObject], item["transaction_refs"])
                ),
            }
            for item in candidates
        ],
        "attention_items": [
            {
                key: item[key]
                for key in (
                    "code",
                    "frequency",
                    "required_observations",
                    "actual_observations",
                )
                if key in item
            }
            for item in cast(list[JsonObject], value["attention_items"])
        ],
    }


def _write_discovery_table(value: JsonObject) -> None:
    print(
        "ID  FREQUENCY  DIRECTION  AMOUNT  SCORE  TRANSACTIONS  PROJECTED NEXT PERIOD"
    )
    for item in cast(list[JsonObject], value["candidates"]):
        money = item["money"]
        amount = (
            f"{money['amount']} {money['currency']}"
            if isinstance(money, dict)
            else json.dumps(item["amount_range"], ensure_ascii=False, sort_keys=True)
        )
        period = cast(JsonObject, item["projected_next_period"])
        print(
            f"{item['candidate_id']}  {item['frequency']}  {item['direction']}  {amount}  {item['score']}  {item['transaction_count']}  {period['start_date']}..{period['end_exclusive']}"
        )


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


def _write_workflow_text(result: JsonObject) -> None:
    changes = cast(JsonObject, result["change_summary"])
    sections = cast(list[JsonObject], result["context_sections"])
    analyses = cast(list[JsonObject], result["analysis_results"])
    action = cast(JsonObject | None, result["next_action"])
    changed = sum(
        len(cast(list[JsonValue], changes.get(key, [])))
        for key in ("confirmed", "proposed", "replaced", "rejected")
    )
    confirmed = sum(
        len(cast(list[JsonValue], section.get("confirmed_items", [])))
        for section in sections
    )
    uncertain = sum(
        len(cast(list[JsonValue], section.get("open_proposals", [])))
        + sum(
            requirement.get("state") != "present"
            for requirement in cast(list[JsonObject], section.get("requirements", []))
        )
        for section in sections
    )
    insights = (
        ", ".join(
            f"{analysis.get('analysis_id', 'analyse')}: {analysis.get('status', 'beschikbaar')}"
            for analysis in analyses
        )
        or "Nog geen analyse beschikbaar."
    )
    question = (
        str(action.get("question", "Voer de voorgestelde vervolgstap uit."))
        if action is not None
        else "Geen vervolgvraag; de gevraagde context is compleet."
    )
    lines = (
        "Zojuist gewijzigd",
        f"{changed} wijziging(en) sinds de opgegeven generatie.",
        "",
        "Bevestigde context",
        f"{confirmed} bevestigd(e) contextitem(s) in {len(sections)} secties.",
        "",
        "Openstaand en onzeker",
        f"{uncertain} open voorstel(len) of ontbrekende vereiste(n).",
        "",
        "Actuele inzichten",
        insights,
        "",
        "Volgende vraag",
        question,
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
    parser = JsonArgumentParser(
        prog="topo",
        description="Local financial context CLI. JSON requests come from --request PATH or stdin; use contract describe for exact contract IDs.",
        epilog=(
            "Examples: topo context summary --package ./context.topo --as-of 2026-09-29 --json; "
            "topo analyze run --package ./context.topo --analysis context_inventory "
            "--as-of 2026-09-29 --compact --json; "
            "topo workflow respond --package ./context.topo --request answer.json --json"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    commands = parser.add_subparsers(
        dest="group", required=True, parser_class=JsonArgumentParser
    )

    workspace_init = commands.add_parser("init")
    workspace_init.add_argument("directory", nargs="?", type=Path, default=Path("."))

    contract = commands.add_parser("contract")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    contract_commands.add_parser(
        "describe",
        help="Describe package-independent CLI contracts (no --package).",
        description="Describe package-independent CLI contracts. This command does not use --package.",
    )
    schema = contract_commands.add_parser("schema")
    schema.add_argument("command", choices=COMMANDS)
    record_schema = contract_commands.add_parser("record-schema")
    record_schema.add_argument(
        "record_type", choices=("entities", "assertions", "evidence", "proposals")
    )

    context = commands.add_parser("context")
    context_commands = context.add_subparsers(dest="context_command", required=True)
    initialize = context_commands.add_parser("init")
    initialize.add_argument("--package", type=Path, required=True)
    status = context_commands.add_parser("status")
    status.add_argument("--package", type=Path, required=True)
    summary = context_commands.add_parser("summary")
    summary.add_argument("--package", type=Path, required=True)
    summary.add_argument("--as-of", required=True, metavar="DATE")
    verify = context_commands.add_parser("verify")
    verify.add_argument("--package", type=Path, required=True)
    for name in ("migrate", "restore", "compact", "privacy-scrub"):
        lifecycle = context_commands.add_parser(name)
        lifecycle.add_argument("--package", type=Path, required=True)

    proposal = commands.add_parser("proposal")
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    for name in (
        "submit",
        "confirm",
        "correct",
        "reject",
        "confirm-batch",
        "reject-batch",
    ):
        proposal_command = proposal_commands.add_parser(name)
        proposal_command.add_argument("--package", type=Path, required=True)

    source = commands.add_parser("source")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    source_import = source_commands.add_parser("import")
    source_import.add_argument("--package", type=Path, required=True)
    source_import.add_argument("--records-csv", type=Path)
    source_classify = source_commands.add_parser("classify-batch")
    source_classify.add_argument("--package", type=Path, required=True)

    discover = commands.add_parser("discover")
    discover_commands = discover.add_subparsers(dest="discover_command", required=True)
    discover_run = discover_commands.add_parser("run")
    discover_run.add_argument("--package", type=Path, required=True)
    discover_run.add_argument(
        "--as-of",
        metavar="DATE",
        help="date for shorthand request; required without JSON request",
    )
    discover_run.add_argument(
        "--scope",
        metavar="HOUSEHOLD_ID",
        help="household when the package has multiple households",
    )
    discover_run.add_argument(
        "--compact",
        action="store_true",
        help="omit proposal and reference details from JSON",
    )
    discover_run.add_argument(
        "--table",
        action="store_true",
        help="print a compact human-readable candidate table",
    )

    analyze = commands.add_parser("analyze")
    analyze_commands = analyze.add_subparsers(dest="analyze_command", required=True)
    analyze_run = analyze_commands.add_parser("run")
    analyze_run.add_argument("--package", type=Path, required=True)
    analyze_run.add_argument(
        "--analysis",
        choices=(
            "context_inventory",
            "net_worth",
            "normalized_monthly_cashflow",
            "realized_monthly_cashflow",
        ),
        help="analysis name for shorthand request",
    )
    analyze_run.add_argument(
        "--as-of", metavar="DATE", help="explicit date for shorthand request"
    )
    analyze_run.add_argument(
        "--scope",
        metavar="HOUSEHOLD_ID",
        help="household when the package has multiple households",
    )
    analyze_run.add_argument(
        "--compact",
        action="store_true",
        help="omit reference and calculation details from JSON",
    )

    workflow = commands.add_parser("workflow")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_next = workflow_commands.add_parser("next")
    workflow_next.add_argument("--package", type=Path, required=True)
    workflow_next.add_argument(
        "--as-of", metavar="DATE", help="explicit date for shorthand request"
    )
    workflow_next.add_argument(
        "--scope",
        metavar="HOUSEHOLD_ID",
        help="household when the package has multiple households",
    )
    workflow_next.add_argument(
        "--request",
        type=Path,
        metavar="PATH",
        help="read the workflow.next JSON request from PATH (defaults to stdin)",
    )
    workflow_respond = workflow_commands.add_parser("respond")
    workflow_respond.add_argument("--package", type=Path, required=True)
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
    for group in commands.choices.values():
        nested = tuple(
            action
            for action in group._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        if not nested:
            group.add_argument(
                "--request",
                type=Path,
                metavar="PATH",
                help="read JSON request from PATH (defaults to stdin)",
            )
            group.epilog = "Contract ID: " + next(
                (key for key, value in CLI_COMMANDS.items() if value == group.prog),
                "see topo contract describe --json",
            )
        for action in nested:
            for leaf in action.choices.values():
                if not any(option.dest == "request" for option in leaf._actions):
                    leaf.add_argument(
                        "--request",
                        type=Path,
                        metavar="PATH",
                        help="read JSON request from PATH (defaults to stdin)",
                    )
                leaf.epilog = "Contract ID: " + next(
                    (
                        key
                        for key, value in CLI_COMMANDS.items()
                        if value
                        == f"topo {group.prog.split()[-1]} {leaf.prog.split()[-1]}"
                    ),
                    "see topo contract describe --json",
                )
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
            if "batch_id" in request:
                request_template["batch_id"] = request["batch_id"]
            else:
                request_template["proposal_ref"] = request.get("proposal_ref")
            reason_code = "PROPOSAL_DECISION_REQUIRES_AUTHORIZATION"
        if command == "context.migrate":
            reason_code = "CONTEXT_MIGRATION_REQUIRES_AUTHORIZATION"
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


def _usage_command(arguments: list[str]) -> str:
    words = [argument for argument in arguments if not argument.startswith("-")]
    if words:
        for command, cli in CLI_COMMANDS.items():
            pieces = cli.split()[1:]
            if words[: len(pieces)] == pieces:
                return command
    return "validate"


def _usage_hint(reason: str) -> str:
    if "--request" in reason or "unrecognized arguments" in reason:
        return "Use --request PATH or send a JSON object on stdin; see the command's --help."
    return "See topo --help and the command's --help for valid syntax."


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
    try:
        if "--request" in arguments:
            request_index = arguments.index("--request")
            if request_index + 1 >= len(arguments) or arguments[
                request_index + 1
            ].startswith("--"):
                raise UsageError("--request requires a file path")
            request_path = Path(arguments[request_index + 1])
            del arguments[request_index : request_index + 2]
        args = _parser().parse_args(arguments)
    except UsageError as error:
        reason = str(error)
        if json_output:
            _write_json(
                _error_envelope(
                    _usage_command(arguments),
                    {"contract_version": CONTRACT_VERSION},
                    code="INVALID_USAGE",
                    message_key="diagnostic.invalid_usage",
                    path="/argv",
                    params={"reason": reason, "hint": _usage_hint(reason)},
                    retryable=False,
                )
            )
        else:
            print(f"{reason}\n{_usage_hint(reason)}", file=sys.stderr)
        return 2
    if args.group == "init":
        command = "workspace.init"
    elif args.group == "contract":
        command = f"contract.{args.contract_command.replace('-', '_')}"
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
        request = _apply_shorthand(
            command,
            args,
            _normalize_request(command, args, _request_from_source(request_path)),
        )
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
        if command == "contract.record_schema":
            _write_json(
                _success_envelope(
                    command,
                    request,
                    {
                        "record_type": args.record_type,
                        "context_schema_version": "topo.context/0.2",
                        "schema": record_collection_schema(args.record_type),
                    },
                )
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
        if command == "context.verify":
            verify_request = ContextVerifyRequest.model_validate(request, strict=True)
            verify_result = EngineCore(
                FileSystemStorageAdapter(Path(verify_request.package))
            ).verify_context()
            verify_result_json = model_to_json_object(verify_result)
            _write_json(
                _success_envelope(
                    command,
                    request,
                    verify_result_json,
                    context_id=verify_result.context_id,
                    generation_before=verify_result.generation_id,
                    generation_after=verify_result.generation_id,
                )
            )
            return 0
        if command == "context.summary":
            summary_result = EngineCore(
                FileSystemStorageAdapter(args.package)
            ).context_summary(date.fromisoformat(args.as_of))
            generation = str(summary_result["generation_id"])
            _write_json(
                _success_envelope(
                    command,
                    request,
                    summary_result,
                    context_id=str(summary_result["context_id"]),
                    generation_before=generation,
                    generation_after=generation,
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
        if command == "source.classify-batch":
            outcome = EngineCore(
                FileSystemStorageAdapter(args.package)
            ).classify_source_proposal_batch(
                SourceClassificationBatchRequest.model_validate_json(
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
            if args.table and json_output:
                raise ValueError("--table cannot be combined with --json")
            discovery_result = (
                _compact_discovery(discovery_outcome.result)
                if args.compact or args.table
                else discovery_outcome.result
            )
            if args.table:
                _write_discovery_table(discovery_result)
                return 0
            _write_json(
                _success_envelope(
                    command,
                    request,
                    discovery_result,
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
            if args.compact:
                analysis_result = _compact_analysis(analysis_result)
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
            envelope = _success_envelope(
                command,
                request,
                workflow_result,
                context_id=workflow_request.context_id,
                generation_before=generation,
                generation_after=generation,
                refs=(Ref(ref_type="generation", id=generation),),
            )
            if json_output:
                _write_json(envelope)
            else:
                _write_workflow_text(workflow_result)
            return 0
        if command == "workflow.respond":
            outcome = EngineCore(
                FileSystemStorageAdapter(args.package)
            ).respond_to_workflow(
                WorkflowRespondRequest.model_validate_json(
                    json.dumps(request), strict=True
                )
            )
            _write_json(_mutation_envelope(command, request, outcome))
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
            elif command == "proposal.reject":
                outcome = engine.reject_proposal(
                    ProposalRejectRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            elif command == "proposal.confirm-batch":
                outcome = engine.confirm_proposal_batch(
                    ProposalBatchConfirmRequest.model_validate_json(
                        json.dumps(request), strict=True
                    )
                )
            else:
                outcome = engine.reject_proposal_batch(
                    ProposalBatchRejectRequest.model_validate_json(
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
