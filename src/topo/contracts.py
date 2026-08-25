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
        properties["records"] = {"type": "array", "items": {"type": "object"}}
        required.append("records")
    if command == "proposal.submit":
        properties["proposal"] = {"type": "object"}
        required.append("proposal")
    if command == "proposal.correct":
        properties["correction"] = {"type": "object"}
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
    elif command in {"discover.run", "analyze.run"}:
        properties["context_id"] = _uuid7()
        required.append("context_id")
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
    return {"type": "object"}


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
            "related_refs": {"type": "array"},
        },
    }


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
            "next_actions": {"type": "array"},
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
