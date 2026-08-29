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
    AnalyzeRunRequest,
    AssertionRecord,
    Diagnostic,
    JsonObject,
    Ref,
    SourceImportRecord,
    SourceRecordEvidenceRecord,
)

_INCOME = {
    "income",
    "salary",
    "holiday_allowance",
    "self_employment",
    "pension_payment",
    "social_benefit",
    "allowance",
    "alimony",
    "interest",
    "dividend",
}
_EXPENSE = {
    "expense",
    "housing",
    "groceries_household",
    "transport",
    "healthcare",
    "insurance",
    "taxes",
    "childcare_education",
    "subscriptions",
    "leisure",
    "debt_payment",
    "other_expense",
}


@dataclass(frozen=True)
class _Transaction:
    transaction_id: str
    account_id: str
    evidence_id: str
    amount: Decimal
    currency: str
    booking_date: date
    source_assertions: tuple[AssertionRecord, ...]
    meaning_assertions: tuple[AssertionRecord, ...]
    classification: str
    transfer_counterpart: str | None


def _stable_uuid7(*parts: str) -> str:
    digest = bytearray(hashlib.sha256("\x1f".join(parts).encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x70
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _diagnostic(code: str, path: str, refs: tuple[Ref, ...] = ()) -> JsonObject:
    return cast(
        JsonObject,
        Diagnostic(
            code=code,
            message_key=f"diagnostic.{code.lower()}",
            severity="warning",
            path=path,
            params={},
            retryable=False,
            related_refs=refs,
        ).model_dump(mode="json"),
    )


def _covers(assertion: AssertionRecord, start: date, end: date) -> bool:
    return assertion.valid_time.start <= start and (
        assertion.valid_time.end_exclusive is None
        or assertion.valid_time.end_exclusive >= end
    )


def _active_on(assertion: AssertionRecord, on_date: date) -> bool:
    return assertion.valid_time.start <= on_date and (
        assertion.valid_time.end_exclusive is None
        or on_date < assertion.valid_time.end_exclusive
    )


def _classification(assertions: tuple[AssertionRecord, ...]) -> str:
    categories = {
        item.predicate.rsplit("/", 1)[-1]
        for item in assertions
        if item.predicate.startswith("domain.cashflow/classification/")
    }
    if "internal_transfer" in categories:
        return "internal_transfer"
    if categories & _INCOME:
        return next(iter(sorted(categories & _INCOME)))
    if categories & _EXPENSE:
        return next(iter(sorted(categories & _EXPENSE)))
    return "unclassified"


def _transactions(
    package: ValidatedPackage, request: AnalyzeRunRequest
) -> tuple[_Transaction, ...]:
    superseded = {
        item.supersedes
        for item in package.evidence.records
        if isinstance(item, SourceRecordEvidenceRecord) and item.supersedes is not None
    }
    result: list[_Transaction] = []
    for evidence in package.evidence.records:
        if (
            not isinstance(evidence, SourceRecordEvidenceRecord)
            or evidence.id in superseded
        ):
            continue
        source = SourceImportRecord.model_validate_json(
            package.source_records[evidence.record_path], strict=True
        )
        if not (
            request.period.start_date <= source.booking_date < request.period.end_date
        ):
            continue
        observed = tuple(
            item
            for item in package.assertions.records
            if item.knowledge_type == "observed"
            and any(ref.id == evidence.id for ref in item.provenance)
        )
        transaction_ids = {item.subject_ref.id for item in observed}
        if len(transaction_ids) != 1:
            raise ValueError("source evidence does not resolve to one transaction")
        transaction_id = next(iter(transaction_ids))
        meaning = tuple(
            item
            for item in package.assertions.records
            if item.subject_ref.id == transaction_id
            and item.knowledge_type != "observed"
            and _active_on(item, source.booking_date)
        )
        counterpart = next(
            (
                item.object_ref.id
                for item in meaning
                if item.predicate == "domain.cashflow/transfer_counterpart"
                and item.object_ref is not None
            ),
            None,
        )
        result.append(
            _Transaction(
                transaction_id,
                _stable_uuid7(evidence.source.adapter_id, source.source_id),
                evidence.id,
                Decimal(source.money.amount),
                source.money.currency,
                source.booking_date,
                observed,
                meaning,
                _classification(meaning),
                counterpart,
            )
        )
    return tuple(sorted(result, key=lambda item: item.transaction_id))


def _relations(
    package: ValidatedPackage, request: AnalyzeRunRequest, account_id: str
) -> tuple[AssertionRecord, ...]:
    predicate = (
        "domain.parties/household_allocation"
        if request.analysis_scope.scope_type == "household"
        else "domain.parties/account_holder"
    )
    return tuple(
        item
        for item in package.assertions.records
        if item.subject_ref.id == account_id
        and item.predicate == predicate
        and item.object_ref is not None
        and item.object_ref.id == request.analysis_scope.entity_id
        and (
            request.analysis_scope.scope_type == "person"
            or item.module_data.get("distribution")
            == {"complete": True, "shares": ["1"]}
        )
        and _covers(item, request.period.start_date, request.period.end_date)
    )


def _coverage(
    package: ValidatedPackage, request: AnalyzeRunRequest, account_id: str
) -> tuple[AssertionRecord, ...]:
    return tuple(
        item
        for item in package.assertions.records
        if item.subject_ref.id == account_id
        and item.predicate == "domain.accounts/transaction_coverage"
        and _covers(item, request.period.start_date, request.period.end_date)
    )


def _money(amount: Decimal, currency: str) -> JsonObject:
    return {"amount": f"{amount:.2f}", "currency": currency}


def _refs(ref_type: str, ids: set[str]) -> list[JsonObject]:
    return [{"ref_type": ref_type, "id": item_id} for item_id in sorted(ids)]


def _json(value: object) -> JsonValue:
    return cast(JsonValue, value)


def _component(
    package: ValidatedPackage,
    request: AnalyzeRunRequest,
    *,
    component_id: str,
    amount: Decimal | None,
    currency: str,
    status: str,
    transactions: tuple[_Transaction, ...],
    relation_assertions: tuple[AssertionRecord, ...],
    requirements: list[JsonObject],
    warnings: list[JsonObject],
    next_question: str | None,
    breakdown: list[JsonObject] | None = None,
) -> JsonObject:
    assertion_ids = {
        assertion.id
        for tx in transactions
        for assertion in (*tx.source_assertions, *tx.meaning_assertions)
    } | {item.id for item in relation_assertions}
    component: JsonObject = {
        "component_id": component_id,
        "status": status,
        "used_assertion_refs": _json(_refs("assertion", assertion_ids)),
        "used_evidence_refs": _json(
            _refs("evidence", {item.evidence_id for item in transactions})
        ),
        "assumptions": [],
        "calculation_steps": (
            [
                {
                    "step_id": f"{component_id}/sum",
                    "operation": "sum_posted_money",
                    "inputs": [
                        _money(item.amount, item.currency) for item in transactions
                    ],
                    "unrounded_result": _money(amount, currency),
                }
            ]
            if amount is not None
            else []
        ),
        "rounding": {"mode": "currency_default", "presented_decimals": 2},
        "requirements": _json(requirements),
        "blockers": [],
        "warnings": _json(warnings),
        "next_question": next_question,
        "explain_ref": {
            "ref_type": "analysis_component",
            "id": _stable_uuid7(
                package.manifest.generation_id,
                request.analysis_id,
                component_id,
                request.period.start_date.isoformat(),
                request.period.end_date.isoformat(),
            ),
        },
    }
    if amount is not None:
        component["value"] = _money(amount, currency)
    if breakdown is not None:
        component["breakdown"] = _json(breakdown)
    return component


def analyze_realized_monthly_cashflow(
    package: ValidatedPackage, request: AnalyzeRunRequest
) -> JsonObject:
    if request.context_id != package.manifest.context_id:
        raise ValueError("request context does not match the package")
    if not any(
        item.id == request.analysis_scope.entity_id
        and item.entity_type == request.analysis_scope.scope_type
        for item in package.entities.records
    ):
        raise ValueError("analysis scope does not resolve to the requested entity type")
    observed = _transactions(package, request)
    account_ids = {item.account_id for item in observed}
    relations = {
        account_id: _relations(package, request, account_id)
        for account_id in account_ids
    }
    coverages = {
        account_id: _coverage(package, request, account_id)
        for account_id in account_ids
    }
    included = tuple(item for item in observed if relations[item.account_id])
    included_currencies = {item.currency for item in included}
    if request.reporting_currency is not None:
        currency = request.reporting_currency.currency
    elif len(included_currencies) == 1:
        currency = next(iter(included_currencies))
    else:
        raise ValueError(
            "reporting currency is required when the included currency is ambiguous"
        )
    if any(item.currency != currency for item in included):
        raise ValueError("currency conversion is unavailable without exchange rates")
    missing_allocation = sorted(
        account_id for account_id in account_ids if not relations[account_id]
    )
    missing_coverage = sorted(
        account_id
        for account_id in account_ids
        if relations[account_id] and not coverages[account_id]
    )
    if not account_ids:
        missing_coverage = [request.analysis_scope.entity_id]
    relation_assertions = tuple(
        item
        for account_id in sorted(account_ids)
        for item in (*relations[account_id], *coverages[account_id])
    )
    requirements: list[JsonObject] = [
        {
            "requirement": "household_account_allocation",
            "state": "unallocated" if missing_allocation else "present",
            "impact": "Unknown account allocation makes household totals provisional.",
        },
        {
            "requirement": "transaction_coverage",
            "state": "missing" if missing_coverage else "present",
            "impact": "Incomplete transaction coverage makes month totals provisional.",
        },
    ]
    core_warnings: list[JsonObject] = []
    if missing_allocation:
        core_warnings.append(
            _diagnostic("ACCOUNT_ALLOCATION_NOT_DEMONSTRATED", "/analysis_scope")
        )
    if missing_coverage:
        core_warnings.append(
            _diagnostic("TRANSACTION_COVERAGE_NOT_DEMONSTRATED", "/period")
        )
    core_status = "complete" if not core_warnings else "provisional"
    next_question = (
        "Which accounts belong to this scope for the requested month?"
        if missing_allocation
        else (
            "Which included accounts have complete transaction coverage for this month?"
            if missing_coverage
            else None
        )
    )

    by_id = {item.transaction_id: item for item in included}
    paired: set[str] = set()
    for item in included:
        counterpart = by_id.get(item.transfer_counterpart or "")
        if (
            item.classification == "internal_transfer"
            and counterpart is not None
            and counterpart.classification == "internal_transfer"
            and counterpart.transfer_counterpart == item.transaction_id
        ):
            paired.update((item.transaction_id, counterpart.transaction_id))
    income = tuple(
        item
        for item in included
        if item.classification in _INCOME and item.transaction_id not in paired
    )
    expenses = tuple(
        item
        for item in included
        if item.classification in _EXPENSE and item.transaction_id not in paired
    )
    transfers = tuple(item for item in included if item.transaction_id in paired)
    unclassified = tuple(
        item
        for item in included
        if item.transaction_id not in paired
        and item not in income
        and item not in expenses
    )
    amounts = {
        "realized/income": sum((item.amount for item in income), Decimal()),
        "realized/expense": sum((abs(item.amount) for item in expenses), Decimal()),
        "realized/net_movement": sum((item.amount for item in included), Decimal()),
        "realized/internal_transfers": sum(
            (abs(item.amount) for item in transfers if item.amount < 0), Decimal()
        ),
        "realized/unclassified_movement": sum(
            (item.amount for item in unclassified), Decimal()
        ),
    }
    transaction_groups = {
        "realized/income": income,
        "realized/expense": expenses,
        "realized/net_movement": included,
        "realized/internal_transfers": transfers,
        "realized/unclassified_movement": unclassified,
    }
    components = [
        _component(
            package,
            request,
            component_id=component_id,
            amount=amount,
            currency=currency,
            status=core_status,
            transactions=transaction_groups[component_id],
            relation_assertions=relation_assertions,
            requirements=requirements,
            warnings=core_warnings,
            next_question=next_question,
        )
        for component_id, amount in amounts.items()
    ]
    unclassified_warnings = (
        [
            _diagnostic(
                "UNCLASSIFIED_TRANSACTION",
                "/components/realized/category_breakdown",
                tuple(
                    Ref(ref_type="entity", id=item.transaction_id)
                    for item in unclassified
                ),
            )
        ]
        if unclassified
        else []
    )
    breakdown: list[JsonObject] = [
        cast(
            JsonObject,
            {
                "category": category,
                "value": _money(
                    sum((item.amount for item in items), Decimal()), currency
                ),
                "transaction_refs": _refs(
                    "entity", {item.transaction_id for item in items}
                ),
            },
        )
        for category, items in sorted(
            {
                category: tuple(
                    item for item in included if item.classification == category
                )
                for category in {item.classification for item in included}
            }.items()
        )
    ]
    components.append(
        _component(
            package,
            request,
            component_id="realized/category_breakdown",
            amount=None,
            currency=currency,
            status="complete"
            if core_status == "complete" and not unclassified
            else "provisional",
            transactions=included,
            relation_assertions=relation_assertions,
            requirements=requirements,
            warnings=[*core_warnings, *unclassified_warnings],
            next_question=next_question,
            breakdown=breakdown,
        )
    )
    return {
        "analysis_id": request.analysis_id,
        "analysis_contract_version": request.analysis_contract_version,
        "analysis_scope": request.analysis_scope.model_dump(mode="json"),
        "as_of_date": request.as_of_date.isoformat(),
        "period": request.period.model_dump(mode="json"),
        "used_generation": package.manifest.generation_id,
        "result_id": _stable_uuid7(
            package.manifest.generation_id, request.model_dump_json()
        ),
        "components": _json(components),
    }
