from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from jsonschema import Draft202012Validator

from topo.identifiers import UUID7_PATTERN


CONTRACT_VERSION = "topo.cli/0.1"
COMMANDS = (
    "context.init",
    "contract.describe",
    "contract.schema",
    "source.import",
    "discover.run",
    "proposal.submit",
    "proposal.confirm",
    "proposal.correct",
    "proposal.reject",
    "validate",
    "analyze.run",
    "explain",
    "workflow.next",
)
MUTATING_COMMANDS = {
    "source.import",
    "proposal.submit",
    "proposal.confirm",
    "proposal.correct",
    "proposal.reject",
}


def schema_ref(command: str, direction: str) -> str:
    slug = command.replace(".", "-")
    return f"topo://schema/{slug}-{direction}/0.1"


def _uuid7() -> Dict[str, Any]:
    return {"type": "string", "pattern": UUID7_PATTERN}


def _closed_object(
    properties: Dict[str, Any], required: tuple[str, ...] = ()
) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": properties,
    }


def _ref(ref_types: tuple[str, ...] = ()) -> Dict[str, Any]:
    ref_type: Dict[str, Any] = {"type": "string"}
    if ref_types:
        ref_type = {"enum": list(ref_types)}
    return _closed_object(
        {"ref_type": ref_type, "id": _uuid7()},
        ("ref_type", "id"),
    )


def _money() -> Dict[str, Any]:
    return _closed_object(
        {
            "amount": {"type": "string", "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$"},
            "currency": {"type": "string", "pattern": r"^[A-Z]{3}$"},
        },
        ("amount", "currency"),
    )


def _scope() -> Dict[str, Any]:
    return _closed_object(
        {
            "scope_type": {"enum": ["person", "household"]},
            "entity_id": _uuid7(),
        },
        ("scope_type", "entity_id"),
    )


def _actor() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["actor_type", "actor_id"],
        "properties": {
            "actor_type": {
                "enum": ["human", "agent", "rule_module", "source_adapter", "system"]
            },
            "actor_id": {"type": "string", "minLength": 1},
        },
    }


def _authorization() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["preview_ref", "authorized_by", "authorized_at"],
        "properties": {
            "preview_ref": {"type": "string", "minLength": 1},
            "authorized_by": _actor(),
            "authorized_at": {"type": "string", "format": "date-time"},
        },
    }


def _base_input_properties() -> Dict[str, Any]:
    return {"contract_version": {"const": CONTRACT_VERSION}}


def _mutation_input(command: str) -> Dict[str, Any]:
    properties = _base_input_properties()
    properties.update(
        {
            "operation_id": _uuid7(),
            "context_id": _uuid7(),
            "expected_generation": _uuid7(),
            "actor": _actor(),
            "reason": {"type": "string", "minLength": 1},
            "authorization": {"oneOf": [_authorization(), {"type": "null"}]},
        }
    )
    required = [
        "contract_version",
        "operation_id",
        "context_id",
        "expected_generation",
        "actor",
        "reason",
    ]
    if command.startswith("proposal."):
        properties["proposal_ref"] = {"type": "string", "minLength": 1}
        required.append("proposal_ref")
    if command in {"proposal.confirm", "proposal.correct"}:
        required.append("authorization")
    if command == "source.import":
        properties.update(
            {
                "adapter": _closed_object(
                    {
                        "adapter_id": {"type": "string", "minLength": 1},
                        "adapter_version": {"type": "string", "minLength": 1},
                    },
                    ("adapter_id", "adapter_version"),
                ),
                "records": {
                    "type": "array",
                    "items": _closed_object(
                        {
                            "source_id": {"type": "string", "minLength": 1},
                            "record_id": {"type": "string", "minLength": 1},
                            "booking_date": {"type": "string", "format": "date"},
                            "money": _money(),
                            "description": {"type": "string"},
                            "source_classification": _closed_object(
                                {
                                    "category": {"type": "string"},
                                    "rule_version": {"type": "string"},
                                    "explanation": {"type": "string"},
                                },
                                ("category", "rule_version", "explanation"),
                            ),
                        },
                        ("source_id", "record_id", "booking_date", "money", "description"),
                    ),
                },
            }
        )
        required.extend(["adapter", "records"])
    if command == "proposal.submit":
        properties["proposal"] = _closed_object(
            {
                "candidate_ref": {"type": "string", "minLength": 1},
                "proposal_type": {"type": "string", "minLength": 1},
                "proposed_assertion": _closed_object(
                    {
                        "subject_ref": _ref(("entity",)),
                        "predicate": {"type": "string", "minLength": 1},
                        "object_value": _closed_object(
                            {
                                "value_type": {"type": "string"},
                                "value": {},
                            },
                            ("value_type", "value"),
                        ),
                        "valid_time": _closed_object(
                            {
                                "start": {"type": "string", "format": "date"},
                                "end_exclusive": {
                                    "type": ["string", "null"],
                                    "format": "date",
                                },
                            },
                            ("start", "end_exclusive"),
                        ),
                        "knowledge_type": {"const": "inferred"},
                    },
                    ("subject_ref", "predicate", "object_value", "valid_time", "knowledge_type"),
                ),
                "evidence_refs": {"type": "array", "items": _ref(("evidence",))},
                "reason_ref": {"type": "string", "minLength": 1},
            },
            (
                "candidate_ref",
                "proposal_type",
                "proposed_assertion",
                "evidence_refs",
                "reason_ref",
            ),
        )
        required.append("proposal")
    if command == "proposal.correct":
        properties["correction"] = _closed_object(
            {
                "object_value": _closed_object(
                    {"value_type": {"type": "string"}, "value": {}},
                    ("value_type", "value"),
                ),
                "reason": {"type": "string", "minLength": 1},
            },
            ("object_value", "reason"),
        )
        required.append("correction")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_ref(command, "request"),
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def input_schema(command: str) -> Dict[str, Any]:
    if command not in COMMANDS:
        raise KeyError(command)
    if command in MUTATING_COMMANDS:
        return _mutation_input(command)

    properties = _base_input_properties()
    required = ["contract_version"]
    if command == "context.init":
        properties.update(
            {
                "package": {"type": "string", "minLength": 1},
                "operation_id": _uuid7(),
                "expected_generation": {"type": "null"},
                "actor": _actor(),
                "reason": {"type": "string", "minLength": 1},
            }
        )
        required.extend(
            ["package", "operation_id", "expected_generation", "actor", "reason"]
        )
    elif command == "discover.run":
        properties.update(
            {
                "context_id": _uuid7(),
                "analysis_scope": _scope(),
                "as_of_date": {"type": "string", "format": "date"},
            }
        )
        required.extend(["context_id", "analysis_scope", "as_of_date"])
    elif command == "analyze.run":
        properties.update(
            {
                "analysis_id": {"type": "string", "minLength": 1},
                "analysis_contract_version": {"type": "string", "minLength": 1},
                "context_id": _uuid7(),
                "analysis_scope": _scope(),
                "as_of_date": {"type": "string", "format": "date"},
                "period": {
                    "oneOf": [
                        _closed_object(
                            {
                                "start_date": {"type": "string", "format": "date"},
                                "end_date": {"type": "string", "format": "date"},
                            },
                            ("start_date", "end_date"),
                        ),
                        {"type": "null"},
                    ]
                },
                "reporting_currency": {
                    "oneOf": [
                        _closed_object(
                            {
                                "currency": {"type": "string", "pattern": r"^[A-Z]{3}$"},
                                "allowed_rate_assertion_refs": {
                                    "type": "array",
                                    "items": _ref(("assertion",)),
                                },
                            },
                            ("currency", "allowed_rate_assertion_refs"),
                        ),
                        {"type": "null"},
                    ]
                },
                "scenario": {"type": ["object", "null"]},
            }
        )
        required.extend(
            [
                "analysis_id",
                "analysis_contract_version",
                "context_id",
                "analysis_scope",
                "as_of_date",
                "period",
                "reporting_currency",
                "scenario",
            ]
        )
    elif command == "explain":
        properties["ref"] = {"type": "string", "minLength": 1}
        required.append("ref")
    elif command == "workflow.next":
        properties["context_id"] = _uuid7()
        required.append("context_id")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_ref(command, "request"),
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _result_schema(command: str) -> Dict[str, Any]:
    uuid7 = _uuid7()
    if command == "context.init":
        names = (
            "context_id",
            "generation_id",
            "mutation_id",
            "person_id",
            "household_id",
            "membership_assertion_id",
        )
        return {
            "type": "object",
            "additionalProperties": False,
            "required": list(names),
            "properties": {name: deepcopy(uuid7) for name in names},
        }
    if command == "contract.describe":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["supported_contract_versions", "commands"],
            "properties": {
                "supported_contract_versions": {
                    "type": "array",
                    "prefixItems": [{"const": CONTRACT_VERSION}],
                    "items": False,
                },
                "commands": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["command", "input_schema_ref", "output_schema_ref"],
                        "properties": {
                            "command": {"enum": list(COMMANDS)},
                            "input_schema_ref": {"type": "string"},
                            "output_schema_ref": {"type": "string"},
                        },
                    },
                },
            },
        }
    if command == "contract.schema":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "command",
                "input_schema_ref",
                "output_schema_ref",
                "input_schema",
                "output_schema",
            ],
            "properties": {
                "command": {"enum": list(COMMANDS)},
                "input_schema_ref": {"type": "string"},
                "output_schema_ref": {"type": "string"},
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            },
        }
    if command == "source.import":
        return _closed_object(
            {
                "imported": {"type": "integer", "minimum": 0},
                "evidence_refs": {"type": "array", "items": _ref(("evidence",))},
                "transaction_refs": {"type": "array", "items": _ref(("entity",))},
            },
            ("imported", "evidence_refs", "transaction_refs"),
        )
    if command == "discover.run":
        candidate = _closed_object(
            {
                "candidate_id": {"type": "string", "minLength": 1},
                "proposal_type": {"type": "string", "minLength": 1},
                "producer": {"type": "string", "minLength": 1},
                "evidence_refs": {"type": "array", "items": _ref(("evidence",))},
            },
            ("candidate_id", "proposal_type", "producer", "evidence_refs"),
        )
        attention = _closed_object(
            {
                "code": {"type": "string", "minLength": 1},
                "related_refs": {"type": "array", "items": _ref()},
            },
            ("code", "related_refs"),
        )
        return _closed_object(
            {
                "candidates": {"type": "array", "items": candidate},
                "attention_items": {"type": "array", "items": attention},
            },
            ("candidates", "attention_items"),
        )
    if command == "proposal.submit":
        return _closed_object(
            {"proposal_ref": _ref(("proposal",)), "status": {"const": "open"}},
            ("proposal_ref", "status"),
        )
    if command in {"proposal.confirm", "proposal.correct"}:
        return _closed_object(
            {
                "proposal_ref": _ref(("proposal",)),
                "assertion_ref": _ref(("assertion",)),
                "decision": {"enum": ["confirmed", "corrected"]},
            },
            ("proposal_ref", "assertion_ref", "decision"),
        )
    if command == "proposal.reject":
        return _closed_object(
            {
                "proposal_ref": _ref(("proposal",)),
                "decision": {"const": "rejected"},
            },
            ("proposal_ref", "decision"),
        )
    if command == "validate":
        return _closed_object(
            {
                "valid": {"type": "boolean"},
                "validated_generation": {"oneOf": [_uuid7(), {"type": "null"}]},
            },
            ("valid", "validated_generation"),
        )
    if command == "analyze.run":
        component = _closed_object(
            {
                "component_id": {"type": "string", "minLength": 1},
                "status": {"enum": ["complete", "provisional", "unavailable"]},
                "value": _money(),
                "used_assertion_refs": {"type": "array", "items": _ref(("assertion",))},
                "used_evidence_refs": {"type": "array", "items": _ref(("evidence",))},
                "requirements": {"type": "array", "items": _closed_object({})},
                "warnings": {"type": "array", "items": _diagnostic_schema()},
                "next_question": {"type": ["string", "null"]},
                "explain_ref": _ref(("analysis_component",)),
            },
            (
                "component_id",
                "status",
                "used_assertion_refs",
                "used_evidence_refs",
                "requirements",
                "warnings",
                "next_question",
                "explain_ref",
            ),
        )
        return _closed_object(
            {
                "analysis_id": {"type": "string", "minLength": 1},
                "analysis_contract_version": {"type": "string", "minLength": 1},
                "analysis_scope": _scope(),
                "as_of_date": {"type": "string", "format": "date"},
                "period": {"type": ["object", "null"]},
                "used_generation": _uuid7(),
                "result_id": _uuid7(),
                "components": {"type": "array", "items": component},
            },
            (
                "analysis_id",
                "analysis_contract_version",
                "analysis_scope",
                "as_of_date",
                "period",
                "used_generation",
                "result_id",
                "components",
            ),
        )
    if command == "explain":
        return _closed_object(
            {
                "ref": {"type": "string", "minLength": 1},
                "meaning": {"type": "string"},
                "source_refs": {"type": "array", "items": _ref()},
                "assertion_refs": {"type": "array", "items": _ref(("assertion",))},
                "steps": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": _closed_object({})},
            },
            ("ref", "meaning", "source_refs", "assertion_refs", "steps", "assumptions"),
        )
    if command == "workflow.next":
        return _closed_object(
            {"actions": {"type": "array", "items": _next_action_schema()}},
            ("actions",),
        )
    raise KeyError(command)


def _diagnostic_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "code",
            "message_key",
            "severity",
            "path",
            "params",
            "retryable",
            "effect",
            "related_refs",
        ],
        "properties": {
            "code": {"type": "string"},
            "message_key": {"type": "string"},
            "severity": {"enum": ["info", "warning", "error"]},
            "path": {"type": "string"},
            "params": {"type": "object"},
            "retryable": {"type": "boolean"},
            "effect": {"const": "none"},
            "related_refs": {"type": "array", "items": _ref()},
        },
    }


def _next_action_schema() -> Dict[str, Any]:
    return _closed_object(
        {
            "action_id": _uuid7(),
            "action_type": {"type": "string", "minLength": 1},
            "action_contract_version": {"const": "topo.workflow-action/0.1"},
            "priority": {"enum": ["blocking", "required", "helpful", "optional"]},
            "reason_code": {"type": "string", "minLength": 1},
            "affected_component": {"type": ["string", "null"]},
            "related_refs": {"type": "array", "items": _ref()},
            "command": {"enum": list(COMMANDS)},
            "request_template": {"type": "object"},
            "input_schema_ref": {"type": "string"},
            "requires_user_input": {"type": "boolean"},
            "requires_authorization": {"type": "boolean"},
        },
        (
            "action_id",
            "action_type",
            "action_contract_version",
            "priority",
            "reason_code",
            "affected_component",
            "related_refs",
            "command",
            "request_template",
            "input_schema_ref",
            "requires_user_input",
            "requires_authorization",
        ),
    )


def output_schema(command: str) -> Dict[str, Any]:
    if command not in COMMANDS:
        raise KeyError(command)
    nullable_uuid7 = {"type": ["string", "null"], "pattern": UUID7_PATTERN}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_ref(command, "response"),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_version",
            "command",
            "operation_id",
            "context_id",
            "generation_before",
            "generation_after",
            "outcome",
            "result",
            "diagnostics",
            "next_actions",
            "trace",
        ],
        "properties": {
            "contract_version": {"const": CONTRACT_VERSION},
            "command": {"const": command},
            "operation_id": deepcopy(nullable_uuid7),
            "context_id": deepcopy(nullable_uuid7),
            "generation_before": deepcopy(nullable_uuid7),
            "generation_after": deepcopy(nullable_uuid7),
            "outcome": {
                "enum": [
                    "succeeded",
                    "no_change",
                    "rejected",
                    "conflict",
                    "requires_authorization",
                ]
            },
            "result": {"type": "object"},
            "diagnostics": {"type": "array", "items": _diagnostic_schema()},
            "next_actions": {"type": "array", "items": _next_action_schema()},
            "trace": {
                "type": "object",
                "additionalProperties": False,
                "required": ["normalized_request", "refs"],
                "properties": {
                    "normalized_request": {"type": "object"},
                    "refs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["ref_type", "id"],
                            "properties": {
                                "ref_type": {"type": "string"},
                                "id": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "allOf": [
            {
                "if": {
                    "properties": {"outcome": {"enum": ["succeeded", "no_change"]}},
                    "required": ["outcome"],
                },
                "then": {"properties": {"result": _result_schema(command)}},
            }
        ],
    }


def describe_result() -> Dict[str, Any]:
    return {
        "supported_contract_versions": [CONTRACT_VERSION],
        "commands": [
            {
                "command": command,
                "input_schema_ref": schema_ref(command, "request"),
                "output_schema_ref": schema_ref(command, "response"),
            }
            for command in COMMANDS
        ],
    }


def schema_result(command: str) -> Dict[str, Any]:
    return {
        "command": command,
        "input_schema_ref": schema_ref(command, "request"),
        "output_schema_ref": schema_ref(command, "response"),
        "input_schema": input_schema(command),
        "output_schema": output_schema(command),
    }


def validate_request(command: str, request: Dict[str, Any]) -> None:
    Draft202012Validator(input_schema(command)).validate(request)


def validate_response(command: str, response: Dict[str, Any]) -> None:
    Draft202012Validator(output_schema(command)).validate(response)
