from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from jsonschema import Draft202012Validator


CONTRACT_VERSION = "topo.cli/0.1"
UUID7_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
COMMANDS = ("context.init", "contract.describe", "contract.schema")


def schema_ref(command: str, direction: str) -> str:
    slug = command.replace(".", "-")
    return f"topo://schema/{slug}-{direction}/0.1"


def input_schema(command: str) -> Dict[str, Any]:
    if command not in COMMANDS:
        raise KeyError(command)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_ref(command, "request"),
        "type": "object",
        "additionalProperties": False,
        "required": ["contract_version"],
        "properties": {
            "contract_version": {"const": CONTRACT_VERSION},
        },
    }


def _result_schema(command: str) -> Dict[str, Any]:
    uuid7 = {"type": "string", "pattern": UUID7_PATTERN}
    if command == "context.init":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "context_id",
                "generation_id",
                "mutation_id",
                "person_id",
                "household_id",
                "membership_assertion_id",
            ],
            "properties": {
                name: deepcopy(uuid7)
                for name in (
                    "context_id",
                    "generation_id",
                    "mutation_id",
                    "person_id",
                    "household_id",
                    "membership_assertion_id",
                )
            },
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
            "result": _result_schema(command),
            "diagnostics": {"type": "array"},
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
