from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal, localcontext
from typing import Any

import pytest
from pydantic import ValidationError

from topo_v2.cashflows import monthly_room
from topo_v2.engine import summarize
from topo_v2.models import Context, ContextQuery, Goal, Inventory, Transaction
from topo_v2.reading import read_context


def goal(**patch: Any) -> dict[str, Any]:
    return {"id": "renovation", "name": "Verbouwing", "target_amount": "10000", **patch}


def context(**patch: Any) -> Context:
    return Context.model_validate(
        {
            "schema_version": "topo2.context/7",
            "context_id": "synthetic",
            "goals": [goal()],
            **patch,
        }
    )


@pytest.mark.parametrize(
    ("reserved", "remaining"),
    [
        (None, None),
        ("0", Decimal(10000)),
        ("4000", Decimal(6000)),
        ("10000", Decimal(0)),
        ("12000", Decimal(0)),
    ],
)
def test_remaining_unknown_zero_and_overreservation(
    reserved: str | None, remaining: Decimal | None
) -> None:
    result = summarize(context(goals=[goal(reserved_amount=reserved)]))
    assert result.goals[0].remaining_amount == remaining
    assert result.goals[0].reserved_amount == (
        Decimal(reserved) if reserved is not None else None
    )
    assert result.reservation_comparison[0].unknown_reservation_ids == (
        ["renovation"] if reserved is None else []
    )
    assert result.reservation_comparison[0].known_free_total is None
    assert result.reservation_comparison[0].possible_excess is None
    assert result.reservation_comparison[0].coverage_unknown


@pytest.mark.parametrize(
    "patch",
    [
        {"target_amount": "0"},
        {"target_amount": "-1"},
        {"reserved_amount": "-1"},
        {"monthly_contribution": "-1"},
        {"reserved_amount": 1},
        {"monthly_contribution": 1.2},
        {"reserved_amount": "NaN"},
        {"monthly_contribution": "Infinity"},
        {"reserved_amount": "0.000000001"},
        {"monthly_contribution": "1" * 29},
        {"priority": "urgent"},
        {"note": " "},
        {"note": "x" * 257},
    ],
)
def test_invalid_goal_enrichments(patch: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Goal.model_validate(goal(**patch))


@pytest.mark.parametrize("priority", [None, "low", "normal", "high"])
def test_optional_metadata_and_large_exact_amounts(priority: str | None) -> None:
    with localcontext() as arithmetic:
        arithmetic.prec = 4
        result = summarize(
            context(
                goals=[
                    goal(
                        target_amount="99999999999999999999.12345678",
                        reserved_amount="0.00000001",
                        monthly_contribution="9999999999999999999999999999",
                        priority=priority,
                        note="x" * 256,
                    )
                ]
            )
        ).goals[0]
    assert result.remaining_amount == Decimal("99999999999999999999.12345677")
    assert result.priority == priority and result.note == "x" * 256
    assert result.monthly_contribution == Decimal(9999999999999999999999999999)


def test_linked_value_is_separate_and_missing_links_do_not_block_remaining() -> None:
    data = context(
        accounts=[
            {
                "id": "bank",
                "label": "Bank",
                "type": "savings",
                "balance": "3000",
                "as_of": "2026-10-15",
            }
        ],
        assets=[{"id": "asset", "label": "Asset", "type": "other"}],
        goals=[
            goal(
                reserved_amount="4000",
                account_ids=["bank", "bank"],
                asset_ids=["asset"],
            ),
            goal(id="old", account_ids=["bank"]),
        ],
    )
    enriched, old = summarize(data).goals
    assert enriched.remaining_amount == 6000 and old.remaining_amount is None
    assert enriched.linked_value.known_amount == enriched.known_amount == 3000
    assert enriched.linked_value.percentage == enriched.percentage == 30
    assert (
        enriched.linked_value.missing_ids == ["asset"]
        and not enriched.linked_value.complete
    )
    assert old.reserved_amount is None and old.linked_value.known_amount == 3000
    compact = read_context(data, ContextQuery())
    assert compact.summary.goals[0].remaining_amount == 6000


def test_currency_comparison_excess_unknown_inventory_and_negative_balances() -> None:
    data = context(
        accounts=[
            {
                "id": "bank",
                "label": "Bank",
                "type": "savings",
                "balance": "3000",
                "as_of": "2026-10-15",
                "availability": "free",
            },
            {
                "id": "overdraft",
                "label": "Bank",
                "type": "payment",
                "balance": "-1000",
                "as_of": "2026-10-15",
                "availability": "free",
            },
            {"id": "unknown", "label": "Bank", "type": "payment"},
            {
                "id": "dollar",
                "label": "Bank",
                "type": "savings",
                "balance": "10",
                "as_of": "2026-10-15",
                "availability": "free",
                "currency": "USD",
            },
        ],
        goals=[
            goal(reserved_amount="4000"),
            goal(id="other"),
            goal(id="usd", currency="USD", reserved_amount="0"),
        ],
    )
    eur, usd = summarize(data).reservation_comparison
    assert eur.known_reserved_total == 4000 and eur.known_free_total == 3000
    assert eur.possible_excess and eur.coverage_unknown
    assert eur.unknown_reservation_ids == ["other"]
    assert eur.missing_value_ids == eur.unknown_availability_ids == ["unknown"]
    assert usd.known_reserved_total == 0 and usd.known_free_total == 10
    assert not usd.possible_excess and usd.coverage_unknown
    # Complete declarations cannot fill missing records or amounts.
    data.inventories = [
        Inventory.model_validate(
            {"id": domain, "status": "complete", "checked_on": "2026-10-15"}
        )
        for domain in ("accounts", "assets", "goals")
    ]
    eur, usd = summarize(data).reservation_comparison
    assert eur.coverage_unknown and not usd.coverage_unknown
    assert (
        not usd.possible_excess
    )  # Within known free value, never a coverage guarantee.


def test_goal_intent_does_not_scan_transactions_or_change_monthly_room() -> None:
    class UnreadableTransactions(list[Transaction]):
        def __iter__(self) -> Iterator[Transaction]:
            raise AssertionError("Goal calculations must not scan transactions")

    data = context(cashflow_settings={"EUR": {"minimum_reserve": "5000"}})
    data.transactions = UnreadableTransactions()
    before = monthly_room(
        data.cashflows, data.cashflow_settings, None, date(2026, 10, 15)
    )
    data.goals = [
        Goal.model_validate(
            goal(id=f"goal_{i}", reserved_amount="4000", monthly_contribution="300")
        )
        for i in range(100)
    ]
    assert len(summarize(data).goals) == 100
    compact = read_context(
        data, ContextQuery(reference_date=before.reference_date, max_age_days=30)
    )
    assert compact.monthly_room == before
    assert compact.summary.reservation_comparison[0].known_reserved_total == 400000


@pytest.mark.parametrize("version", range(1, 7))
def test_goal_enrichment_requires_v7(version: int) -> None:
    with pytest.raises(ValidationError, match="Goal enrichments require"):
        context(
            schema_version=f"topo2.context/{version}", goals=[goal(reserved_amount="0")]
        )
