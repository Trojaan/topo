from __future__ import annotations

from copy import deepcopy
from typing import Literal, cast

from jsonschema import Draft202012Validator, FormatChecker

from topo.identifiers import UUID7_PATTERN
from topo.models import (
    CommandDescriptor,
    DescribeResult,
    JsonObject,
    SchemaResult,
    model_to_json_object,
)

SchemaObject = dict[str, object]

CONTRACT_VERSION: Literal["topo.cli/0.1"] = "topo.cli/0.1"
COMMANDS = (
    "context.init",
    "contract.describe",
    "contract.schema",
    "proposal.submit",
    "proposal.confirm",
    "proposal.correct",
    "proposal.reject",
)
SCHEMA_COMMANDS = (
    *COMMANDS,
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


def _uuid7() -> SchemaObject:
    return {"type": "string", "pattern": UUID7_PATTERN}


def _closed_object(
    properties: SchemaObject, required: tuple[str, ...] = ()
) -> SchemaObject:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": properties,
    }


def _ref(ref_types: tuple[str, ...] = ()) -> SchemaObject:
    ref_type: SchemaObject = {"type": "string"}
    if ref_types:
        ref_type = {"enum": list(ref_types)}
    return _closed_object(
        {"ref_type": ref_type, "id": _uuid7()},
        ("ref_type", "id"),
    )


def _money() -> SchemaObject:
    return _closed_object(
        {
            "amount": {"type": "string", "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$"},
            "currency": {"type": "string", "pattern": r"^[A-Z]{3}$"},
        },
        ("amount", "currency"),
    )


def _scope() -> SchemaObject:
    return _closed_object(
        {
            "scope_type": {"enum": ["person", "household"]},
            "entity_id": _uuid7(),
        },
        ("scope_type", "entity_id"),
    )


def _scenario_assumption() -> SchemaObject:
    common = {
        "target_ref": _ref(("entity",)),
        "money": _money(),
        "effective_date": {"type": "string", "format": "date"},
        "reason": {"type": "string", "minLength": 1},
    }
    recurring = _closed_object(
        {
            "assumption_type": {"const": "recurring_cashflow_change"},
            **common,
            "change": {"enum": ["add", "replace", "end"]},
        },
        (
            "assumption_type",
            "target_ref",
            "change",
            "money",
            "effective_date",
            "reason",
        ),
    )
    one_off = _closed_object(
        {
            "assumption_type": {"const": "one_off_cashflow"},
            **common,
            "direction": {"enum": ["inflow", "outflow"]},
        },
        (
            "assumption_type",
            "target_ref",
            "direction",
            "money",
            "effective_date",
            "reason",
        ),
    )
    override = _closed_object(
        {"assumption_type": {"const": "value_override"}, **common},
        ("assumption_type", "target_ref", "money", "effective_date", "reason"),
    )
    return {"oneOf": [recurring, one_off, override]}


def _scenario() -> SchemaObject:
    return {
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["scenario_id", "assumptions"],
                "properties": {
                    "scenario_id": _uuid7(),
                    "assumptions": {
                        "type": "array",
                        "items": _scenario_assumption(),
                    },
                },
            },
            {"type": "null"},
        ]
    }


def _actor() -> SchemaObject:
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


def _authorization() -> SchemaObject:
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


def _base_input_properties() -> SchemaObject:
    return {"contract_version": {"const": CONTRACT_VERSION}}


def _mutation_input(command: str) -> SchemaObject:
    properties = _base_input_properties()
    properties.update(
        {
            "operation_id": _uuid7(),
            "context_id": _uuid7(),
            "expected_generation": _uuid7(),
            "actor": _actor(),
            "reason": {"type": "string", "minLength": 1},
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
    if command in {"proposal.confirm", "proposal.correct", "proposal.reject"}:
        properties["proposal_ref"] = _uuid7()
        required.append("proposal_ref")
    if command in {"proposal.confirm", "proposal.correct"}:
        properties["authorization"] = {"oneOf": [_authorization(), {"type": "null"}]}
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
                        (
                            "source_id",
                            "record_id",
                            "booking_date",
                            "money",
                            "description",
                        ),
                    ),
                },
            }
        )
        required.extend(["adapter", "records"])
    if command == "proposal.submit":
        properties["proposal"] = _closed_object(
            {
                "proposal_type": {"const": "assertion"},
                "producer": _closed_object(
                    {
                        "producer_type": {"enum": ["agent", "rule_module"]},
                        "producer_id": {"type": "string", "minLength": 1},
                        "producer_version": {"type": "string", "minLength": 1},
                    },
                    ("producer_type", "producer_id", "producer_version"),
                ),
                "proposed_assertion": {
                    **_closed_object(
                        {
                            "subject_ref": _ref(("entity",)),
                            "predicate": {"type": "string", "minLength": 1},
                            "object_ref": _ref(("entity",)),
                            "object_value": _closed_object(
                                {
                                    "value_type": {"type": "string", "minLength": 1},
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
                            "module_data": {"type": "object"},
                        },
                        (
                            "subject_ref",
                            "predicate",
                            "valid_time",
                            "knowledge_type",
                            "module_data",
                        ),
                    ),
                    "oneOf": [
                        {
                            "required": ["object_ref"],
                            "not": {"required": ["object_value"]},
                        },
                        {
                            "required": ["object_value"],
                            "not": {"required": ["object_ref"]},
                        },
                    ],
                },
                "evidence_refs": {
                    "type": "array",
                    "minItems": 1,
                    "items": _ref(("evidence",)),
                },
                "reason_ref": {"type": "string", "minLength": 1},
                "detection": {
                    "oneOf": [
                        _closed_object(
                            {
                                "scheme": {"type": "string", "minLength": 1},
                                "score": {
                                    "type": "string",
                                    "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$",
                                },
                            },
                            ("scheme", "score"),
                        ),
                        {"type": "null"},
                    ]
                },
            },
            (
                "proposal_type",
                "producer",
                "proposed_assertion",
                "evidence_refs",
                "reason_ref",
            ),
        )
        required.append("proposal")
    if command == "proposal.correct":
        properties["correction"] = {
            **_closed_object(
                {
                    "object_ref": _ref(("entity",)),
                    "object_value": _closed_object(
                        {
                            "value_type": {"type": "string", "minLength": 1},
                            "value": {},
                        },
                        ("value_type", "value"),
                    ),
                    "reason": {"type": "string", "minLength": 1},
                },
                ("reason",),
            ),
            "oneOf": [
                {
                    "required": ["object_ref"],
                    "not": {"required": ["object_value"]},
                },
                {
                    "required": ["object_value"],
                    "not": {"required": ["object_ref"]},
                },
            ],
        }
        required.append("correction")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_ref(command, "request"),
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def input_schema(command: str) -> SchemaObject:
    if command not in SCHEMA_COMMANDS:
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
                                "currency": {
                                    "type": "string",
                                    "pattern": r"^[A-Z]{3}$",
                                },
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
                "scenario": _scenario(),
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


def _result_schema(command: str) -> SchemaObject:
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
                        "required": [
                            "command",
                            "input_schema_ref",
                            "output_schema_ref",
                        ],
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
            {"proposal_id": _uuid7()},
            ("proposal_id",),
        )
    if command == "proposal.confirm":
        return _closed_object(
            {
                "proposal_id": _uuid7(),
                "assertion_id": _uuid7(),
                "evidence_id": _uuid7(),
            },
            ("proposal_id", "assertion_id", "evidence_id"),
        )
    if command == "proposal.correct":
        return _closed_object(
            {
                "proposal_id": _uuid7(),
                "assertion_id": _uuid7(),
                "evidence_id": _uuid7(),
            },
            ("proposal_id", "assertion_id", "evidence_id"),
        )
    if command == "proposal.reject":
        return _closed_object(
            {"proposal_id": _uuid7()},
            ("proposal_id",),
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
        requirement = _closed_object(
            {
                "requirement": {"type": "string", "minLength": 1},
                "state": {
                    "enum": [
                        "present",
                        "missing",
                        "conflicting",
                        "insufficiently_current",
                        "unallocated",
                    ]
                },
                "impact": {"type": "string", "minLength": 1},
            },
            ("requirement", "state", "impact"),
        )
        calculation_step = _closed_object(
            {
                "step_id": {"type": "string", "minLength": 1},
                "operation": {"type": "string", "minLength": 1},
                "inputs": {
                    "type": "array",
                    "items": {"oneOf": [_ref(), _money()]},
                },
                "unrounded_result": _money(),
            },
            ("step_id", "operation", "inputs", "unrounded_result"),
        )
        component = _closed_object(
            {
                "component_id": {"type": "string", "minLength": 1},
                "status": {"enum": ["complete", "provisional", "unavailable"]},
                "value": _money(),
                "used_assertion_refs": {"type": "array", "items": _ref(("assertion",))},
                "used_evidence_refs": {"type": "array", "items": _ref(("evidence",))},
                "assumptions": {
                    "type": "array",
                    "items": _scenario_assumption(),
                },
                "calculation_steps": {
                    "type": "array",
                    "items": calculation_step,
                },
                "rounding": _closed_object(
                    {
                        "mode": {"enum": ["currency_default", "none"]},
                        "presented_decimals": {"type": "integer", "minimum": 0},
                    },
                    ("mode", "presented_decimals"),
                ),
                "requirements": {"type": "array", "items": requirement},
                "blockers": {"type": "array", "items": _diagnostic_schema()},
                "warnings": {"type": "array", "items": _diagnostic_schema()},
                "next_question": {"type": ["string", "null"]},
                "explain_ref": _ref(("analysis_component",)),
            },
            (
                "component_id",
                "status",
                "used_assertion_refs",
                "used_evidence_refs",
                "assumptions",
                "calculation_steps",
                "rounding",
                "requirements",
                "blockers",
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


def _diagnostic_schema() -> SchemaObject:
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


def _next_action_schema() -> SchemaObject:
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


def output_schema(command: str) -> SchemaObject:
    if command not in SCHEMA_COMMANDS:
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


def describe_result() -> JsonObject:
    return model_to_json_object(
        DescribeResult(
            supported_contract_versions=(CONTRACT_VERSION,),
            commands=tuple(
                CommandDescriptor(
                    command=command,
                    input_schema_ref=schema_ref(command, "request"),
                    output_schema_ref=schema_ref(command, "response"),
                )
                for command in COMMANDS
            ),
        )
    )


def schema_result(command: str) -> JsonObject:
    return model_to_json_object(
        SchemaResult(
            command=command,
            input_schema_ref=schema_ref(command, "request"),
            output_schema_ref=schema_ref(command, "response"),
            input_schema=cast(JsonObject, input_schema(command)),
            output_schema=cast(JsonObject, output_schema(command)),
        )
    )


def validate_request(command: str, request: JsonObject) -> None:
    Draft202012Validator(
        input_schema(command), format_checker=FormatChecker()
    ).validate(request)


def validate_response(command: str, response: JsonObject) -> None:
    Draft202012Validator(
        output_schema(command), format_checker=FormatChecker()
    ).validate(response)
