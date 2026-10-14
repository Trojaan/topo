from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from topo_v2.engine import summarize
from topo_v2.models import Context, ContextQuery, Debt
from topo_v2.reading import read_context


def fixture() -> dict[str, Any]:
    return {
        "schema_version": "topo2.context/4",
        "context_id": "synthetic",
        "accounts": [
            {
                "id": "savings",
                "label": "Sparen",
                "type": "savings",
                "balance": "10000",
                "as_of": "2026-10-04",
            },
            {
                "id": "bank",
                "label": "Bank",
                "type": "payment",
                "balance": "-500",
                "as_of": "2026-10-04",
            },
            {
                "id": "usd",
                "label": "Dollar",
                "type": "payment",
                "balance": "1000",
                "currency": "USD",
                "as_of": "2026-10-04",
            },
        ],
        "assets": [
            {
                "id": "home",
                "label": "Woning",
                "type": "property",
                "value": "300000",
                "as_of": "2026-10-04",
            }
        ],
        "debts": [
            {
                "id": "mortgage",
                "label": "Hypotheek",
                "type": "mortgage",
                "amount": "200000",
                "as_of": "2026-10-04",
            }
        ],
    }


def test_net_wealth_and_explicit_overdraft_once() -> None:
    data = fixture()
    initial = summarize(Context.model_validate(data))
    eur, usd = initial.net_wealth.subtotals
    assert (eur.known_total, usd.known_total) == (Decimal(109500), Decimal(1000))
    assert eur.complete and not eur.inventory_complete
    assert eur.known_account_asset_total == 309500 and eur.known_debt_total == 200000
    data["debts"].append(
        {
            "id": "overdraft",
            "label": "Rood",
            "type": "overdraft",
            "amount": "500",
            "as_of": "2026-10-04",
            "account_id": "bank",
        }
    )
    result = summarize(Context.model_validate(data))
    assert result.net_wealth.subtotals[0].known_total == eur.known_total
    assert result.net_wealth.subtotals[0].linked_debt_ids == ["overdraft"]
    assert result.subtotals == initial.subtotals


@pytest.mark.parametrize("status", [None, "unknown", "partial", "complete"])
def test_missing_values_and_inventory_are_separate(status: str | None) -> None:
    data = fixture()
    data["debts"].append({"id": "missing_debt", "label": "Lening", "type": "loan"})
    data["assets"][0]["value"] = None
    if status:
        data["inventories"] = [
            {"id": domain, "status": status, "checked_on": "2026-10-14"}
            for domain in ("accounts", "assets", "debts")
        ]
    result = read_context(
        Context.model_validate(data),
        ContextQuery(reference_date=date(2026, 10, 14), max_age_days=9),
    )
    eur = result.summary.net_wealth.subtotals[0]
    assert eur.known_total == -190500
    assert eur.missing_ids == ["home", "missing_debt"] and not eur.complete
    assert eur.inventory_complete == (status == "complete")
    assert result.summary.net_wealth.inventories[2].status == (status or "unknown")
    assert any(
        item.outcome == "net_wealth"
        and item.code == "missing_values"
        and "missing_debt" in item.ids
        for item in result.limitations
    )
    assert any(
        item.outcome == "net_wealth"
        and item.code == "stale_values"
        and "mortgage" in item.ids
        for item in result.limitations
    )
    assert not any(
        item.outcome == "wealth_overview" and "missing_debt" in item.ids
        for item in result.limitations
    )
    assert not any(
        item.outcome == "net_wealth" and item.code == "not_supported"
        for item in result.limitations
    )


def test_empty_zero_and_debt_only() -> None:
    empty = Context(context_id="synthetic")
    assert summarize(empty).net_wealth.subtotals == []
    assert all(
        item.status == "unknown" for item in summarize(empty).net_wealth.inventories
    )
    data: dict[str, Any] = {
        "schema_version": "topo2.context/4",
        "context_id": "synthetic",
        "debts": [
            {
                "id": "loan",
                "label": "Lening",
                "type": "loan",
                "amount": "0",
                "as_of": "2026-10-14",
            }
        ],
        "inventories": [
            {"id": "debts", "status": "complete", "checked_on": "2026-10-14"}
        ],
    }
    result = summarize(Context.model_validate(data))
    assert result.subtotals == []
    assert result.net_wealth.subtotals[0].known_total == 0
    assert result.net_wealth.subtotals[0].complete
    data["debts"][0]["amount"] = "12.00000001"
    assert summarize(Context.model_validate(data)).net_wealth.subtotals[
        0
    ].known_total == Decimal("-12.00000001")
    data["debts"][0]["amount"] = None
    assert not summarize(Context.model_validate(data)).net_wealth.subtotals[0].complete


def test_optional_availability_does_not_infer_liquidity() -> None:
    data = fixture()
    data["accounts"][0]["availability"] = "free"
    data["accounts"][1]["availability"] = "free"
    data["assets"][0]["availability"] = "restricted"
    data["assets"].append(
        {
            "id": "unknown_value",
            "label": "Ontbreekt",
            "type": "cash",
            "availability": "free",
        }
    )
    eur, usd = summarize(Context.model_validate(data)).availability
    assert (eur.known_free_total, eur.known_restricted_total) == (
        Decimal(10000),
        Decimal(300000),
    )
    assert eur.missing_ids == ["unknown_value"]
    assert usd.unknown_availability_ids == ["usd"] and usd.known_free_total == 0
    data["assets"][0].pop("availability")
    assert (
        "home"
        in summarize(Context.model_validate(data))
        .availability[0]
        .unknown_availability_ids
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"amount": "-1"},
        {"amount": "1"},
        {"interest_rate": "-1"},
        {"account_id": "bank"},
        {"amount": 1},
        {"amount": "NaN"},
    ],
)
def test_invalid_debt_fields(patch: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Debt.model_validate({"id": "loan", "label": "Lening", "type": "loan", **patch})


@pytest.mark.parametrize(
    "version", ["topo2.context/1", "topo2.context/2", "topo2.context/3"]
)
def test_new_fields_require_version_four(version: str) -> None:
    data = fixture()
    data["schema_version"] = version
    with pytest.raises(ValidationError, match="require topo2.context/4"):
        Context.model_validate(data)
    data["debts"] = []
    data["accounts"][0]["availability_note"] = "Vrijwillige toelichting"
    with pytest.raises(ValidationError, match="require topo2.context/4"):
        Context.model_validate(data)
