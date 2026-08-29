from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from pydantic import JsonValue

from topo.canonical_validation import ValidatedPackage
from topo.models import (
    AssertionRecord,
    ExchangeRateValue,
    JsonObject,
    Money,
    NetWorthAnalyzeRunRequest,
)

_KINDS = {
    "domain.accounts/balance": ("account", Decimal(1)),
    "domain.assets/value": ("asset", Decimal(1)),
    "jurisdiction.nl/valuation/woz": ("asset", Decimal(1)),
    "domain.debts/balance": ("debt", Decimal(-1)),
    "domain.pensions/value": ("pension", Decimal(1)),
}
_RELATIONS = {
    "domain.parties/household_allocation",
    "domain.parties/account_holder",
    "domain.parties/ownership",
    "domain.parties/debtor",
    "domain.parties/beneficiary",
    "domain.parties/scope",
}
_RESTRICTIONS = {
    "jurisdiction.nl/qualification/retirement_restriction",
    "jurisdiction.nl/qualification/annuity_restriction",
}
_DOUBLE_COUNTED_BASES = (
    {"account_balance", "asset_value"},
    {"portfolio_total", "position_sum"},
    {"credit_account", "debt_balance"},
)
_VALUATION_BASES = {
    "account_balance",
    "asset_value",
    "debt_balance",
    "pension_value",
    "portfolio_total",
    "position_sum",
    "credit_account",
}


@dataclass(frozen=True)
class _Valuation:
    assertion: AssertionRecord
    interest: str
    kind: str
    basis: str
    amount: Decimal
    currency: str
    sign: Decimal
    related_assertions: tuple[AssertionRecord, ...]
    restricted: bool


@dataclass(frozen=True)
class _Issue:
    code: str
    state: str
    currency: str
    assertions: tuple[AssertionRecord, ...]


def _stable_uuid7(*parts: str) -> str:
    digest = bytearray(hashlib.sha256("\x1f".join(parts).encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x70
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _json(value: object) -> JsonValue:
    return cast(JsonValue, value)


def _money(amount: Decimal, currency: str, *, presented: bool = True) -> JsonObject:
    return {
        "amount": f"{amount:.2f}" if presented else format(amount, "f"),
        "currency": currency,
    }


def _refs(ref_type: str, ids: set[str]) -> list[JsonObject]:
    return [{"ref_type": ref_type, "id": item_id} for item_id in sorted(ids)]


def _active_on(assertion: AssertionRecord, on_date: date) -> bool:
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
        if item.id not in superseded and _active_on(item, on_date)
    )


def _allocation(
    active: tuple[AssertionRecord, ...],
    request: NetWorthAnalyzeRunRequest,
    subject_id: str,
) -> tuple[AssertionRecord, ...] | None:
    if subject_id == request.analysis_scope.entity_id:
        return ()
    relations = tuple(
        item
        for item in active
        if item.subject_ref.id == subject_id
        and item.predicate in _RELATIONS
        and item.object_ref is not None
        and item.object_ref.id == request.analysis_scope.entity_id
    )
    if request.analysis_scope.scope_type == "person":
        return relations or None
    complete = tuple(
        item
        for item in relations
        if item.module_data.get("distribution") == {"complete": True, "shares": ["1"]}
    )
    return complete or None


def _restriction_assertions(
    active: tuple[AssertionRecord, ...], valuation: AssertionRecord, interest: str
) -> tuple[AssertionRecord, ...]:
    return tuple(
        item
        for item in active
        if item.predicate in _RESTRICTIONS
        and (
            item.module_data.get("economic_interest_ref") == interest
            or (
                "economic_interest_ref" not in item.module_data
                and item.subject_ref.id == valuation.subject_ref.id
            )
        )
    )


def _collect(
    package: ValidatedPackage, request: NetWorthAnalyzeRunRequest
) -> tuple[tuple[_Valuation, ...], tuple[_Issue, ...]]:
    active = _active_assertions(package, request.as_of_date)
    groups: dict[str, list[AssertionRecord]] = {}
    for assertion in active:
        if assertion.predicate not in _KINDS:
            continue
        interest = assertion.module_data.get("economic_interest_ref")
        if isinstance(interest, str) and interest:
            groups.setdefault(interest, []).append(assertion)

    valuations: list[_Valuation] = []
    issues: list[_Issue] = []
    for interest, candidates in sorted(groups.items()):
        parsed: list[tuple[AssertionRecord, Money]] = []
        for assertion in candidates:
            if (
                assertion.object_value is None
                or assertion.object_value.value_type != "money"
            ):
                continue
            parsed.append(
                (
                    assertion,
                    Money.model_validate(assertion.object_value.value, strict=True),
                )
            )
        if not parsed:
            continue
        currencies = {money.currency for _, money in parsed}
        bases = {
            basis
            for assertion, _ in parsed
            if isinstance(basis := assertion.module_data.get("valuation_basis"), str)
        }
        monetary_values = {(money.amount, money.currency) for _, money in parsed}
        conflicting_basis = any(pair <= bases for pair in _DOUBLE_COUNTED_BASES)
        if len(currencies) != 1 or len(monetary_values) != 1 or conflicting_basis:
            for currency in sorted(currencies):
                issues.append(
                    _Issue(
                        "CONFLICTING_VALUATION",
                        "conflicting",
                        currency,
                        tuple(item for item, _ in parsed),
                    )
                )
            continue
        assertion, money = min(parsed, key=lambda item: item[0].id)
        allocation = _allocation(active, request, assertion.subject_ref.id)
        if allocation is None:
            issues.append(
                _Issue(
                    "VALUATION_NOT_ALLOCATED",
                    "unallocated",
                    money.currency,
                    (assertion,),
                )
            )
            continue
        kind, sign = _KINDS[assertion.predicate]
        restrictions = _restriction_assertions(active, assertion, interest)
        basis = cast(str, assertion.module_data["valuation_basis"])
        valuations.append(
            _Valuation(
                assertion=assertion,
                interest=interest,
                kind=kind,
                basis=basis,
                amount=Decimal(money.amount),
                currency=money.currency,
                sign=sign,
                related_assertions=(*allocation, *restrictions),
                restricted=kind == "pension" or bool(restrictions),
            )
        )
    for assertion in active:
        interest = assertion.module_data.get("economic_interest_ref")
        basis = assertion.module_data.get("valuation_basis")
        expected_currency = assertion.module_data.get("expected_currency")
        if (
            not isinstance(interest, str)
            or not interest
            or interest in groups
            or basis not in _VALUATION_BASES
            or not isinstance(expected_currency, str)
            or len(expected_currency) != 3
        ):
            continue
        allocation = _allocation(active, request, assertion.subject_ref.id)
        issues.append(
            _Issue(
                "MISSING_VALUATION"
                if allocation is not None
                else "VALUATION_NOT_ALLOCATED",
                "missing" if allocation is not None else "unallocated",
                expected_currency,
                (assertion, *(() if allocation is None else allocation)),
            )
        )
    return tuple(valuations), tuple(issues)


def _diagnostic(
    code: str, assertions: tuple[AssertionRecord, ...], *, blocker: bool
) -> JsonObject:
    return {
        "code": code,
        "message_key": f"diagnostic.{code.lower()}",
        "severity": "error" if blocker else "warning",
        "path": "/components",
        "params": {},
        "retryable": False,
        "effect": "none",
        "related_refs": _json(
            _refs("assertion", {assertion.id for assertion in assertions})
        ),
    }


def _component(
    package: ValidatedPackage,
    request: NetWorthAnalyzeRunRequest,
    *,
    component_id: str,
    currency: str,
    valuations: tuple[_Valuation, ...],
    issues: tuple[_Issue, ...] = (),
) -> JsonObject:
    unavailable = any(issue.state == "conflicting" for issue in issues)
    status = "unavailable" if unavailable else "provisional" if issues else "complete"
    amount = sum((item.amount * item.sign for item in valuations), Decimal())
    assertions = tuple(
        assertion
        for item in valuations
        for assertion in (item.assertion, *item.related_assertions)
    ) + tuple(assertion for issue in issues for assertion in issue.assertions)
    assertion_ids = {item.id for item in assertions}
    evidence_ids = {
        ref.id
        for assertion in assertions
        for ref in assertion.provenance
        if ref.ref_type == "evidence"
    }
    blockers = [
        _diagnostic(issue.code, issue.assertions, blocker=True)
        for issue in issues
        if issue.state == "conflicting"
    ]
    warnings = [
        _diagnostic(issue.code, issue.assertions, blocker=False)
        for issue in issues
        if issue.state != "conflicting"
    ]
    component: JsonObject = {
        "component_id": component_id,
        "status": status,
        "used_assertion_refs": _json(_refs("assertion", assertion_ids)),
        "used_evidence_refs": _json(_refs("evidence", evidence_ids)),
        "assumptions": [],
        "calculation_steps": [],
        "rounding": {"mode": "currency_default", "presented_decimals": 2},
        "requirements": [
            {
                "requirement": "current_allocated_valuations",
                "state": (
                    "conflicting"
                    if unavailable
                    else issues[0].state
                    if issues
                    else "present"
                ),
                "impact": "Only current, explicitly allocated, non-conflicting values contribute.",
            }
        ],
        "blockers": _json(blockers),
        "warnings": _json(warnings),
        "next_question": (
            "Which current valuation or allocation resolves this net-worth component?"
            if issues
            else None
        ),
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
    if not unavailable:
        component["value"] = _money(amount, currency)
        component["calculation_steps"] = _json(
            [
                {
                    "step_id": f"{component_id}/sum",
                    "operation": "sum_allocated_net_worth",
                    "inputs": _json(
                        _refs("assertion", {item.assertion.id for item in valuations})
                    ),
                    "unrounded_result": _money(amount, currency, presented=False),
                }
            ]
        )
    return component


def _rates(
    package: ValidatedPackage, request: NetWorthAnalyzeRunRequest
) -> dict[tuple[str, str], tuple[Decimal, AssertionRecord]]:
    if request.reporting_currency is None:
        return {}
    allowed = {ref.id for ref in request.reporting_currency.allowed_rate_assertion_refs}
    result: dict[tuple[str, str], tuple[Decimal, AssertionRecord]] = {}
    for assertion in _active_assertions(package, request.as_of_date):
        if (
            assertion.id not in allowed
            or assertion.predicate != "topo.core/exchange_rate"
            or assertion.object_value is None
            or assertion.object_value.value_type != "exchange_rate"
        ):
            continue
        rate = ExchangeRateValue.model_validate(
            assertion.object_value.value, strict=True
        )
        if rate.as_of_date != request.as_of_date:
            continue
        value = Decimal(rate.rate)
        result[(rate.base_currency, rate.quote_currency)] = (value, assertion)
        result[(rate.quote_currency, rate.base_currency)] = (
            Decimal(1) / value,
            assertion,
        )
    return result


def _total_component(
    package: ValidatedPackage,
    request: NetWorthAnalyzeRunRequest,
    subtotals: dict[
        str, tuple[Decimal, str, tuple[_Valuation, ...], tuple[_Issue, ...]]
    ],
) -> JsonObject:
    reporting = (
        request.reporting_currency.currency if request.reporting_currency else None
    )
    assertion_ids = {
        assertion.id
        for _, _, valuations, issues in subtotals.values()
        for assertion in (
            *(item.assertion for item in valuations),
            *(item for issue in issues for item in issue.assertions),
        )
    }
    blockers: list[JsonObject] = []
    rates = _rates(package, request)
    total = Decimal()
    used_rates: list[AssertionRecord] = []
    steps: list[JsonObject] = []
    if not subtotals:
        blockers.append(_diagnostic("MISSING_NET_WORTH_INPUT", (), blocker=True))
    elif reporting is None and len(subtotals) > 1:
        blockers.append(_diagnostic("MISSING_REPORTING_CURRENCY", (), blocker=True))
    elif any(status == "unavailable" for _, status, _, _ in subtotals.values()):
        blockers.append(
            _diagnostic("DEPENDENT_VALUATION_UNAVAILABLE", (), blocker=True)
        )
    else:
        reporting = reporting or next(iter(subtotals))
        for currency, (amount, _, valuations, _) in sorted(subtotals.items()):
            rate = Decimal(1)
            if currency != reporting:
                found = rates.get((currency, reporting))
                if found is None:
                    blockers.append(
                        _diagnostic("MISSING_EXCHANGE_RATE", (), blocker=True)
                    )
                    continue
                rate, rate_assertion = found
                used_rates.append(rate_assertion)
                assertion_ids.add(rate_assertion.id)
            converted = amount * rate
            total += converted
            steps.append(
                {
                    "step_id": f"net_worth/total/convert-{currency}",
                    "operation": "convert_currency",
                    "inputs": _json(
                        _refs("assertion", {item.assertion.id for item in valuations})
                    ),
                    "unrounded_result": _money(converted, reporting, presented=False),
                }
            )
    evidence_ids = {
        ref.id
        for assertion in used_rates
        for ref in assertion.provenance
        if ref.ref_type == "evidence"
    }
    status = (
        "unavailable"
        if blockers
        else "provisional"
        if any(status == "provisional" for _, status, _, _ in subtotals.values())
        else "complete"
    )
    component: JsonObject = {
        "component_id": "net_worth/total",
        "status": status,
        "used_assertion_refs": _json(_refs("assertion", assertion_ids)),
        "used_evidence_refs": _json(_refs("evidence", evidence_ids)),
        "assumptions": [],
        "calculation_steps": _json(steps if not blockers else []),
        "rounding": {"mode": "currency_default", "presented_decimals": 2},
        "requirements": [
            {
                "requirement": "convertible_currency_subtotals",
                "state": "missing" if blockers else "present",
                "impact": "Every original-currency subtotal needs an explicit allowed rate.",
            }
        ],
        "blockers": _json(blockers),
        "warnings": [],
        "next_question": (
            "Which dated exchange rate may Topo use for the unavailable total?"
            if blockers
            else None
        ),
        "explain_ref": {
            "ref_type": "analysis_component",
            "id": _stable_uuid7(
                package.manifest.generation_id,
                request.analysis_id,
                "net_worth/total",
                request.as_of_date.isoformat(),
            ),
        },
    }
    if not blockers and reporting is not None:
        component["value"] = _money(total, reporting)
    return component


def analyze_net_worth(
    package: ValidatedPackage, request: NetWorthAnalyzeRunRequest
) -> JsonObject:
    if request.context_id != package.manifest.context_id:
        raise ValueError("request context does not match the package")
    if not any(
        item.id == request.analysis_scope.entity_id
        and item.entity_type == request.analysis_scope.scope_type
        for item in package.entities.records
    ):
        raise ValueError("analysis scope does not resolve to the requested entity type")

    valuations, issues = _collect(package, request)
    currencies = sorted(
        {item.currency for item in valuations} | {issue.currency for issue in issues}
    )
    components: list[JsonObject] = []
    subtotals: dict[
        str, tuple[Decimal, str, tuple[_Valuation, ...], tuple[_Issue, ...]]
    ] = {}
    for currency in currencies:
        included = tuple(
            item
            for item in valuations
            if item.currency == currency and not item.restricted
        )
        local_issues = tuple(item for item in issues if item.currency == currency)
        component = _component(
            package,
            request,
            component_id=f"net_worth/{currency}",
            currency=currency,
            valuations=included,
            issues=local_issues,
        )
        components.append(component)
        subtotals[currency] = (
            sum((item.amount * item.sign for item in included), Decimal()),
            cast(str, component["status"]),
            included,
            local_issues,
        )
    for currency in sorted({item.currency for item in valuations if item.restricted}):
        restricted = tuple(
            item for item in valuations if item.currency == currency and item.restricted
        )
        components.append(
            _component(
                package,
                request,
                component_id=f"net_worth/restricted_pension/{currency}",
                currency=currency,
                valuations=restricted,
            )
        )
    components.append(_total_component(package, request, subtotals))
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
