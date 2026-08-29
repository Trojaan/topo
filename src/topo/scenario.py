from __future__ import annotations

import hashlib
import uuid
from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import cast

from pydantic import JsonValue

from topo.canonical_validation import ValidatedPackage
from topo.models import (
    AssertionRecord,
    JsonObject,
    NetWorthAnalyzeRunRequest,
    NormalizedAnalyzeRunRequest,
    OneOffCashflowAssumption,
    RecurringCashflowChangeAssumption,
    RecurringCashflowValue,
    ScenarioAnalyzeRunRequest,
    ScenarioAssumption,
    ValueOverrideAssumption,
)
from topo.net_worth import analyze_net_worth
from topo.normalized_cashflow import analyze_normalized_monthly_cashflow

_FACTORS = {
    "weekly": (Decimal(52), Decimal(12)),
    "four_weekly": (Decimal(13), Decimal(12)),
    "monthly": (Decimal(1), Decimal(1)),
    "quarterly": (Decimal(1), Decimal(3)),
    "annual": (Decimal(1), Decimal(12)),
}
_VALUATION_SIGNS = {
    "domain.accounts/balance": Decimal(1),
    "domain.assets/value": Decimal(1),
    "jurisdiction.nl/valuation/woz": Decimal(1),
    "domain.debts/balance": Decimal(-1),
}
_STATUS_ORDER = {"complete": 0, "provisional": 1, "unavailable": 2}


def _json(value: object) -> JsonValue:
    return cast(JsonValue, value)


def _stable_uuid7(*parts: str) -> str:
    digest = bytearray(hashlib.sha256("\x1f".join(parts).encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x70
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _money(amount: Decimal, currency: str, *, presented: bool = True) -> JsonObject:
    return {
        "amount": f"{amount:.2f}" if presented else format(amount, "f"),
        "currency": currency,
    }


def _active(assertion: AssertionRecord, on_date: date) -> bool:
    return assertion.valid_time.start <= on_date and (
        assertion.valid_time.end_exclusive is None
        or on_date < assertion.valid_time.end_exclusive
    )


def _active_assertions(
    package: ValidatedPackage, on_date: date
) -> tuple[AssertionRecord, ...]:
    superseded = {
        item.supersedes
        for item in package.assertions.records
        if item.supersedes is not None
    }
    return tuple(
        item
        for item in package.assertions.records
        if item.id not in superseded and _active(item, on_date)
    )


def _component(result: JsonObject, component_id: str) -> JsonObject:
    components = cast(list[JsonObject], result["components"])
    return deepcopy(
        next(item for item in components if item["component_id"] == component_id)
    )


def _assumptions(items: tuple[ScenarioAssumption, ...]) -> list[JsonObject]:
    return [cast(JsonObject, item.model_dump(mode="json")) for item in items]


def _validate_request(
    package: ValidatedPackage, request: ScenarioAnalyzeRunRequest
) -> None:
    entity_ids = {item.id for item in package.entities.records}
    seen_overrides: set[str] = set()
    for assumption in request.scenario.assumptions:
        if assumption.target_ref.ref_type != "entity":
            raise ValueError("scenario assumptions must target an entity")
        if assumption.target_ref.id not in entity_ids:
            raise ValueError("scenario assumption target does not exist")
        if assumption.effective_date > request.as_of_date:
            raise ValueError("scenario assumption takes effect after the scenario date")
        amount = Decimal(assumption.money.amount)
        if isinstance(assumption, OneOffCashflowAssumption) and amount <= 0:
            raise ValueError("one-off cashflow money must be positive")
        if isinstance(assumption, ValueOverrideAssumption):
            if amount < 0:
                raise ValueError("a value override must not be negative")
            if assumption.effective_date != request.as_of_date:
                raise ValueError("a value override must be dated on the scenario date")
            if assumption.target_ref.id in seen_overrides:
                raise ValueError(
                    "an entity can have only one value override per scenario"
                )
            seen_overrides.add(assumption.target_ref.id)


def _normalized_amount(assertion: AssertionRecord) -> tuple[Decimal, str]:
    if assertion.object_value is None:
        raise ValueError("recurring cashflow target has no value")
    value = RecurringCashflowValue.model_validate(
        assertion.object_value.value, strict=True
    )
    if value.money is None:
        raise ValueError("replace and end require an exact recurring cashflow")
    multiply, divide = _FACTORS[value.frequency]
    return Decimal(value.money.amount) * multiply / divide, value.money.currency


def _recurring_delta(
    package: ValidatedPackage,
    request: ScenarioAnalyzeRunRequest,
    assumptions: tuple[RecurringCashflowChangeAssumption, ...],
) -> Decimal:
    active = _active_assertions(package, request.as_of_date)
    total = Decimal()
    for assumption in assumptions:
        if assumption.money.currency != request.reporting_currency.currency:
            raise ValueError("scenario cashflow currency must match reporting currency")
        proposed = Decimal(assumption.money.amount)
        if assumption.change == "add":
            total += proposed
            continue
        matches = tuple(
            item
            for item in active
            if item.subject_ref.id == assumption.target_ref.id
            and item.predicate == "domain.cashflow/recurring_cashflow"
        )
        if len(matches) != 1:
            raise ValueError(
                "replace and end must resolve to exactly one recurring cashflow"
            )
        current, currency = _normalized_amount(matches[0])
        if currency != assumption.money.currency:
            raise ValueError("recurring cashflow change currency must match its target")
        total += -current if assumption.change == "end" else proposed - current
    return total


def _adjust_component(
    baseline: JsonObject,
    *,
    delta: Decimal,
    currency: str,
    assumptions: tuple[ScenarioAssumption, ...],
    operation: str,
) -> JsonObject:
    scenario = deepcopy(baseline)
    scenario["assumptions"] = _json(_assumptions(assumptions))
    for field in ("value", "minimum_value", "maximum_value", "expected_value"):
        value = scenario.get(field)
        if not isinstance(value, dict):
            continue
        if value.get("currency") != currency:
            raise ValueError(
                "scenario assumption currency does not match the component"
            )
        adjusted = Decimal(cast(str, value["amount"])) + delta
        scenario[field] = _money(adjusted, currency)
    if scenario.get("status") != "unavailable":
        steps = cast(list[JsonObject], scenario["calculation_steps"])
        steps.append(
            {
                "step_id": f"{scenario['component_id']}/apply-scenario",
                "operation": operation,
                "inputs": _json(
                    [
                        cast(JsonObject, item.money.model_dump(mode="json"))
                        for item in assumptions
                    ]
                ),
                "unrounded_result": _money(delta, currency, presented=False),
            }
        )
    return scenario


def _one_off_component(
    package: ValidatedPackage,
    request: ScenarioAnalyzeRunRequest,
    assumptions: tuple[OneOffCashflowAssumption, ...],
    *,
    scenario: bool,
) -> JsonObject:
    currency = request.reporting_currency.currency
    amount = Decimal()
    if scenario:
        for assumption in assumptions:
            if assumption.money.currency != currency:
                raise ValueError(
                    "one-off cashflow currency must match reporting currency"
                )
            sign = Decimal(1) if assumption.direction == "inflow" else Decimal(-1)
            amount += Decimal(assumption.money.amount) * sign
    component_id = "scenario/one_off_cashflow"
    return {
        "component_id": component_id,
        "status": "complete",
        "value": _money(amount, currency),
        "used_assertion_refs": [],
        "used_evidence_refs": [],
        "assumptions": _json(_assumptions(assumptions) if scenario else []),
        "calculation_steps": _json(
            [
                {
                    "step_id": f"{component_id}/sum",
                    "operation": "sum_explicit_one_off_cashflows",
                    "inputs": _json(
                        [
                            cast(JsonObject, item.money.model_dump(mode="json"))
                            for item in assumptions
                        ]
                        if scenario
                        else []
                    ),
                    "unrounded_result": _money(amount, currency, presented=False),
                }
            ]
        ),
        "rounding": {"mode": "currency_default", "presented_decimals": 2},
        "requirements": [
            {
                "requirement": "explicit_dated_one_off_cashflows",
                "state": "present",
                "impact": "Only explicit one-off assumptions contribute.",
            }
        ],
        "blockers": [],
        "warnings": [],
        "next_question": None,
        "explain_ref": {
            "ref_type": "analysis_component",
            "id": _stable_uuid7(
                package.manifest.generation_id,
                request.scenario.scenario_id,
                component_id,
                "scenario" if scenario else "baseline",
            ),
        },
    }


def _value_override_delta(
    package: ValidatedPackage,
    request: ScenarioAnalyzeRunRequest,
    assumptions: tuple[ValueOverrideAssumption, ...],
) -> Decimal:
    active = _active_assertions(package, request.as_of_date)
    total = Decimal()
    for assumption in assumptions:
        matches = tuple(
            item
            for item in active
            if item.subject_ref.id == assumption.target_ref.id
            and item.predicate in _VALUATION_SIGNS
            and item.object_value is not None
            and item.object_value.value_type == "money"
        )
        if len(matches) != 1:
            raise ValueError("value override must resolve to exactly one usable value")
        assertion = matches[0]
        assert assertion.object_value is not None
        value = cast(dict[str, str], assertion.object_value.value)
        if value["currency"] != assumption.money.currency:
            raise ValueError("value override currency must match its target")
        if value["currency"] != request.reporting_currency.currency:
            raise ValueError("value override currency must match reporting currency")
        sign = _VALUATION_SIGNS[assertion.predicate]
        total += (Decimal(assumption.money.amount) - Decimal(value["amount"])) * sign
    return total


def _diagnostic(code: str, assumptions: tuple[ScenarioAssumption, ...]) -> JsonObject:
    return {
        "code": code,
        "message_key": f"diagnostic.{code.lower()}",
        "severity": "warning",
        "path": "/scenario/assumptions",
        "params": {},
        "retryable": False,
        "effect": "none",
        "related_refs": _json(
            [item.target_ref.model_dump(mode="json") for item in assumptions]
        ),
    }


def _delta_component(
    package: ValidatedPackage,
    request: ScenarioAnalyzeRunRequest,
    baseline: JsonObject,
    scenario: JsonObject,
    assumptions: tuple[ScenarioAssumption, ...],
) -> JsonObject:
    baseline_status = cast(str, baseline["status"])
    scenario_status = cast(str, scenario["status"])
    status = max((baseline_status, scenario_status), key=_STATUS_ORDER.__getitem__)
    component: JsonObject = {
        "component_id": cast(str, scenario["component_id"]),
        "status": status,
        "used_assertion_refs": deepcopy(scenario["used_assertion_refs"]),
        "used_evidence_refs": deepcopy(scenario["used_evidence_refs"]),
        "assumptions": _json(_assumptions(assumptions)),
        "calculation_steps": [],
        "rounding": {"mode": "currency_default", "presented_decimals": 2},
        "requirements": deepcopy(scenario["requirements"]),
        "blockers": deepcopy(scenario["blockers"]),
        "warnings": deepcopy(scenario["warnings"]),
        "next_question": scenario["next_question"],
        "explain_ref": {
            "ref_type": "analysis_component",
            "id": _stable_uuid7(
                package.manifest.generation_id,
                request.scenario.scenario_id,
                cast(str, scenario["component_id"]),
                "delta",
            ),
        },
    }
    for field in ("value", "minimum_value", "maximum_value", "expected_value"):
        baseline_value = baseline.get(field)
        scenario_value = scenario.get(field)
        if not isinstance(baseline_value, dict) or not isinstance(scenario_value, dict):
            continue
        currency = cast(str, scenario_value["currency"])
        difference = Decimal(cast(str, scenario_value["amount"])) - Decimal(
            cast(str, baseline_value["amount"])
        )
        component[field] = _money(difference, currency)
    if status != "unavailable" and isinstance(component.get("value"), dict):
        value = cast(JsonObject, component["value"])
        component["calculation_steps"] = _json(
            [
                {
                    "step_id": f"{component['component_id']}/subtract-baseline",
                    "operation": "subtract_baseline",
                    "inputs": _json(
                        [
                            cast(JsonObject, baseline["value"]),
                            cast(JsonObject, scenario["value"]),
                        ]
                    ),
                    "unrounded_result": {
                        "amount": cast(str, value["amount"]),
                        "currency": cast(str, value["currency"]),
                    },
                }
            ]
        )
    return component


def analyze_scenario_comparison(
    package: ValidatedPackage, request: ScenarioAnalyzeRunRequest
) -> JsonObject:
    if request.context_id != package.manifest.context_id:
        raise ValueError("request context does not match the package")
    if not any(
        item.id == request.analysis_scope.entity_id
        and item.entity_type == request.analysis_scope.scope_type
        for item in package.entities.records
    ):
        raise ValueError("analysis scope does not resolve to the requested entity type")
    _validate_request(package, request)

    normalized_request = NormalizedAnalyzeRunRequest(
        contract_version=request.contract_version,
        analysis_id="analysis.normalized_monthly_cashflow",
        analysis_contract_version=request.analysis_contract_version,
        context_id=request.context_id,
        analysis_scope=request.analysis_scope,
        as_of_date=request.as_of_date,
        period=None,
        reporting_currency=request.reporting_currency,
        scenario=None,
    )
    net_worth_request = NetWorthAnalyzeRunRequest(
        contract_version=request.contract_version,
        analysis_id="analysis.net_worth",
        analysis_contract_version=request.analysis_contract_version,
        context_id=request.context_id,
        analysis_scope=request.analysis_scope,
        as_of_date=request.as_of_date,
        period=None,
        reporting_currency=request.reporting_currency,
        scenario=None,
    )
    normalized = analyze_normalized_monthly_cashflow(package, normalized_request)
    net_worth = analyze_net_worth(package, net_worth_request)
    baseline_cashflow = _component(normalized, "normalized/net")
    baseline_net_worth = _component(net_worth, "net_worth/total")

    recurring = tuple(
        item
        for item in request.scenario.assumptions
        if isinstance(item, RecurringCashflowChangeAssumption)
    )
    one_offs = tuple(
        item
        for item in request.scenario.assumptions
        if isinstance(item, OneOffCashflowAssumption)
    )
    overrides = tuple(
        item
        for item in request.scenario.assumptions
        if isinstance(item, ValueOverrideAssumption)
    )
    currency = request.reporting_currency.currency
    scenario_cashflow = _adjust_component(
        baseline_cashflow,
        delta=_recurring_delta(package, request, recurring),
        currency=currency,
        assumptions=recurring,
        operation="apply_explicit_recurring_cashflow_changes",
    )
    baseline_one_off = _one_off_component(package, request, one_offs, scenario=False)
    scenario_one_off = _one_off_component(package, request, one_offs, scenario=True)
    scenario_net_worth = _adjust_component(
        baseline_net_worth,
        delta=_value_override_delta(package, request, overrides),
        currency=currency,
        assumptions=request.scenario.assumptions,
        operation="apply_explicit_value_overrides",
    )
    cashflow_assumptions: tuple[ScenarioAssumption, ...] = (*recurring, *one_offs)
    if cashflow_assumptions:
        warnings = cast(list[JsonObject], scenario_net_worth["warnings"])
        warnings.append(
            _diagnostic("CASHFLOW_DESTINATION_NOT_MODELED", cashflow_assumptions)
        )

    baseline: dict[str, JsonObject] = {
        "normalized_monthly_cashflow": baseline_cashflow,
        "one_off_cashflow": baseline_one_off,
        "net_worth": baseline_net_worth,
    }
    scenario: dict[str, JsonObject] = {
        "normalized_monthly_cashflow": scenario_cashflow,
        "one_off_cashflow": scenario_one_off,
        "net_worth": scenario_net_worth,
    }
    relevant_assumptions: dict[str, tuple[ScenarioAssumption, ...]] = {
        "normalized_monthly_cashflow": recurring,
        "one_off_cashflow": one_offs,
        "net_worth": request.scenario.assumptions,
    }
    delta = {
        name: _delta_component(
            package,
            request,
            baseline[name],
            scenario[name],
            relevant_assumptions[name],
        )
        for name in baseline
    }
    return {
        "analysis_id": request.analysis_id,
        "analysis_contract_version": request.analysis_contract_version,
        "analysis_scope": request.analysis_scope.model_dump(mode="json"),
        "as_of_date": request.as_of_date.isoformat(),
        "period": None,
        "used_generation": package.manifest.generation_id,
        "result_id": _stable_uuid7(
            package.manifest.generation_id, request.model_dump_json()
        ),
        "scenario_id": request.scenario.scenario_id,
        "knowledge_type": "projected",
        "baseline": _json(baseline),
        "scenario": _json(scenario),
        "delta": _json(delta),
    }
