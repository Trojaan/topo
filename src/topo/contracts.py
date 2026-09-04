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
    "workspace.init",
    "context.status",
    "context.verify",
    "contract.describe",
    "contract.schema",
    "context.migrate",
    "context.restore",
    "context.compact",
    "context.privacy_scrub",
    "source.import",
    "discover.run",
    "proposal.submit",
    "proposal.confirm",
    "proposal.correct",
    "proposal.reject",
    "proposal.confirm-batch",
    "proposal.reject-batch",
    "analyze.run",
    "workflow.next",
    "workflow.respond",
    "rule.validate",
    "rule.preview",
    "rule.activate",
    "explain",
)
SCHEMA_COMMANDS = (
    *COMMANDS,
    "validate",
)
MUTATING_COMMANDS = {
    "context.migrate",
    "context.restore",
    "context.compact",
    "context.privacy_scrub",
    "source.import",
    "proposal.submit",
    "proposal.confirm",
    "proposal.correct",
    "proposal.reject",
    "proposal.confirm-batch",
    "proposal.reject-batch",
    "workflow.respond",
    "rule.activate",
}


def schema_ref(command: str, direction: str) -> str:
    slug = command.replace(".", "-")
    version = (
        "0.2"
        if (command, direction)
        in {
            ("proposal.submit", "request"),
            ("proposal.submit", "response"),
            ("workflow.respond", "request"),
            ("workflow.respond", "response"),
            ("workflow.next", "response"),
            ("workflow.next", "request"),
            ("proposal.confirm-batch", "request"),
            ("proposal.confirm-batch", "response"),
            ("proposal.reject-batch", "request"),
            ("proposal.reject-batch", "response"),
        }
        else "0.1"
    )
    return f"topo://schema/{slug}-{direction}/{version}"


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


def _workflow_context_item_schema() -> SchemaObject:
    return _closed_object(
        {
            "item_id": _uuid7(),
            "label": {"type": "string", "minLength": 1},
            "entity_ref": {"oneOf": [_ref(("entity",)), {"type": "null"}]},
            "entity_type": {
                "enum": [
                    "person",
                    "account",
                    "asset",
                    "debt",
                    "contract",
                    "pension_entitlement",
                    "goal",
                    "recurring_cashflow",
                ]
            },
            "classification": {"type": ["string", "null"], "minLength": 1},
            "money": {"oneOf": [_money(), {"type": "null"}]},
            "amount_range": {
                "oneOf": [
                    _closed_object(
                        {"minimum": _money(), "maximum": _money()},
                        ("minimum", "maximum"),
                    ),
                    {"type": "null"},
                ]
            },
            "typical_money": {"oneOf": [_money(), {"type": "null"}]},
            "direction": {"enum": ["inflow", "outflow", None]},
            "frequency": {
                "enum": [
                    "weekly",
                    "four_weekly",
                    "monthly",
                    "quarterly",
                    "annual",
                    None,
                ]
            },
            "expected_period": {
                "oneOf": [
                    _closed_object(
                        {
                            "start_date": {"type": "string", "format": "date"},
                            "end_exclusive": {"type": "string", "format": "date"},
                        },
                        ("start_date", "end_exclusive"),
                    ),
                    {"type": "null"},
                ]
            },
            "valid_from": {"type": ["string", "null"], "format": "date"},
            "target_date": {"type": ["string", "null"], "format": "date"},
            "target_money": {"oneOf": [_money(), {"type": "null"}]},
            "household_share": {
                "type": ["string", "null"],
                "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$",
            },
            "source": {
                "oneOf": [
                    _closed_object(
                        {
                            "adapter_id": {"type": "string", "minLength": 1},
                            "source_id": {"type": "string", "minLength": 1},
                        },
                        ("adapter_id", "source_id"),
                    ),
                    {"type": "null"},
                ]
            },
        },
        ("item_id", "label", "entity_type"),
    )


def _workflow_context_response_schema() -> SchemaObject:
    return _closed_object(
        {
            "action_id": _uuid7(),
            "response_type": {"const": "context_inventory"},
            "section_id": {
                "enum": [
                    "household",
                    "accounts",
                    "cashflow",
                    "assets",
                    "debts",
                    "pensions",
                    "contracts_insurance",
                    "goals",
                ]
            },
            "analysis_scope": _scope(),
            "as_of_date": {"type": "string", "format": "date"},
            "producer": _producer(agent_only=True),
            "coverage": {"enum": ["partial", "complete"]},
            "items": {"type": "array", "items": _workflow_context_item_schema()},
        },
        (
            "action_id",
            "response_type",
            "section_id",
            "analysis_scope",
            "as_of_date",
            "producer",
            "coverage",
            "items",
        ),
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
                        "minItems": 1,
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


def _producer(*, agent_only: bool = False) -> SchemaObject:
    producer_type: SchemaObject = (
        {"const": "agent"} if agent_only else {"enum": ["agent", "rule_module"]}
    )
    return _closed_object(
        {
            "producer_type": producer_type,
            "producer_id": {"type": "string", "minLength": 1},
            "producer_version": {"type": "string", "minLength": 1},
        },
        ("producer_type", "producer_id", "producer_version"),
    )


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
    if command in {"proposal.confirm-batch", "proposal.reject-batch"}:
        properties["batch_id"] = _uuid7()
        required.append("batch_id")
    if command == "proposal.confirm-batch":
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
                "authorization": {"oneOf": [_authorization(), {"type": "null"}]},
            }
        )
        required.extend(["adapter", "records", "authorization"])
    if command == "rule.activate":
        properties.update(
            {
                "rule_package_yaml": {"type": "string", "minLength": 1},
                "authorization": {"oneOf": [_authorization(), {"type": "null"}]},
            }
        )
        required.extend(["rule_package_yaml", "authorization"])
    if command == "context.migrate":
        properties.update(
            {
                "target_package_version": {"type": "string", "minLength": 1},
                "target_context_schema_version": {
                    "type": "string",
                    "minLength": 1,
                },
                "target_module_versions": {
                    "type": "object",
                    "minProperties": 1,
                    "propertyNames": {"type": "string", "minLength": 1},
                    "additionalProperties": {"type": "string", "minLength": 1},
                },
                "authorization": {"oneOf": [_authorization(), {"type": "null"}]},
            }
        )
        required.extend(
            [
                "target_package_version",
                "target_context_schema_version",
                "target_module_versions",
            ]
        )
    if command == "workflow.respond":
        properties["workflow_response"] = _workflow_context_response_schema()
        required.append("workflow_response")
    if command == "context.restore":
        properties["restore_generation"] = _uuid7()
        required.append("restore_generation")
    if command == "context.compact":
        properties.update(
            {
                "retain_latest": {"type": "integer", "minimum": 1, "maximum": 100},
                "restore_generations": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": _uuid7(),
                },
            }
        )
        required.extend(["retain_latest", "restore_generations"])
    if command == "context.privacy_scrub":
        properties["evidence_ids"] = {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": _uuid7(),
        }
        required.append("evidence_ids")
    if command == "proposal.submit":
        properties["proposal"] = _closed_object(
            {
                "proposal_type": {"const": "assertion"},
                "producer": _producer(),
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
                            "knowledge_type": {"enum": ["inferred", "user_provided"]},
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
        properties["workflow_response"] = _closed_object(
            {
                "action_id": _uuid7(),
                "response_type": {"const": "account_balances"},
                "analysis_id": {"const": "analysis.net_worth"},
                "analysis_scope": _scope(),
                "as_of_date": {"type": "string", "format": "date"},
                "producer": _producer(agent_only=True),
                "balances": {
                    "type": "array",
                    "minItems": 1,
                    "items": _closed_object(
                        {
                            "account_ref": _ref(("entity",)),
                            "source": _closed_object(
                                {
                                    "adapter_id": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "source_id": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                },
                                ("adapter_id", "source_id"),
                            ),
                            "money": _money(),
                        },
                        ("account_ref", "source", "money"),
                    ),
                },
            },
            (
                "action_id",
                "response_type",
                "analysis_id",
                "analysis_scope",
                "as_of_date",
                "producer",
                "balances",
            ),
        )
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
    schema: SchemaObject = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_ref(command, "request"),
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }
    if command == "proposal.submit":
        schema["oneOf"] = [
            {"required": ["proposal"], "not": {"required": ["workflow_response"]}},
            {"required": ["workflow_response"], "not": {"required": ["proposal"]}},
        ]
    return schema


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
    elif command == "workspace.init":
        properties["directory"] = {"type": "string", "minLength": 1}
        required.append("directory")
    elif command in {"context.status", "context.verify"}:
        properties["package"] = {"type": "string", "minLength": 1}
        required.append("package")
    elif command == "discover.run":
        properties.update(
            {
                "context_id": _uuid7(),
                "analysis_scope": _scope(),
                "as_of_date": {"type": "string", "format": "date"},
            }
        )
        required.extend(["context_id", "analysis_scope", "as_of_date"])
    elif command in {"rule.validate", "rule.preview"}:
        properties.update(
            {
                "context_id": _uuid7(),
                "expected_generation": _uuid7(),
                "rule_package_yaml": {"type": "string", "minLength": 1},
            }
        )
        required.extend(["context_id", "expected_generation", "rule_package_yaml"])
    elif command == "analyze.run":
        properties.update(
            {
                "analysis_id": {
                    "enum": [
                        "analysis.realized_monthly_cashflow",
                        "analysis.context_inventory",
                        "analysis.normalized_monthly_cashflow",
                        "analysis.net_worth",
                        "analysis.scenario_comparison",
                    ]
                },
                "analysis_contract_version": {"const": "0.1"},
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
        properties.update(
            {
                "context_id": _uuid7(),
                "workflow_contract_version": {"const": "topo.workflow/0.2"},
                "analysis_id": {"const": "analysis.net_worth"},
                "analysis_scope": _scope(),
                "as_of_date": {"type": "string", "format": "date"},
                "include_basis_context": {"type": "boolean"},
                "since_generation": {"oneOf": [_uuid7(), {"type": "null"}]},
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
            }
        )
        required.extend(["context_id", "analysis_id", "analysis_scope", "as_of_date"])
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
    if command == "workspace.init":
        return _closed_object(
            {
                "workspace": {"type": "string", "minLength": 1},
                "package": {"type": "string", "minLength": 1},
                "context_id": deepcopy(uuid7),
                "generation_id": deepcopy(uuid7),
                "person_id": deepcopy(uuid7),
                "household_id": deepcopy(uuid7),
                "context_created": {"type": "boolean"},
                "created_paths": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
                "updated_paths": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
                "unchanged_paths": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
            },
            (
                "workspace",
                "package",
                "context_id",
                "generation_id",
                "person_id",
                "household_id",
                "context_created",
                "created_paths",
                "updated_paths",
                "unchanged_paths",
            ),
        )
    if command == "context.status":
        return _closed_object(
            {
                "context_id": deepcopy(uuid7),
                "generation_id": deepcopy(uuid7),
                "person_id": deepcopy(uuid7),
                "household_id": deepcopy(uuid7),
                "package_version": {"type": "string", "minLength": 1},
                "context_schema_version": {"type": "string", "minLength": 1},
                "modules": {
                    "type": "array",
                    "items": _closed_object(
                        {
                            "module_id": {"type": "string", "minLength": 1},
                            "module_version": {"type": "string", "minLength": 1},
                            "checksum": {
                                "type": "string",
                                "pattern": r"^sha256:[0-9a-f]{64}$",
                            },
                        },
                        ("module_id", "module_version", "checksum"),
                    ),
                },
            },
            (
                "context_id",
                "generation_id",
                "person_id",
                "household_id",
                "package_version",
                "context_schema_version",
                "modules",
            ),
        )
    if command == "context.verify":
        return _closed_object(
            {
                "context_id": deepcopy(uuid7),
                "generation_id": deepcopy(uuid7),
                "generations_verified": {"type": "integer", "minimum": 1},
                "evidence_records_verified": {"type": "integer", "minimum": 0},
            },
            (
                "context_id",
                "generation_id",
                "generations_verified",
                "evidence_records_verified",
            ),
        )
    if command == "context.migrate":
        return {
            "oneOf": [
                _closed_object(
                    {
                        "package_version": {"type": "string"},
                        "context_schema_version": {"type": "string"},
                        "module_versions": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    ("package_version", "context_schema_version", "module_versions"),
                ),
                _authorization_preview_schema(),
            ]
        }
    if command == "context.restore":
        return _closed_object(
            {"restored_from_generation": _uuid7()},
            ("restored_from_generation",),
        )
    if command == "context.compact":
        return _closed_object(
            {
                "retain_latest": {"type": "integer", "minimum": 1, "maximum": 100},
                "restore_generations": {"type": "array", "items": _uuid7()},
                "removed_generations": {"type": "array", "items": _uuid7()},
            },
            ("retain_latest", "restore_generations", "removed_generations"),
        )
    if command == "context.privacy_scrub":
        return _closed_object(
            {
                "scrubbed_evidence_count": {"type": "integer", "minimum": 0},
                "remaining_assertions_marked_unverifiable": {
                    "type": "integer",
                    "minimum": 0,
                },
            },
            ("scrubbed_evidence_count",),
        )
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
                "account_refs": {"type": "array", "items": _ref(("entity",))},
                "transaction_refs": {"type": "array", "items": _ref(("entity",))},
            },
            ("imported", "evidence_refs", "account_refs", "transaction_refs"),
        )
    if command == "discover.run":
        proposal_input = _mutation_input("proposal.submit")
        proposal_properties = cast(SchemaObject, proposal_input["properties"])
        proposal_schema = deepcopy(proposal_properties["proposal"])
        amount_range = _closed_object(
            {"minimum": _money(), "maximum": _money()},
            ("minimum", "maximum"),
        )
        expected_period = _closed_object(
            {
                "start_date": {"type": "string", "format": "date"},
                "end_exclusive": {"type": "string", "format": "date"},
            },
            ("start_date", "end_exclusive"),
        )
        detection = _closed_object(
            {
                "scheme": {"type": "string", "minLength": 1},
                "score": {
                    "type": "string",
                    "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$",
                },
            },
            ("scheme", "score"),
        )
        deviation = _closed_object(
            {
                "transaction_ref": _ref(("entity",)),
                "kind": {"const": "amount_variation"},
                "observed_money": _money(),
            },
            ("transaction_ref", "kind", "observed_money"),
        )
        candidate = _closed_object(
            {
                "candidate_id": {"type": "string", "minLength": 1},
                "proposal_type": {"const": "recurring_cashflow"},
                "frequency": {
                    "enum": [
                        "weekly",
                        "four_weekly",
                        "monthly",
                        "quarterly",
                        "annual",
                    ]
                },
                "direction": {"enum": ["inflow", "outflow"]},
                "expected_period": expected_period,
                "money": {"oneOf": [_money(), {"type": "null"}]},
                "amount_range": {"oneOf": [amount_range, {"type": "null"}]},
                "producer": {"type": "string", "minLength": 1},
                "rule_version": {"type": "string", "minLength": 1},
                "evidence_refs": {"type": "array", "items": _ref(("evidence",))},
                "transaction_refs": {
                    "type": "array",
                    "items": _ref(("entity",)),
                },
                "deviations": {"type": "array", "items": deviation},
                "detection": detection,
                "proposal": proposal_schema,
            },
            (
                "candidate_id",
                "proposal_type",
                "frequency",
                "direction",
                "expected_period",
                "money",
                "amount_range",
                "evidence_refs",
                "transaction_refs",
                "deviations",
                "producer",
                "rule_version",
                "detection",
                "proposal",
            ),
        )
        attention = _closed_object(
            {
                "code": {"const": "INSUFFICIENT_PATTERN_HISTORY"},
                "message_key": {"const": "attention.insufficient_pattern_history"},
                "frequency": {
                    "enum": [
                        "weekly",
                        "four_weekly",
                        "monthly",
                        "quarterly",
                        "annual",
                    ]
                },
                "required_observations": {"type": "integer", "minimum": 2},
                "actual_observations": {"type": "integer", "minimum": 0},
                "related_refs": {"type": "array", "items": _ref()},
            },
            (
                "code",
                "message_key",
                "frequency",
                "required_observations",
                "actual_observations",
                "related_refs",
            ),
        )
        return _closed_object(
            {
                "candidates": {"type": "array", "items": candidate},
                "attention_items": {"type": "array", "items": attention},
            },
            ("candidates", "attention_items"),
        )
    if command == "proposal.submit":
        return {
            "oneOf": [
                _closed_object({"proposal_id": _uuid7()}, ("proposal_id",)),
                _closed_object(
                    {
                        "proposal_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": _uuid7(),
                        },
                        "evidence_id": _uuid7(),
                    },
                    ("proposal_ids", "evidence_id"),
                ),
            ]
        }
    if command == "workflow.respond":
        return _closed_object(
            {
                "batch_id": _uuid7(),
                "proposal_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": _uuid7(),
                },
                "evidence_id": _uuid7(),
            },
            ("batch_id", "proposal_ids", "evidence_id"),
        )
    if command == "proposal.confirm":
        return _closed_object(
            {
                "proposal_id": _uuid7(),
                "assertion_id": _uuid7(),
                "evidence_id": _uuid7(),
                "decision_ref": {
                    "type": "string",
                    "pattern": f"^decision:{UUID7_PATTERN[1:-1]}$",
                },
            },
            ("proposal_id", "assertion_id", "evidence_id", "decision_ref"),
        )
    if command == "proposal.correct":
        return _closed_object(
            {
                "proposal_id": _uuid7(),
                "assertion_id": _uuid7(),
                "evidence_id": _uuid7(),
                "decision_ref": {
                    "type": "string",
                    "pattern": f"^decision:{UUID7_PATTERN[1:-1]}$",
                },
            },
            ("proposal_id", "assertion_id", "evidence_id", "decision_ref"),
        )
    if command == "proposal.reject":
        return _closed_object(
            {
                "proposal_id": _uuid7(),
                "decision_ref": {
                    "type": "string",
                    "pattern": f"^decision:{UUID7_PATTERN[1:-1]}$",
                },
            },
            ("proposal_id", "decision_ref"),
        )
    if command == "proposal.confirm-batch":
        return {
            "oneOf": [
                _authorization_preview_schema(),
                _closed_object(
                    {
                        "batch_id": _uuid7(),
                        "proposal_ids": {"type": "array", "items": _uuid7()},
                        "entity_ids": {"type": "array", "items": _uuid7()},
                        "assertion_ids": {"type": "array", "items": _uuid7()},
                        "evidence_id": _uuid7(),
                        "decision_ref": {
                            "type": "string",
                            "pattern": f"^decision:{UUID7_PATTERN[1:-1]}$",
                        },
                    },
                    (
                        "batch_id",
                        "proposal_ids",
                        "entity_ids",
                        "assertion_ids",
                        "evidence_id",
                        "decision_ref",
                    ),
                ),
            ]
        }
    if command == "proposal.reject-batch":
        return _closed_object(
            {
                "batch_id": _uuid7(),
                "proposal_ids": {"type": "array", "items": _uuid7()},
            },
            ("batch_id", "proposal_ids"),
        )
    if command in {"rule.validate", "rule.preview"}:
        validation_properties: SchemaObject = {
            "valid": {"const": True},
            "validated_generation": _uuid7(),
            "package_id": {"type": "string", "minLength": 1},
            "package_version": {"type": "string", "minLength": 1},
            "module_id": {"type": "string", "minLength": 1},
            "checksum": {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}$"},
            "rule_count": {"type": "integer", "minimum": 1},
            "rule_types": {
                "type": "array",
                "items": {
                    "enum": [
                        "recognition",
                        "validation",
                        "completeness",
                        "question_priority",
                    ]
                },
            },
        }
        required = tuple(validation_properties)
        if command == "rule.preview":
            effect = _closed_object(
                {
                    "action": {"const": "replace_rule_package"},
                    "module_id": {"type": "string", "minLength": 1},
                    "package_id": {"type": "string", "minLength": 1},
                    "package_version": {"type": "string", "minLength": 1},
                },
                ("action", "module_id", "package_id", "package_version"),
            )
            condition = _closed_object(
                {
                    "predicate": {"type": "string", "minLength": 1},
                    "args": {"type": "object"},
                    "result": {"type": "boolean"},
                    "reason": {"type": "string", "minLength": 1},
                },
                ("predicate", "args", "result", "reason"),
            )
            evaluation = _closed_object(
                {
                    "package_id": {"type": "string", "minLength": 1},
                    "package_version": {"type": "string", "minLength": 1},
                    "rule_id": {"type": "string", "minLength": 1},
                    "rule_version": {"type": "string", "minLength": 1},
                    "rule_type": {
                        "enum": [
                            "recognition",
                            "validation",
                            "completeness",
                            "question_priority",
                        ]
                    },
                    "input_view": {"type": "string", "minLength": 1},
                    "conditions": {"type": "array", "items": condition},
                    "matched": {"type": "boolean"},
                    "outcome": {"type": "string", "minLength": 1},
                    "explain_ref": _ref(("rule_outcome",)),
                },
                (
                    "package_id",
                    "package_version",
                    "rule_id",
                    "rule_version",
                    "rule_type",
                    "input_view",
                    "conditions",
                    "matched",
                    "outcome",
                    "explain_ref",
                ),
            )
            validation_properties.update(
                {
                    "preview_ref": {
                        "type": "string",
                        "pattern": r"^preview:sha256:[0-9a-f]{64}$",
                    },
                    "effects": {"type": "array", "items": effect},
                    "evaluations": {"type": "array", "items": evaluation},
                }
            )
            required = tuple(validation_properties)
        return _closed_object(validation_properties, required)
    if command == "rule.activate":
        return _closed_object(
            {
                "package_id": {"type": "string", "minLength": 1},
                "package_version": {"type": "string", "minLength": 1},
                "module_id": {"type": "string", "minLength": 1},
                "checksum": {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}$"},
                "rule_count": {"type": "integer", "minimum": 1},
                "preview_ref": {
                    "type": "string",
                    "pattern": r"^preview:sha256:[0-9a-f]{64}$",
                },
                "effects": {"type": "array"},
            },
            ("package_id", "package_version", "module_id", "checksum", "rule_count"),
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
                "knowledge_types": {
                    "type": "array",
                    "items": {
                        "enum": [
                            "observed",
                            "user_provided",
                            "inferred",
                            "calculated",
                            "assumed",
                            "projected",
                        ]
                    },
                },
                "verification_statuses": {
                    "type": "array",
                    "items": {
                        "enum": [
                            "proposed",
                            "confirmed",
                            "rejected",
                            "superseded",
                            "unverifiable",
                        ]
                    },
                },
                "valid_times": {"type": "array", "items": {"type": "object"}},
                "recorded_times": {
                    "type": "array",
                    "items": {"type": "string", "format": "date-time"},
                },
                "required_time_coverage": _closed_object(
                    {"as_of_date": {"type": "string", "format": "date"}},
                    ("as_of_date",),
                ),
                "allocation_state": {"enum": ["allocated", "unallocated", "unknown"]},
                "next_question": {"type": ["string", "null"]},
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
                "factor": _closed_object(
                    {
                        "multiply_by": {
                            "type": "string",
                            "pattern": r"^[1-9][0-9]*$",
                        },
                        "divide_by": {
                            "type": "string",
                            "pattern": r"^[1-9][0-9]*$",
                        },
                    },
                    ("multiply_by", "divide_by"),
                ),
            },
            ("step_id", "operation", "inputs", "unrounded_result"),
        )
        component = _closed_object(
            {
                "component_id": {"type": "string", "minLength": 1},
                "status": {"enum": ["complete", "provisional", "unavailable"]},
                "value": _money(),
                "minimum_value": _money(),
                "maximum_value": _money(),
                "expected_value": _money(),
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
                "breakdown": {
                    "type": "array",
                    "items": _closed_object(
                        {
                            "category": {"type": "string", "minLength": 1},
                            "value": _money(),
                            "transaction_refs": {
                                "type": "array",
                                "items": _ref(("entity",)),
                            },
                        },
                        ("category", "value", "transaction_refs"),
                    ),
                },
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
        metadata = {
            "analysis_id": {"type": "string", "minLength": 1},
            "analysis_contract_version": {"type": "string", "minLength": 1},
            "analysis_scope": _scope(),
            "as_of_date": {"type": "string", "format": "date"},
            "period": {"type": ["object", "null"]},
            "used_generation": _uuid7(),
            "result_id": _uuid7(),
        }
        metadata_required = (
            "analysis_id",
            "analysis_contract_version",
            "analysis_scope",
            "as_of_date",
            "period",
            "used_generation",
            "result_id",
        )
        domain_count = _closed_object(
            {
                "domain_id": {"type": "string", "minLength": 1},
                "count": {"type": "integer", "minimum": 0},
                "assertion_refs": {"type": "array", "items": _ref(("assertion",))},
            },
            ("domain_id", "count", "assertion_refs"),
        )
        inventory_step = _closed_object(
            {
                "step_id": {"type": "string", "minLength": 1},
                "operation": {"const": "count_assertions"},
                "input_assertion_refs": {
                    "type": "array",
                    "items": _ref(("assertion",)),
                },
                "result_count": {"type": "integer", "minimum": 0},
            },
            ("step_id", "operation", "input_assertion_refs", "result_count"),
        )
        ordinary_result = _closed_object(
            {
                **metadata,
                "components": {"type": "array", "items": component},
                "domain_counts": {"type": "array", "items": domain_count},
                "inventory_steps": {"type": "array", "items": inventory_step},
            },
            (*metadata_required, "components"),
        )
        scenario_view = _closed_object(
            {
                "normalized_monthly_cashflow": component,
                "one_off_cashflow": component,
                "net_worth": component,
            },
            ("normalized_monthly_cashflow", "one_off_cashflow", "net_worth"),
        )
        scenario_result = _closed_object(
            {
                **metadata,
                "scenario_id": _uuid7(),
                "knowledge_type": {"const": "projected"},
                "baseline": scenario_view,
                "scenario": scenario_view,
                "delta": scenario_view,
            },
            (
                *metadata_required,
                "scenario_id",
                "knowledge_type",
                "baseline",
                "scenario",
                "delta",
            ),
        )
        return {"oneOf": [ordinary_result, scenario_result]}
    if command == "explain":
        return _closed_object(
            {
                "ref": {"type": "string", "minLength": 1},
                "ref_type": {
                    "enum": [
                        "proposal",
                        "decision",
                        "diagnostic",
                        "rule_outcome",
                        "analysis_component",
                    ]
                },
                "meaning": {"type": "string"},
                "generation_id": _uuid7(),
                "contract_version": {"const": CONTRACT_VERSION},
                "record_checksum": {
                    "type": "string",
                    "pattern": r"^sha256:[0-9a-f]{64}$",
                },
                "analysis_id": {"type": "string"},
                "analysis_contract_version": {"type": "string"},
                "module_versions": {
                    "type": "array",
                    "items": _closed_object(
                        {
                            "module_id": {"type": "string", "minLength": 1},
                            "module_version": {"type": "string", "minLength": 1},
                        },
                        ("module_id", "module_version"),
                    ),
                },
                "assertion_refs": {"type": "array", "items": _ref(("assertion",))},
                "evidence_refs": {"type": "array", "items": _ref(("evidence",))},
                "requirements": {"type": "array", "items": {"type": "object"}},
                "assumptions": {"type": "array", "items": {"type": "object"}},
                "calculation_steps": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "intermediate_results": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "rounding": {"type": ["object", "null"]},
                "proposal": {"type": "object"},
                "decision": {"type": ["object", "null"]},
                "diagnostic": {"type": "object"},
                "rule_trace": {"type": ["object", "null"]},
            },
            (
                "ref",
                "ref_type",
                "meaning",
                "generation_id",
                "contract_version",
                "module_versions",
                "assertion_refs",
                "evidence_refs",
                "requirements",
                "assumptions",
                "calculation_steps",
                "intermediate_results",
                "rounding",
                "decision",
                "rule_trace",
            ),
        )
    if command == "workflow.next":
        return _closed_object(
            {
                "workflow_contract_version": {"const": "topo.workflow/0.2"},
                "scope": _scope(),
                "as_of_date": {"type": "string", "format": "date"},
                "used_generation": _uuid7(),
                "change_summary": {"type": "object"},
                "context_sections": {"type": "array", "items": {"type": "object"}},
                "analysis_results": {"type": "array", "items": {"type": "object"}},
                "next_action": {"oneOf": [_next_action_schema(), {"type": "null"}]},
                "actions": {
                    "type": "array",
                    "maxItems": 1,
                    "items": _next_action_schema(),
                },
            },
            (
                "workflow_contract_version",
                "scope",
                "as_of_date",
                "used_generation",
                "change_summary",
                "context_sections",
                "analysis_results",
                "next_action",
                "actions",
            ),
        )
    raise KeyError(command)


def _authorization_preview_schema() -> SchemaObject:
    return _closed_object(
        {
            "preview_ref": {
                "type": "string",
                "pattern": r"^preview:sha256:[0-9a-f]{64}$",
            },
            "batch_id": _uuid7(),
            "effects": {"type": "array", "minItems": 1, "items": {"type": "object"}},
        },
        ("preview_ref", "effects"),
    )


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
            "explain_ref": _ref(("diagnostic",)),
        },
    }


def _next_action_schema() -> SchemaObject:
    common = {
        "action_id": _uuid7(),
        "action_type": {"type": "string", "minLength": 1},
        "priority": {"enum": ["blocking", "required", "helpful", "optional"]},
        "reason_code": {"type": "string", "minLength": 1},
        "affected_component": {"type": ["string", "null"]},
        "related_refs": {"type": "array", "items": _ref()},
        "command": {"enum": list(COMMANDS)},
        "request_template": {"type": "object"},
        "input_schema_ref": {"type": "string"},
        "requires_user_input": {"type": "boolean"},
        "requires_authorization": {"type": "boolean"},
    }
    required = (
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
    )
    legacy = _closed_object(
        {
            **common,
            "action_contract_version": {"const": "topo.workflow-action/0.1"},
        },
        required,
    )
    executable = _closed_object(
        {
            **common,
            "action_contract_version": {"const": "topo.workflow-action/0.2"},
            "question": {"type": "string", "minLength": 1},
            "available_context": {
                "type": "object",
                "additionalProperties": False,
                "required": ["accounts"],
                "properties": {
                    "accounts": {
                        "type": "array",
                        "minItems": 1,
                        "items": _closed_object(
                            {
                                "account_ref": _ref(("entity",)),
                                "source": _closed_object(
                                    {
                                        "adapter_id": {
                                            "type": "string",
                                            "minLength": 1,
                                        },
                                        "source_id": {
                                            "type": "string",
                                            "minLength": 1,
                                        },
                                    },
                                    ("adapter_id", "source_id"),
                                ),
                            },
                            ("account_ref", "source"),
                        ),
                    }
                },
            },
            "user_input_schema": {"type": "object"},
            "user_input_paths": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
            "agent_input_paths": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
        },
        (
            *required,
            "question",
            "available_context",
            "user_input_schema",
            "user_input_paths",
            "agent_input_paths",
        ),
    )
    proactive = _closed_object(
        {
            **common,
            "action_contract_version": {"const": "topo.workflow-action/0.3"},
            "question": {"type": "string", "minLength": 1},
            "available_context": {"type": "object"},
            "user_input_schema": {"type": "object"},
            "user_input_paths": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
            "agent_input_paths": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
        },
        (
            *required,
            "question",
            "available_context",
            "user_input_schema",
            "user_input_paths",
            "agent_input_paths",
        ),
    )
    return {"oneOf": [legacy, executable, proactive]}


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
