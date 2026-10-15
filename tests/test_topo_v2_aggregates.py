from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

import pytest
from pydantic import ValidationError

from topo_v2.models import Context, TransactionAggregateQuery, TransactionQuery
from topo_v2.transactions import aggregate_transactions, select_transactions


def fixture(**overrides: Any) -> Context:
    records = [
        ("salary", "3000", "income", "Salaris"),
        ("purchase", "-100", "expense", "Winkel"),
        ("refund", "20", "expense", "Winkel"),
        ("recovery", "-50", "income", "Salaris"),
        ("transfer", "-500", "internal_transfer", None),
        ("unclassified", "-10", None, "Salaris"),
        ("explicit_unknown", "5", "unknown", None),
        ("zero", "0", "expense", None),
    ]
    return Context.model_validate(
        {
            "schema_version": "topo2.context/5",
            "context_id": "synthetic",
            "accounts": [
                {"id": "bank", "label": "Bank", "type": "payment"},
                {"id": "empty", "label": "Empty", "type": "savings"},
            ],
            "transactions": [
                {
                    "id": ident,
                    "amount": amount,
                    "kind": kind,
                    "category": category,
                    "account_id": "bank",
                    "currency": "EUR",
                    "booking_date": "2026-10-01",
                    "description": "Synthetic",
                }
                for ident, amount, kind, category in records
            ],
            **overrides,
        }
    )


def test_signed_economic_totals_and_account_movement_reconcile() -> None:
    context = fixture()
    result = aggregate_transactions(
        context, TransactionAggregateQuery(group_by=["month", "category"])
    )
    total = result.totals[0]
    assert (total.receipts, total.outflows, total.net_movement) == (
        Decimal(3025),
        Decimal(660),
        Decimal(2365),
    )
    assert (total.income, total.expenses, total.classified_net_cashflow) == (
        Decimal(2950),
        Decimal(80),
        Decimal(2870),
    )
    assert total.internal_transfers.count == 1
    assert total.internal_transfers.net_movement == -500
    assert total.unknown.count == total.unknown_count == 2
    assert total.unknown.net_movement == -5
    assert total.classified_count == 6 and total.classification_complete is False
    assert (
        total.net_movement
        == total.classified_net_cashflow
        + total.internal_transfers.net_movement
        + total.unknown.net_movement
    )
    for field in (
        "count",
        "receipts",
        "outflows",
        "net_movement",
        "income",
        "expenses",
        "classified_net_cashflow",
    ):
        assert sum(getattr(group, field) for group in result.groups) == getattr(
            total, field
        )
    assert result.groups[0].category is None
    assert all(group.month == "2026-10" for group in result.groups)


def test_combined_filters_match_detail_and_empty_selection() -> None:
    context = fixture()
    filters = {
        "from_date": "2026-10-01",
        "to_date": "2026-10-01",
        "category": "Winkel",
        "account_id": "bank",
        "currency": "EUR",
        "min_amount": "-100",
        "max_amount": "20",
        "search": "synthetic",
    }
    aggregate = aggregate_transactions(
        context, TransactionAggregateQuery.model_validate(filters)
    )
    detail = select_transactions(
        context.transactions, TransactionQuery.model_validate(filters)
    )
    assert aggregate.count == detail.total == 2
    assert aggregate.totals[0].net_movement == sum(
        record.amount for record in detail.records
    )
    empty = aggregate_transactions(context, TransactionAggregateQuery(currency="USD"))
    assert empty.count == 0 and empty.totals == empty.groups == []
    assert empty.classification_complete is None
    assert [item.account_id for item in empty.coverage] == ["bank", "empty"]


def test_currencies_precision_negative_expenses_and_unknown_zero() -> None:
    records = fixture().transactions[:3]
    records[0].amount = Decimal(9999999999999999999999999999)
    records[1].amount = Decimal(9999999999999999999999999999)
    records[1].kind = "income"
    records[2].amount = Decimal("0.00000001")
    records[2].kind = "income"
    usd = records[2].model_copy(
        update={"id": "usd", "currency": "USD", "kind": None, "amount": Decimal(0)}
    )
    context = fixture(transactions=[*records, usd])
    with localcontext() as arithmetic:
        arithmetic.prec = 6
        result = aggregate_transactions(context, TransactionAggregateQuery())
    assert result.totals[0].income == Decimal("19999999999999999999999999998.00000001")
    assert result.totals[0].classification_complete is True
    assert (
        result.totals[1].unknown_count == 1
        and result.totals[1].classification_complete is False
    )
    refund_only = fixture(transactions=[fixture().transactions[2]])
    assert (
        aggregate_transactions(refund_only, TransactionAggregateQuery())
        .totals[0]
        .expenses
        == -20
    )


@pytest.mark.parametrize(
    ("intervals", "expected"),
    [
        ([], "unknown"),
        ([(1, 5)], "partial"),
        ([(1, 5), (6, 10)], "complete"),
        ([(1, 5), (7, 10)], "partial"),
        ([(1, 7), (5, 10)], "complete"),
        ([(11, 15)], "unknown"),
        ([(1, 10)], "complete"),
    ],
)
def test_declared_coverage_union_independent_of_classification(
    intervals: list[tuple[int, int]], expected: str
) -> None:
    declarations = [
        {
            "id": f"coverage_{i}",
            "account_id": "bank",
            "from_date": f"2026-10-{start:02}",
            "to_date": f"2026-10-{end:02}",
            "checked_on": "2026-10-14",
        }
        for i, (start, end) in enumerate(intervals)
    ]
    context = fixture(transaction_coverage=declarations)
    query = TransactionAggregateQuery.model_validate(
        {"from_date": "2026-10-01", "to_date": "2026-10-10", "currency": "USD"}
    )
    result = aggregate_transactions(context, query)
    assert result.coverage[0].status == expected
    assert result.coverage[1].status == "unknown"
    assert result.classification_complete is None
    unbounded = aggregate_transactions(
        context, TransactionAggregateQuery(account_id="bank")
    )
    assert unbounded.coverage[0].status == ("declared" if intervals else "unknown")


def test_validation_and_maximum_date() -> None:
    with pytest.raises(ValidationError, match="unique"):
        TransactionAggregateQuery(group_by=["month", "month"])
    with pytest.raises(ValidationError, match="from_date"):
        TransactionAggregateQuery.model_validate(
            {"from_date": "2026-10-10", "to_date": "2026-10-01"}
        )
    context = fixture(
        transaction_coverage=[
            {
                "id": "coverage",
                "account_id": "bank",
                "from_date": "9999-12-31",
                "to_date": "9999-12-31",
                "checked_on": "2026-10-14",
            }
        ]
    )
    assert (
        aggregate_transactions(
            context,
            TransactionAggregateQuery.model_validate(
                {"from_date": "9999-12-31", "to_date": "9999-12-31"}
            ),
        )
        .coverage[0]
        .status
        == "complete"
    )
    assert (
        aggregate_transactions(context, TransactionAggregateQuery(account_id="missing"))
        .coverage[0]
        .status
        == "unknown"
    )


def test_groups_are_deterministic_under_reordered_records() -> None:
    context = fixture()
    query = TransactionAggregateQuery(group_by=["month", "category"])
    forward = aggregate_transactions(context, query)
    context.transactions.reverse()
    backward = aggregate_transactions(
        context, TransactionAggregateQuery(group_by=["category", "month"])
    )
    assert forward.totals == backward.totals and forward.groups == backward.groups
