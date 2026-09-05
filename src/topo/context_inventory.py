from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from typing import cast

from pydantic import JsonValue

from topo.canonical_validation import ValidatedPackage
from topo.identifiers import source_account_id
from topo.models import (
    AssertionRecord,
    ContextInventoryAnalyzeRunRequest,
    JsonObject,
    NetWorthAnalyzeRunRequest,
    ProposalRecord,
    SourceRecordEvidenceRecord,
    WorkflowNextRequest,
)
from topo.net_worth import analyze_net_worth

_COUNTED_DOMAINS = (
    "domain.accounts",
    "domain.assets",
    "domain.cashflow",
    "domain.debts",
)

_BASIS_SECTIONS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("household", "domain.parties", ("person",), "domain.parties/inventory_coverage"),
    ("accounts", "domain.accounts", ("account",), "domain.accounts/inventory_coverage"),
    ("cashflow", "domain.cashflow", (), "domain.cashflow/inventory_coverage"),
    ("assets", "domain.assets", ("asset",), "domain.assets/inventory_coverage"),
    ("debts", "domain.debts", ("debt",), "domain.debts/inventory_coverage"),
    (
        "pensions",
        "domain.pensions",
        ("pension_entitlement",),
        "domain.pensions/inventory_coverage",
    ),
    (
        "contracts_insurance",
        "domain.contracts",
        ("contract",),
        "domain.contracts/inventory_coverage",
    ),
    ("goals", "domain.goals", ("goal",), "domain.goals/inventory_coverage"),
)

_SECTION_QUESTIONS = {
    "household": "Welke personen horen bij dit huishouden, en is deze lijst compleet?",
    "accounts": "Welke betaal-, spaar- en beleggingsrekeningen horen bij dit huishouden, en is deze lijst compleet?",
    "cashflow": "Welke terugkerende inkomsten en uitgaven heeft dit huishouden, en is deze lijst compleet?",
    "assets": "Welke bezittingen horen bij dit huishouden, wat zijn hun actuele waarden, en is deze lijst compleet?",
    "debts": "Welke schulden horen bij dit huishouden, wat zijn hun actuele standen, en is deze lijst compleet?",
    "pensions": "Welke pensioenaanspraken zijn er, welke waarde is bekend, en is deze lijst compleet?",
    "contracts_insurance": "Welke relevante contracten en verzekeringen zijn er, en is deze lijst compleet?",
    "goals": "Welke financiële doelen zijn er, en is deze lijst compleet?",
}


@dataclass(frozen=True)
class _Requirement:
    name: str
    predicates: tuple[str, ...]


_NET_WORTH_REQUIREMENTS = (
    _Requirement("account_balances", ("domain.accounts/balance",)),
    _Requirement(
        "asset_valuations",
        ("domain.assets/value", "jurisdiction.nl/valuation/woz"),
    ),
    _Requirement("debt_balances", ("domain.debts/balance",)),
)


@dataclass(frozen=True)
class _NextRequirementDecision:
    requirement: str
    state: str
    question: str
    reason_code: str
    priority: str
    proposal_type: str


def _stable_uuid7(*parts: str) -> str:
    digest = bytearray(hashlib.sha256("\x1f".join(parts).encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x70
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _known_source_accounts(package: ValidatedPackage) -> list[JsonObject]:
    account_ids = {
        entity.id
        for entity in package.entities.records
        if entity.entity_type == "account"
    }
    accounts: dict[str, JsonObject] = {}
    for evidence in package.evidence.records:
        if not isinstance(evidence, SourceRecordEvidenceRecord):
            continue
        account_id = source_account_id(
            evidence.source.adapter_id, evidence.source.source_id
        )
        if account_id not in account_ids:
            continue
        accounts[account_id] = {
            "account_ref": {"ref_type": "entity", "id": account_id},
            "source": {
                "adapter_id": evidence.source.adapter_id,
                "source_id": evidence.source.source_id,
            },
        }
    return [accounts[account_id] for account_id in sorted(accounts)]


def _account_balance_action(
    package: ValidatedPackage,
    request: WorkflowNextRequest,
    decision: _NextRequirementDecision,
    *,
    component_id: str,
    accounts: list[JsonObject],
) -> JsonObject:
    action_id = _stable_uuid7(
        package.manifest.generation_id,
        request.analysis_id,
        request.analysis_scope.entity_id,
        request.as_of_date.isoformat(),
        decision.reason_code,
    )
    balance_templates = [
        {
            **account,
            "money": {"amount": None, "currency": None},
        }
        for account in accounts
    ]
    user_input_paths = [
        path
        for index in range(len(accounts))
        for path in (
            f"/workflow_response/balances/{index}/money/amount",
            f"/workflow_response/balances/{index}/money/currency",
        )
    ]
    money_input_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["amount", "currency"],
        "properties": {
            "amount": {
                "type": "string",
                "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$",
            },
            "currency": {"type": "string", "pattern": r"^[A-Z]{3}$"},
        },
    }
    user_balance_schemas = [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["source", "money"],
            "properties": {
                "source": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["adapter_id", "source_id"],
                    "properties": {
                        "adapter_id": {
                            "const": cast(JsonObject, account["source"])["adapter_id"]
                        },
                        "source_id": {
                            "const": cast(JsonObject, account["source"])["source_id"]
                        },
                    },
                },
                "money": money_input_schema,
            },
        }
        for account in accounts
    ]
    request_template = cast(
        JsonObject,
        {
            "contract_version": request.contract_version,
            "operation_id": action_id,
            "context_id": request.context_id,
            "expected_generation": package.manifest.generation_id,
            "actor": {"actor_type": "agent", "actor_id": None},
            "reason": f"Answer workflow action {action_id}",
            "workflow_response": {
                "action_id": action_id,
                "response_type": "account_balances",
                "analysis_id": request.analysis_id,
                "analysis_scope": request.analysis_scope.model_dump(mode="json"),
                "as_of_date": request.as_of_date.isoformat(),
                "producer": {
                    "producer_type": "agent",
                    "producer_id": None,
                    "producer_version": None,
                },
                "balances": balance_templates,
            },
        },
    )
    return cast(
        JsonObject,
        {
            "action_id": action_id,
            "action_type": "answer_question",
            "action_contract_version": "topo.workflow-action/0.2",
            "priority": decision.priority,
            "reason_code": decision.reason_code,
            "affected_component": component_id,
            "related_refs": [account["account_ref"] for account in accounts],
            "command": "proposal.submit",
            "question": decision.question,
            "available_context": {"accounts": accounts},
            "request_template": request_template,
            "user_input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["balances"],
                "properties": {
                    "balances": {
                        "type": "array",
                        "minItems": len(accounts),
                        "maxItems": len(accounts),
                        "items": {"oneOf": user_balance_schemas},
                        "allOf": [
                            {
                                "contains": account_schema,
                                "minContains": 1,
                                "maxContains": 1,
                            }
                            for account_schema in user_balance_schemas
                        ],
                    }
                },
            },
            "user_input_paths": user_input_paths,
            "agent_input_paths": [
                "/actor/actor_id",
                "/workflow_response/producer/producer_id",
                "/workflow_response/producer/producer_version",
            ],
            "input_schema_ref": "topo://schema/proposal-submit-request/0.2",
            "requires_user_input": True,
            "requires_authorization": False,
        },
    )


def _component_result(
    package: ValidatedPackage,
    request: ContextInventoryAnalyzeRunRequest,
    *,
    component_id: str,
    status: str,
    requirements: list[JsonObject],
    next_question: str | None,
) -> JsonObject:
    return cast(
        JsonObject,
        {
            "component_id": component_id,
            "status": status,
            "used_assertion_refs": [],
            "used_evidence_refs": [],
            "assumptions": [],
            "calculation_steps": [],
            "rounding": {"mode": "none", "presented_decimals": 0},
            "requirements": requirements,
            "blockers": [],
            "warnings": [],
            "next_question": next_question,
            "explain_ref": {
                "ref_type": "analysis_component",
                "id": _stable_uuid7(
                    package.manifest.generation_id,
                    request.analysis_id,
                    component_id,
                    request.as_of_date.isoformat(),
                ),
            },
        },
    )


def _active_on(assertion: AssertionRecord, as_of_date: date) -> bool:
    return assertion.valid_time.start <= as_of_date and (
        assertion.valid_time.end_exclusive is None
        or as_of_date < assertion.valid_time.end_exclusive
    )


def _assertion_value(assertion: AssertionRecord) -> str:
    value = assertion.object_ref or assertion.object_value
    if value is None:
        raise ValueError("assertion has no object")
    return json.dumps(value.model_dump(mode="json"), sort_keys=True)


def _is_allocated_to_scope(
    package: ValidatedPackage,
    assertion: AssertionRecord,
    request: ContextInventoryAnalyzeRunRequest,
    requirement: _Requirement,
) -> bool:
    if request.analysis_scope.scope_type == "person":
        relation_predicate = _scope_relation_predicate(requirement)
        return any(
            relation.predicate == relation_predicate
            and relation.subject_ref.id == assertion.subject_ref.id
            and relation.object_ref is not None
            and relation.object_ref.id == request.analysis_scope.entity_id
            and _active_on(relation, request.as_of_date)
            for relation in package.assertions.records
        )
    if assertion.subject_ref.id == request.analysis_scope.entity_id:
        return True
    return any(
        allocation.predicate == "domain.parties/household_allocation"
        and allocation.subject_ref.id == assertion.subject_ref.id
        and allocation.object_ref is not None
        and allocation.object_ref.id == request.analysis_scope.entity_id
        and _active_on(allocation, request.as_of_date)
        for allocation in package.assertions.records
    )


def _scope_relation_predicate(requirement: _Requirement) -> str:
    return {
        "account_balances": "domain.parties/account_holder",
        "asset_valuations": "domain.parties/ownership",
        "debt_balances": "domain.parties/debtor",
    }[requirement.name]


def _scope_subject_ids(
    package: ValidatedPackage,
    request: ContextInventoryAnalyzeRunRequest,
    requirement: _Requirement,
) -> set[str]:
    scope_id = request.analysis_scope.entity_id
    relation_predicate = _scope_relation_predicate(requirement)
    if request.analysis_scope.scope_type == "person":
        return {
            assertion.subject_ref.id
            for assertion in package.assertions.records
            if assertion.predicate == relation_predicate
            and assertion.object_ref is not None
            and assertion.object_ref.id == scope_id
            and _active_on(assertion, request.as_of_date)
        }
    household_members = {
        assertion.subject_ref.id
        for assertion in package.assertions.records
        if assertion.predicate == "domain.parties/household_membership"
        and assertion.object_ref is not None
        and assertion.object_ref.id == scope_id
        and _active_on(assertion, request.as_of_date)
    }
    explicitly_allocated = {
        assertion.subject_ref.id
        for assertion in package.assertions.records
        if assertion.predicate == "domain.parties/household_allocation"
        and assertion.object_ref is not None
        and assertion.object_ref.id == scope_id
        and _active_on(assertion, request.as_of_date)
    }
    member_related = {
        assertion.subject_ref.id
        for assertion in package.assertions.records
        if assertion.predicate == relation_predicate
        and assertion.object_ref is not None
        and assertion.object_ref.id in household_members
        and _active_on(assertion, request.as_of_date)
    }
    return {scope_id} | explicitly_allocated | member_related


def _requirement_state(
    package: ValidatedPackage,
    request: ContextInventoryAnalyzeRunRequest,
    requirement: _Requirement,
) -> tuple[str, tuple[AssertionRecord, ...]]:
    assertions = tuple(
        assertion
        for assertion in package.assertions.records
        if assertion.predicate in requirement.predicates
        and _active_on(assertion, request.as_of_date)
        and assertion.subject_ref.id
        in _scope_subject_ids(package, request, requirement)
    )
    if not assertions:
        coverage_predicate = {
            "account_balances": "domain.accounts/inventory_coverage",
            "asset_valuations": "domain.assets/inventory_coverage",
            "debt_balances": "domain.debts/inventory_coverage",
        }.get(requirement.name)
        explicitly_complete = any(
            assertion.subject_ref.id == request.analysis_scope.entity_id
            and assertion.predicate == coverage_predicate
            and assertion.object_value is not None
            and assertion.object_value.value_type == "inventory_coverage"
            and isinstance(assertion.object_value.value, dict)
            and assertion.object_value.value.get("coverage") == "complete"
            and assertion.object_value.value.get("as_of_date")
            == request.as_of_date.isoformat()
            and _active_on(assertion, request.as_of_date)
            for assertion in package.assertions.records
        )
        if explicitly_complete:
            return "present", assertions
        return "missing", assertions
    values_by_subject: dict[str, set[str]] = {}
    for assertion in assertions:
        values_by_subject.setdefault(assertion.subject_ref.id, set()).add(
            _assertion_value(assertion)
        )
    if any(len(values) > 1 for values in values_by_subject.values()):
        return "conflicting", assertions
    if any(
        isinstance(
            currentness := assertion.module_data.get("analysis_currentness"), dict
        )
        and currentness.get("analysis.net_worth") == "insufficiently_current"
        for assertion in assertions
    ):
        return "insufficiently_current", assertions
    if not all(
        _is_allocated_to_scope(package, assertion, request, requirement)
        for assertion in assertions
    ):
        return "unallocated", assertions
    return "present", assertions


def _matching_proposals(
    package: ValidatedPackage,
    request: ContextInventoryAnalyzeRunRequest,
    requirement: _Requirement,
) -> tuple[ProposalRecord, ...]:
    subject_ids = _scope_subject_ids(package, request, requirement)
    return tuple(
        proposal
        for proposal in package.proposals.records
        if proposal.proposal_type == "assertion"
        and proposal.proposed_assertion is not None
        and proposal.proposed_assertion.predicate in requirement.predicates
        and proposal.proposed_assertion.subject_ref.id in subject_ids
        and proposal.proposed_assertion.valid_time.start <= request.as_of_date
        and (
            proposal.proposed_assertion.valid_time.end_exclusive is None
            or request.as_of_date < proposal.proposed_assertion.valid_time.end_exclusive
        )
    )


def _net_worth_requirements(
    package: ValidatedPackage, request: ContextInventoryAnalyzeRunRequest
) -> tuple[list[JsonObject], tuple[AssertionRecord, ...]]:
    impacts = {
        "present": "no_impact",
        "missing": "blocks_component",
        "conflicting": "blocks_component",
        "insufficiently_current": "makes_component_provisional",
        "unallocated": "makes_component_provisional",
    }
    requirement_results: list[JsonObject] = []
    assertions: list[AssertionRecord] = []
    for requirement in _NET_WORTH_REQUIREMENTS:
        state, matched = _requirement_state(package, request, requirement)
        proposals = _matching_proposals(package, request, requirement)
        proposal_statuses = {
            "open": "proposed",
            "confirmed": "confirmed",
            "corrected": "superseded",
            "rejected": "rejected",
            "superseded": "superseded",
        }
        next_question = _requirement_question(
            requirement.name, state, request.as_of_date.isoformat()
        )
        requirement_results.append(
            cast(
                JsonObject,
                {
                    "requirement": requirement.name,
                    "state": state,
                    "impact": impacts[state],
                    "knowledge_types": sorted(
                        {assertion.knowledge_type for assertion in matched}
                        | {
                            proposal.proposed_assertion.knowledge_type
                            for proposal in proposals
                            if proposal.proposed_assertion is not None
                        }
                    ),
                    "verification_statuses": sorted(
                        {assertion.verification_status for assertion in matched}
                        | {proposal_statuses[proposal.status] for proposal in proposals}
                    ),
                    "valid_times": [
                        assertion.valid_time.model_dump(mode="json")
                        for assertion in matched
                    ]
                    + [
                        proposal.proposed_assertion.valid_time.model_dump(mode="json")
                        for proposal in proposals
                        if proposal.proposed_assertion is not None
                    ],
                    "recorded_times": [
                        assertion.recorded_at.isoformat() for assertion in matched
                    ]
                    + [proposal.created_at.isoformat() for proposal in proposals],
                    "required_time_coverage": {
                        "as_of_date": request.as_of_date.isoformat()
                    },
                    "allocation_state": (
                        "unknown"
                        if state == "missing"
                        else "unallocated"
                        if state == "unallocated"
                        else "allocated"
                    ),
                    "next_question": next_question,
                },
            )
        )
        assertions.extend(matched)
    return requirement_results, tuple(assertions)


def _requirement_question(requirement: str, state: str, as_of_date: str) -> str | None:
    if state == "present":
        return None
    questions = {
        ("account_balances", "conflicting"): (
            f"Which account balance is correct for this scope as of {as_of_date}?"
        ),
        ("account_balances", "unallocated"): (
            "How should the known account balance be allocated to this household?"
        ),
        ("account_balances", "insufficiently_current"): (
            f"What are the current account balances as of {as_of_date}?"
        ),
        ("asset_valuations", "conflicting"): (
            f"Which asset valuation is correct for this scope as of {as_of_date}?"
        ),
        ("asset_valuations", "unallocated"): (
            "How should the known asset valuation be allocated to this household?"
        ),
        ("asset_valuations", "insufficiently_current"): (
            f"What are the current asset valuations as of {as_of_date}?"
        ),
        ("debt_balances", "conflicting"): (
            f"Which debt balance is correct for this scope as of {as_of_date}?"
        ),
        ("debt_balances", "unallocated"): (
            "How should the known debt balance be allocated to this household?"
        ),
        ("debt_balances", "insufficiently_current"): (
            f"What are the current debt balances as of {as_of_date}?"
        ),
    }
    if (question := questions.get((requirement, state))) is not None:
        return question
    if requirement == "account_balances":
        return f"Which accounts and balances belong to this scope as of {as_of_date}?"
    if requirement == "asset_valuations":
        return f"Which assets and valuations belong to this scope as of {as_of_date}?"
    return f"What debts and balances belong to this scope as of {as_of_date}?"


def _next_requirement_decision(
    requirements: list[JsonObject], as_of_date: str
) -> _NextRequirementDecision | None:
    by_name = {
        str(requirement["requirement"]): requirement for requirement in requirements
    }
    reason_codes = {
        ("account_balances", "missing"): "NET_WORTH_NEEDS_ACCOUNT_BALANCE",
        ("account_balances", "conflicting"): "NET_WORTH_CONFLICTING_ACCOUNT_BALANCE",
        ("account_balances", "unallocated"): "NET_WORTH_NEEDS_HOUSEHOLD_ALLOCATION",
        (
            "account_balances",
            "insufficiently_current",
        ): "NET_WORTH_NEEDS_CURRENT_ACCOUNT_BALANCE",
        ("asset_valuations", "missing"): "NET_WORTH_NEEDS_ASSET_VALUATION",
        ("asset_valuations", "conflicting"): "NET_WORTH_CONFLICTING_ASSET_VALUATION",
        ("asset_valuations", "unallocated"): "NET_WORTH_NEEDS_HOUSEHOLD_ALLOCATION",
        (
            "asset_valuations",
            "insufficiently_current",
        ): "NET_WORTH_NEEDS_CURRENT_ASSET_VALUATION",
        ("debt_balances", "missing"): "NET_WORTH_NEEDS_DEBT_BALANCE",
        ("debt_balances", "conflicting"): "NET_WORTH_CONFLICTING_DEBT_BALANCE",
        ("debt_balances", "unallocated"): "NET_WORTH_NEEDS_HOUSEHOLD_ALLOCATION",
        (
            "debt_balances",
            "insufficiently_current",
        ): "NET_WORTH_NEEDS_CURRENT_DEBT_BALANCE",
    }
    proposal_types = {
        "account_balances": "account_balance",
        "asset_valuations": "asset_valuation",
        "debt_balances": "debt_balance",
    }
    for state in ("conflicting", "missing", "unallocated", "insufficiently_current"):
        for requirement_name in (
            "account_balances",
            "asset_valuations",
            "debt_balances",
        ):
            requirement = by_name[requirement_name]
            if requirement["state"] != state:
                continue
            question = _requirement_question(requirement_name, state, as_of_date)
            if question is None:
                continue
            return _NextRequirementDecision(
                requirement=requirement_name,
                state=state,
                question=question,
                reason_code=reason_codes[(requirement_name, state)],
                priority="blocking" if state == "conflicting" else "required",
                proposal_type=(
                    "household_allocation"
                    if state == "unallocated"
                    else proposal_types[requirement_name]
                ),
            )
    return None


def inventory_context(
    package: ValidatedPackage, request: ContextInventoryAnalyzeRunRequest
) -> JsonObject:
    if request.context_id != package.manifest.context_id:
        raise ValueError("context_id does not match the package")

    scope = next(
        (
            entity
            for entity in package.entities.records
            if entity.id == request.analysis_scope.entity_id
        ),
        None,
    )
    if scope is None or scope.entity_type != request.analysis_scope.scope_type:
        raise ValueError("analysis_scope does not resolve to the requested entity type")

    as_of_date = request.as_of_date.isoformat()
    requirements, used_assertions = _net_worth_requirements(package, request)
    states = {str(requirement["state"]) for requirement in requirements}
    if states & {"missing", "conflicting"}:
        net_worth_status = "unavailable"
    elif states & {"insufficiently_current", "unallocated"}:
        net_worth_status = "provisional"
    else:
        net_worth_status = "complete"
    next_decision = _next_requirement_decision(requirements, as_of_date)
    components = [
        _component_result(
            package,
            request,
            component_id="analysis.context_inventory/inventory",
            status="complete",
            requirements=[],
            next_question=None,
        ),
        _component_result(
            package,
            request,
            component_id="analysis.net_worth/total",
            status=net_worth_status,
            requirements=requirements,
            next_question=next_decision.question if next_decision is not None else None,
        ),
    ]
    components[1]["used_assertion_refs"] = [
        {"ref_type": "assertion", "id": assertion.id} for assertion in used_assertions
    ]
    components[1]["used_evidence_refs"] = [
        {"ref_type": "evidence", "id": ref.id}
        for assertion in used_assertions
        for ref in assertion.provenance
        if ref.ref_type == "evidence"
    ]
    components[0]["used_assertion_refs"] = [
        {"ref_type": "assertion", "id": assertion.id}
        for assertion in package.assertions.records
    ]
    components[0]["used_evidence_refs"] = [
        {"ref_type": "evidence", "id": ref.id}
        for assertion in package.assertions.records
        for ref in assertion.provenance
        if ref.ref_type == "evidence"
    ]
    domain_counts = [
        {
            "domain_id": domain_id,
            "count": sum(
                assertion.predicate.startswith(f"{domain_id}/")
                for assertion in package.assertions.records
            ),
            "assertion_refs": [
                {"ref_type": "assertion", "id": assertion.id}
                for assertion in package.assertions.records
                if assertion.predicate.startswith(f"{domain_id}/")
            ],
        }
        for domain_id in _COUNTED_DOMAINS
    ]
    normalized_request = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return cast(
        JsonObject,
        {
            "analysis_id": request.analysis_id,
            "analysis_contract_version": request.analysis_contract_version,
            "analysis_scope": request.analysis_scope.model_dump(mode="json"),
            "as_of_date": as_of_date,
            "period": request.period,
            "used_generation": package.manifest.generation_id,
            "result_id": _stable_uuid7(
                package.manifest.generation_id,
                request.analysis_contract_version,
                normalized_request,
            ),
            "components": components,
            "domain_counts": domain_counts,
            "inventory_steps": [
                {
                    "step_id": f"count-{count['domain_id']}",
                    "operation": "count_assertions",
                    "input_assertion_refs": count["assertion_refs"],
                    "result_count": count["count"],
                }
                for count in domain_counts
            ],
        },
    )


def _current_assertions(
    package: ValidatedPackage, as_of_date: date
) -> tuple[AssertionRecord, ...]:
    superseded = {
        assertion.supersedes
        for assertion in package.assertions.records
        if assertion.supersedes is not None
    }
    return tuple(
        assertion
        for assertion in package.assertions.records
        if assertion.id not in superseded
        and assertion.verification_status == "confirmed"
        and _active_on(assertion, as_of_date)
    )


def _value(assertion: AssertionRecord) -> JsonObject | None:
    if assertion.object_value is None:
        return None
    return cast(JsonObject, assertion.object_value.model_dump(mode="json"))


def _context_sections(
    package: ValidatedPackage, request: WorkflowNextRequest
) -> list[JsonObject]:
    active = _current_assertions(package, request.as_of_date)
    labels = {
        assertion.subject_ref.id: assertion.object_value.value
        for assertion in active
        if assertion.predicate == "topo.core/label"
        and assertion.object_value is not None
        and isinstance(assertion.object_value.value, str)
    }
    sections: list[JsonObject] = []
    for section_id, module_id, entity_types, coverage_predicate in _BASIS_SECTIONS:
        entities = tuple(
            entity
            for entity in package.entities.records
            if entity.entity_type in entity_types
        )
        item_results: list[JsonObject] = []
        for entity in entities:
            facts = [
                {
                    "predicate": assertion.predicate,
                    "object_ref": (
                        assertion.object_ref.model_dump(mode="json")
                        if assertion.object_ref is not None
                        else None
                    ),
                    "object_value": _value(assertion),
                    "valid_time": assertion.valid_time.model_dump(mode="json"),
                    "assertion_ref": {"ref_type": "assertion", "id": assertion.id},
                }
                for assertion in active
                if assertion.subject_ref.id == entity.id
            ]
            item_results.append(
                cast(
                    JsonObject,
                    {
                        "item_id": entity.id,
                        "item_type": entity.entity_type,
                        "label": str(labels.get(entity.id, entity.id)),
                        "entity_ref": {"ref_type": "entity", "id": entity.id},
                        "facts": facts,
                    },
                )
            )
        if section_id == "cashflow":
            for assertion in active:
                if assertion.predicate != "domain.cashflow/recurring_cashflow":
                    continue
                item_results.append(
                    {
                        "item_id": assertion.id,
                        "item_type": "recurring_cashflow",
                        "label": assertion.predicate,
                        "entity_ref": None,
                        "facts": [
                            {
                                "predicate": assertion.predicate,
                                "object_ref": None,
                                "object_value": _value(assertion),
                                "valid_time": assertion.valid_time.model_dump(
                                    mode="json"
                                ),
                                "assertion_ref": {
                                    "ref_type": "assertion",
                                    "id": assertion.id,
                                },
                            }
                        ],
                    }
                )
        coverage_assertion = next(
            (
                assertion
                for assertion in active
                if assertion.subject_ref.id == request.analysis_scope.entity_id
                and assertion.predicate == coverage_predicate
                and assertion.object_value is not None
                and isinstance(assertion.object_value.value, dict)
                and assertion.object_value.value.get("as_of_date")
                == request.as_of_date.isoformat()
            ),
            None,
        )
        coverage = "unknown"
        coverage_ref: JsonObject | None = None
        if (
            coverage_assertion is not None
            and coverage_assertion.object_value is not None
        ):
            raw_coverage = coverage_assertion.object_value.value
            assert isinstance(raw_coverage, dict)
            coverage = str(raw_coverage.get("coverage", "unknown"))
            coverage_ref = {"ref_type": "assertion", "id": coverage_assertion.id}
        open_proposals = [
            {
                "proposal_ref": {"ref_type": "proposal", "id": proposal.id},
                "proposal_type": proposal.proposal_type,
                "batch_id": proposal.batch_id,
            }
            for proposal in package.proposals.records
            if proposal.status == "open"
            and (
                (
                    proposal.proposed_entity is not None
                    and proposal.proposed_entity.module_id == module_id
                )
                or (
                    proposal.proposed_assertion is not None
                    and (
                        proposal.proposed_assertion.predicate.startswith(
                            f"{module_id}/"
                        )
                        or proposal.proposed_assertion.predicate == "topo.core/label"
                        and proposal.proposed_assertion.subject_ref.id
                        in {entity.id for entity in entities}
                    )
                )
            )
        ]
        detail_state = "present"
        if coverage == "complete" and item_results:
            required_predicates = {
                "accounts": {"topo.core/label", "domain.accounts/balance"},
                "assets": {"topo.core/label", "domain.assets/value"},
                "debts": {"topo.core/label", "domain.debts/balance"},
                "pensions": {"topo.core/label"},
                "contracts_insurance": {"topo.core/label"},
                "goals": {"topo.core/label", "domain.goals/definition"},
            }.get(section_id, set())
            for item in item_results:
                predicates = {
                    str(fact["predicate"])
                    for fact in cast(list[JsonObject], item["facts"])
                }
                item_type = str(item["item_type"])
                requires_classification = item_type in {
                    "account",
                    "asset",
                    "debt",
                    "contract",
                }
                has_classification = any(
                    predicate.startswith(f"{module_id}/classification/")
                    for predicate in predicates
                )
                allocation_predicate = {
                    "account": "domain.parties/account_holder",
                    "asset": "domain.parties/ownership",
                    "debt": "domain.parties/debtor",
                    "pension_entitlement": "domain.parties/beneficiary",
                }.get(item_type)
                has_allocation = allocation_predicate is None or bool(
                    {
                        allocation_predicate,
                        "domain.parties/household_allocation",
                    }
                    & predicates
                )
                if (
                    not required_predicates <= predicates
                    or requires_classification
                    and not has_classification
                    or not has_allocation
                ):
                    detail_state = "missing"
                    break
        sections.append(
            cast(
                JsonObject,
                {
                    "section_id": section_id,
                    "coverage": coverage,
                    "coverage_ref": coverage_ref,
                    "confirmed_items": item_results,
                    "open_proposals": open_proposals,
                    "requirements": [
                        {
                            "requirement": "inventory_coverage",
                            "state": "present" if coverage == "complete" else "missing",
                        },
                        {"requirement": "minimum_item_details", "state": detail_state},
                    ],
                },
            )
        )
    return sections


def _change_summary(
    package: ValidatedPackage, since_generation: str | None
) -> JsonObject:
    empty: JsonObject = {
        "since_generation": since_generation,
        "available": since_generation is None,
        "confirmed": [],
        "proposed": [],
        "replaced": [],
        "rejected": [],
    }
    if since_generation is None:
        return empty
    index = next(
        (
            position
            for position, entry in enumerate(package.journal.entries)
            if entry.generation_after == since_generation
        ),
        None,
    )
    if index is None:
        return empty
    empty["available"] = True
    for entry in package.journal.entries[index + 1 :]:
        item: JsonObject = {
            "operation": entry.operation,
            "generation_id": entry.generation_after,
            "recorded_at": entry.recorded_at.isoformat(),
            "result": entry.result,
        }
        if entry.operation in {"proposal.submit", "workflow.respond"}:
            cast(list[JsonObject], empty["proposed"]).append(item)
        elif entry.operation in {
            "proposal.confirm",
            "proposal.confirm-batch",
            "source.classify-batch",
        }:
            cast(list[JsonObject], empty["confirmed"]).append(item)
        elif entry.operation == "proposal.correct":
            cast(list[JsonObject], empty["replaced"]).append(item)
        elif entry.operation in {"proposal.reject", "proposal.reject-batch"}:
            cast(list[JsonObject], empty["rejected"]).append(item)
    return empty


def _context_action(
    package: ValidatedPackage,
    request: WorkflowNextRequest,
    section: JsonObject,
) -> JsonObject:
    section_id = str(section["section_id"])
    action_id = _stable_uuid7(
        package.manifest.generation_id,
        request.analysis_scope.entity_id,
        request.as_of_date.isoformat(),
        "basis_context",
        section_id,
    )
    items = [
        {
            "item_id": item["item_id"],
            "label": item["label"],
            "entity_ref": item["entity_ref"],
            "entity_type": item["item_type"],
        }
        for item in cast(list[JsonObject], section["confirmed_items"])
        if item["item_type"] != "recurring_cashflow"
    ]
    template: JsonObject = {
        "contract_version": request.contract_version,
        "operation_id": action_id,
        "context_id": request.context_id,
        "expected_generation": package.manifest.generation_id,
        "actor": {"actor_type": "agent", "actor_id": None},
        "reason": f"Answer basis-context action {action_id}",
        "workflow_response": {
            "action_id": action_id,
            "response_type": "context_inventory",
            "section_id": section_id,
            "analysis_scope": request.analysis_scope.model_dump(mode="json"),
            "as_of_date": request.as_of_date.isoformat(),
            "producer": {
                "producer_type": "agent",
                "producer_id": None,
                "producer_version": None,
            },
            "coverage": "complete",
            "items": cast(JsonValue, items),
        },
    }
    return {
        "action_id": action_id,
        "action_type": "answer_context_inventory",
        "action_contract_version": "topo.workflow-action/0.3",
        "priority": "required",
        "reason_code": f"BASIS_CONTEXT_NEEDS_{section_id.upper()}",
        "affected_component": f"basis_context/{section_id}",
        "related_refs": [],
        "command": "workflow.respond",
        "question": _SECTION_QUESTIONS[section_id],
        "available_context": {"section": section},
        "request_template": template,
        "user_input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["coverage", "items"],
            "properties": {
                "coverage": {"enum": ["partial", "complete"]},
                "items": {"type": "array", "items": {"type": "object"}},
            },
        },
        "user_input_paths": [
            "/workflow_response/coverage",
            "/workflow_response/items",
        ],
        "agent_input_paths": [
            "/actor/actor_id",
            "/workflow_response/producer/producer_id",
            "/workflow_response/producer/producer_version",
        ],
        "input_schema_ref": "topo://schema/workflow-respond-request/0.2",
        "requires_user_input": True,
        "requires_authorization": False,
    }


def _batch_action(
    package: ValidatedPackage, request: WorkflowNextRequest, batch_id: str
) -> JsonObject:
    action_id = _stable_uuid7(
        package.manifest.generation_id, batch_id, "prepare_batch_authorization"
    )
    return {
        "action_id": action_id,
        "action_type": "prepare_authorization",
        "action_contract_version": "topo.workflow-action/0.3",
        "priority": "blocking",
        "reason_code": "PROPOSAL_BATCH_REQUIRES_AUTHORIZATION",
        "affected_component": None,
        "related_refs": [
            {"ref_type": "proposal", "id": proposal.id}
            for proposal in package.proposals.records
            if proposal.status == "open" and proposal.batch_id == batch_id
        ],
        "command": "proposal.confirm-batch",
        "question": "Controleer en autoriseer de voorgestelde contextwijzigingen.",
        "available_context": {"batch_id": batch_id},
        "request_template": {
            "contract_version": request.contract_version,
            "operation_id": action_id,
            "context_id": request.context_id,
            "expected_generation": package.manifest.generation_id,
            "actor": {"actor_type": "agent", "actor_id": None},
            "reason": f"Prepare proposal batch {batch_id}",
            "batch_id": batch_id,
            "authorization": None,
        },
        "user_input_schema": {"type": "object", "additionalProperties": False},
        "user_input_paths": [],
        "agent_input_paths": ["/actor/actor_id"],
        "input_schema_ref": "topo://schema/proposal-confirm-batch-request/0.2",
        "requires_user_input": False,
        "requires_authorization": False,
    }


def next_workflow_action(
    package: ValidatedPackage, request: WorkflowNextRequest
) -> JsonObject:
    sections = _context_sections(package, request)
    if package.manifest.context_schema_version == "topo.context/0.1":
        from topo.builtin_modules import default_module_catalog

        action_id = _stable_uuid7(
            package.manifest.generation_id, "migrate", "topo.context/0.2"
        )
        migration_action: JsonObject = {
            "action_id": action_id,
            "action_type": "prepare_authorization",
            "action_contract_version": "topo.workflow-action/0.3",
            "priority": "blocking",
            "reason_code": "CONTEXT_MIGRATION_REQUIRED",
            "affected_component": None,
            "related_refs": [
                {"ref_type": "generation", "id": package.manifest.generation_id}
            ],
            "command": "context.migrate",
            "question": "Autoriseer de migratie van deze context naar topo.context/0.2.",
            "available_context": {},
            "request_template": {
                "contract_version": request.contract_version,
                "operation_id": action_id,
                "context_id": request.context_id,
                "expected_generation": package.manifest.generation_id,
                "actor": {"actor_type": "agent", "actor_id": None},
                "reason": "Migrate context for proactive workflow",
                "target_package_version": "0.2",
                "target_context_schema_version": "topo.context/0.2",
                "target_module_versions": {
                    pin.module_id: pin.module_version
                    for pin in default_module_catalog().pins
                },
                "authorization": None,
            },
            "user_input_schema": {"type": "object", "additionalProperties": False},
            "user_input_paths": [],
            "agent_input_paths": ["/actor/actor_id"],
            "input_schema_ref": "topo://schema/context-migrate-request/0.1",
            "requires_user_input": False,
            "requires_authorization": False,
        }
        return cast(
            JsonObject,
            {
                "workflow_contract_version": request.workflow_contract_version,
                "scope": request.analysis_scope.model_dump(mode="json"),
                "as_of_date": request.as_of_date.isoformat(),
                "used_generation": package.manifest.generation_id,
                "change_summary": _change_summary(package, request.since_generation),
                "context_sections": sections,
                "analysis_results": [],
                "next_action": migration_action,
                "actions": [migration_action],
            },
        )

    analysis_request = ContextInventoryAnalyzeRunRequest(
        contract_version=request.contract_version,
        analysis_id="analysis.context_inventory",
        analysis_contract_version="0.1",
        context_id=request.context_id,
        analysis_scope=request.analysis_scope,
        as_of_date=request.as_of_date,
        period=None,
        reporting_currency=None,
        scenario=None,
    )
    inventory_result = inventory_context(package, analysis_request)
    requirements, _ = _net_worth_requirements(package, analysis_request)
    decision = _next_requirement_decision(requirements, request.as_of_date.isoformat())
    net_worth_request = NetWorthAnalyzeRunRequest(
        contract_version=request.contract_version,
        analysis_id="analysis.net_worth",
        analysis_contract_version="0.1",
        context_id=request.context_id,
        analysis_scope=request.analysis_scope,
        as_of_date=request.as_of_date,
        period=None,
        reporting_currency=request.reporting_currency,
        scenario=None,
    )
    inventory_result["status"] = (
        "complete"
        if all(
            section["coverage"] == "complete"
            and all(
                requirement["state"] == "present"
                for requirement in cast(list[JsonObject], section["requirements"])
            )
            for section in sections
        )
        else "provisional"
    )
    net_worth_result = analyze_net_worth(package, net_worth_request)
    incomplete_requirements = [
        requirement for requirement in requirements if requirement["state"] != "present"
    ]
    net_worth_components = cast(list[JsonObject], net_worth_result["components"])
    net_worth_total = next(
        component
        for component in net_worth_components
        if component["component_id"] == "net_worth/total"
    )
    if incomplete_requirements and net_worth_total["status"] == "complete":
        net_worth_total["status"] = "provisional"
    net_worth_result["status"] = (
        "unavailable"
        if net_worth_total["status"] == "unavailable"
        else "provisional"
        if incomplete_requirements or net_worth_total["status"] == "provisional"
        else "complete"
    )
    net_worth_result["workflow_requirements"] = cast(JsonValue, incomplete_requirements)
    analysis_results: list[JsonObject] = [inventory_result, net_worth_result]
    batch_id = next(
        (
            proposal.batch_id
            for proposal in package.proposals.records
            if proposal.status == "open" and proposal.batch_id is not None
        ),
        None,
    )
    action: JsonObject | None = None
    if batch_id is not None:
        action = _batch_action(package, request, batch_id)

    component_id = "analysis.net_worth/total"
    accounts = _known_source_accounts(package)
    if (
        action is None
        and decision is not None
        and decision.requirement == "account_balances"
        and decision.state == "missing"
        and accounts
    ):
        action = _account_balance_action(
            package,
            request,
            decision,
            component_id=component_id,
            accounts=accounts,
        )
    elif action is None and decision is not None:
        target_section = {
            "account_balances": "accounts",
            "asset_valuations": "assets",
            "debt_balances": "debts",
        }.get(decision.requirement)
        if (
            request.include_basis_context
            and decision.state == "missing"
            and target_section is not None
        ):
            section = next(
                item for item in sections if item["section_id"] == target_section
            )
            action = _context_action(package, request, section)
        else:
            action = cast(
                JsonObject,
                {
                    "action_id": _stable_uuid7(
                        package.manifest.generation_id,
                        request.analysis_id,
                        request.analysis_scope.entity_id,
                        request.as_of_date.isoformat(),
                        decision.reason_code,
                    ),
                    "action_type": "answer_question",
                    "action_contract_version": "topo.workflow-action/0.1",
                    "priority": decision.priority,
                    "reason_code": decision.reason_code,
                    "affected_component": component_id,
                    "related_refs": [],
                    "command": "proposal.submit",
                    "request_template": {"proposal_type": decision.proposal_type},
                    "input_schema_ref": "topo://schema/proposal-submit-request/0.1",
                    "requires_user_input": True,
                    "requires_authorization": False,
                },
            )
    if action is None and request.include_basis_context:
        incomplete_sections = [
            item
            for item in sections
            if item["coverage"] != "complete"
            or any(
                requirement["state"] != "present"
                for requirement in cast(list[JsonObject], item["requirements"])
            )
        ]
        candidate_section = incomplete_sections[0] if incomplete_sections else None
        if candidate_section is not None:
            action = _context_action(package, request, candidate_section)
    return cast(
        JsonObject,
        {
            "workflow_contract_version": request.workflow_contract_version,
            "scope": request.analysis_scope.model_dump(mode="json"),
            "as_of_date": request.as_of_date.isoformat(),
            "used_generation": package.manifest.generation_id,
            "change_summary": _change_summary(package, request.since_generation),
            "context_sections": sections,
            "analysis_results": analysis_results,
            "next_action": action,
            "actions": [] if action is None else [action],
        },
    )
