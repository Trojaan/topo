from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from pydantic import JsonValue

from topo.canonical_validation import ValidatedPackage
from topo.models import (
    AssertionRecord,
    JsonObject,
    NormalizedAnalyzeRunRequest,
    RecurringCashflowValue,
)

_FACTORS = {
    "weekly": (Decimal(52), Decimal(12)),
    "four_weekly": (Decimal(13), Decimal(12)),
    "monthly": (Decimal(1), Decimal(1)),
    "quarterly": (Decimal(1), Decimal(3)),
    "annual": (Decimal(1), Decimal(12)),
}


@dataclass(frozen=True)
class _Cashflow:
    assertion: AssertionRecord
    value: RecurringCashflowValue
    currency: str
    minimum: Decimal
    maximum: Decimal
    expected: Decimal | None
    is_variable: bool


def _stable_uuid7(*parts: str) -> str:
    digest = bytearray(hashlib.sha256("\x1f".join(parts).encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x70
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _json(value: object) -> JsonValue:
    return cast(JsonValue, value)


def _presented_money(amount: Decimal, currency: str) -> JsonObject:
    return {"amount": f"{amount:.2f}", "currency": currency}


def _unrounded_money(amount: Decimal, currency: str) -> JsonObject:
    return {"amount": format(amount, "f"), "currency": currency}


def _refs(ref_type: str, ids: set[str]) -> list[JsonObject]:
    return [{"ref_type": ref_type, "id": item_id} for item_id in sorted(ids)]


def _normalize(amount: Decimal, frequency: str) -> Decimal:
    multiply_by, divide_by = _FACTORS[frequency]
    return amount * multiply_by / divide_by


def _active_cashflows(
    package: ValidatedPackage, request: NormalizedAnalyzeRunRequest
) -> tuple[_Cashflow, ...]:
    superseded = {
        assertion.supersedes
        for assertion in package.assertions.records
        if assertion.supersedes is not None
    }
    result: list[_Cashflow] = []
    for assertion in package.assertions.records:
        if (
            assertion.id in superseded
            or assertion.subject_ref.id != request.analysis_scope.entity_id
            or assertion.predicate != "domain.cashflow/recurring_cashflow"
            or assertion.object_value is None
            or assertion.object_value.value_type != "recurring_cashflow"
            or assertion.valid_time.start > request.as_of_date
            or (
                assertion.valid_time.end_exclusive is not None
                and request.as_of_date >= assertion.valid_time.end_exclusive
            )
        ):
            continue
        value = RecurringCashflowValue.model_validate(assertion.object_value.value)
        if value.money is not None:
            amount = _normalize(Decimal(value.money.amount), value.frequency)
            result.append(
                _Cashflow(
                    assertion=assertion,
                    value=value,
                    currency=value.money.currency,
                    minimum=amount,
                    maximum=amount,
                    expected=amount,
                    is_variable=False,
                )
            )
        else:
            assert value.amount_range is not None
            result.append(
                _Cashflow(
                    assertion=assertion,
                    value=value,
                    currency=value.amount_range.minimum.currency,
                    minimum=_normalize(
                        Decimal(value.amount_range.minimum.amount), value.frequency
                    ),
                    maximum=_normalize(
                        Decimal(value.amount_range.maximum.amount), value.frequency
                    ),
                    expected=(
                        None
                        if value.typical_money is None
                        else _normalize(
                            Decimal(value.typical_money.amount), value.frequency
                        )
                    ),
                    is_variable=True,
                )
            )
    return tuple(sorted(result, key=lambda item: item.assertion.id))


def _component(
    package: ValidatedPackage,
    request: NormalizedAnalyzeRunRequest,
    *,
    component_id: str,
    cashflows: tuple[_Cashflow, ...],
    currency: str,
    magnitude: bool = False,
) -> JsonObject:
    bounds = tuple(
        (
            (abs(item.maximum), abs(item.minimum))
            if magnitude
            else (item.minimum, item.maximum)
        )
        for item in cashflows
    )
    minimum = sum((item[0] for item in bounds), Decimal())
    maximum = sum((item[1] for item in bounds), Decimal())
    expected_parts = tuple(
        None
        if item.expected is None
        else abs(item.expected)
        if magnitude
        else item.expected
        for item in cashflows
    )
    expected = (
        None
        if any(item is None for item in expected_parts)
        else sum((cast(Decimal, item) for item in expected_parts), Decimal())
    )
    calculation_steps: list[JsonObject] = []
    for item, (item_minimum, item_maximum) in zip(cashflows, bounds, strict=True):
        multiply_by, divide_by = _FACTORS[item.value.frequency]
        source_values = (
            ("exact", item_minimum),
            ("minimum", item_minimum),
            ("maximum", item_maximum),
        )
        selected = source_values[:1] if not item.is_variable else source_values[1:]
        if item.is_variable and item.expected is not None:
            selected = (
                *selected,
                ("typical", abs(item.expected) if magnitude else item.expected),
            )
        for bound_name, result in selected:
            calculation_steps.append(
                {
                    "step_id": (
                        f"{component_id}/{item.assertion.id}/normalize-{bound_name}"
                    ),
                    "operation": "normalize_frequency",
                    "inputs": [{"ref_type": "assertion", "id": item.assertion.id}],
                    "factor": {
                        "multiply_by": format(multiply_by, "f"),
                        "divide_by": format(divide_by, "f"),
                    },
                    "unrounded_result": _unrounded_money(result, currency),
                }
            )
    totals = [("minimum", minimum), ("maximum", maximum)]
    if minimum == maximum:
        totals = [("exact", minimum)]
    elif expected is not None:
        totals.append(("expected", expected))
    for total_name, total in totals:
        calculation_steps.append(
            {
                "step_id": f"{component_id}/sum-{total_name}",
                "operation": "sum_normalized_money",
                "inputs": [],
                "unrounded_result": _unrounded_money(total, currency),
            }
        )
    assertion_ids = {item.assertion.id for item in cashflows}
    evidence_ids = {
        ref.id
        for item in cashflows
        for ref in item.assertion.provenance
        if ref.ref_type == "evidence"
    }
    component: JsonObject = {
        "component_id": component_id,
        "status": "complete",
        "used_assertion_refs": _json(_refs("assertion", assertion_ids)),
        "used_evidence_refs": _json(_refs("evidence", evidence_ids)),
        "assumptions": [],
        "calculation_steps": _json(calculation_steps),
        "rounding": {"mode": "currency_default", "presented_decimals": 2},
        "requirements": [
            {
                "requirement": "confirmed_current_recurring_cashflows",
                "state": "present",
                "impact": "Only confirmed recurring cashflows valid on the as-of date contribute.",
            }
        ],
        "blockers": [],
        "warnings": [],
        "next_question": None,
        "explain_ref": {
            "ref_type": "analysis_component",
            "id": _stable_uuid7(
                package.manifest.generation_id,
                request.analysis_id,
                component_id,
                request.as_of_date.isoformat(),
            ),
        },
    }
    if minimum == maximum:
        component["value"] = _presented_money(minimum, currency)
    else:
        component["minimum_value"] = _presented_money(minimum, currency)
        component["maximum_value"] = _presented_money(maximum, currency)
        if expected is not None:
            component["expected_value"] = _presented_money(expected, currency)
    return component


def analyze_normalized_monthly_cashflow(
    package: ValidatedPackage, request: NormalizedAnalyzeRunRequest
) -> JsonObject:
    if request.context_id != package.manifest.context_id:
        raise ValueError("request context does not match the package")
    if not any(
        item.id == request.analysis_scope.entity_id
        and item.entity_type == request.analysis_scope.scope_type
        for item in package.entities.records
    ):
        raise ValueError("analysis scope does not resolve to the requested entity type")
    cashflows = _active_cashflows(package, request)
    currencies = {item.currency for item in cashflows}
    if request.reporting_currency is not None:
        currency = request.reporting_currency.currency
    elif len(currencies) == 1:
        currency = next(iter(currencies))
    else:
        raise ValueError(
            "reporting currency is required when the included currency is ambiguous"
        )
    if any(item.currency != currency for item in cashflows):
        raise ValueError("currency conversion is unavailable without exchange rates")
    income = tuple(item for item in cashflows if item.value.direction == "inflow")
    expenses = tuple(item for item in cashflows if item.value.direction == "outflow")
    fixed_income = tuple(item for item in income if not item.is_variable)
    variable_income = tuple(item for item in income if item.is_variable)
    fixed_expenses = tuple(item for item in expenses if not item.is_variable)
    variable_expenses = tuple(item for item in expenses if item.is_variable)
    components = [
        _component(
            package,
            request,
            component_id="normalized/income",
            cashflows=income,
            currency=currency,
        ),
        _component(
            package,
            request,
            component_id="normalized/fixed_income",
            cashflows=fixed_income,
            currency=currency,
        ),
        _component(
            package,
            request,
            component_id="normalized/variable_income",
            cashflows=variable_income,
            currency=currency,
        ),
        _component(
            package,
            request,
            component_id="normalized/expense",
            cashflows=expenses,
            currency=currency,
            magnitude=True,
        ),
        _component(
            package,
            request,
            component_id="normalized/fixed_expense",
            cashflows=fixed_expenses,
            currency=currency,
            magnitude=True,
        ),
        _component(
            package,
            request,
            component_id="normalized/variable_expense",
            cashflows=variable_expenses,
            currency=currency,
            magnitude=True,
        ),
        _component(
            package,
            request,
            component_id="normalized/net",
            cashflows=cashflows,
            currency=currency,
        ),
    ]
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
        "components": _json(components),
    }
