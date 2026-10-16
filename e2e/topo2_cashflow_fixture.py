"""Agent-side preparation for explicit synthetic sources; no engine inference."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from topo2_input_fixture import first_request
from topo2_wealth_fixture import wealth_request

CASHFLOW_SOURCE = (
    Path(__file__).parent / "fixtures" / "topo2-cashflows" / "verwachtingen.txt"
)


def source_request() -> dict[str, Any]:
    request = first_request()
    kinds = ["income", "internal_transfer", "internal_transfer", "expense"]
    for record, kind in zip(request["transactions"]["add"], kinds, strict=True):
        record["kind"] = kind
    for section, operations in wealth_request().items():
        request.setdefault(section, {}).setdefault("add", []).extend(operations["add"])
    savings = next(
        item for item in request["accounts"]["add"] if item["id"] == "savings"
    )
    savings.update(availability="free", availability_note="Synthetische toelichting")
    request["assets"]["add"][0].update(
        availability="restricted", availability_note="Woning"
    )
    return request


def prepared_expectations(aggregate: dict[str, Any]) -> dict[str, Any]:
    # This is a fixture transcription. The explicit source supplies frequency and
    # ranges; the export's one purchase never establishes a weekly pattern.
    total = next(item for item in aggregate["totals"] if item["currency"] == "EUR")
    assert Decimal(total["income"]) == 3000
    assert Decimal(total["expenses"]) == Decimal("85.50")
    assert total["internal_transfers"]["count"] == 2
    groceries = next(
        item for item in aggregate["groups"] if item["category"] == "Boodschappen"
    )
    assert Decimal(80) <= Decimal(groceries["expenses"]) <= Decimal(120)
    base = {
        "start_date": "2026-10-14",
        "currency": "EUR",
        "kind": "expense",
        "frequency": "monthly",
        "source": "Synthetische verwachtingen.txt",
    }
    return {
        "cashflows": {
            "add": [
                {
                    **base,
                    "id": "salary",
                    "label": "Salaris",
                    "kind": "income",
                    "amount": total["income"],
                    "frequency": "four_weekly",
                    "category": "Inkomen",
                },
                {
                    **base,
                    "id": "groceries",
                    "label": "Boodschappen",
                    "frequency": "weekly",
                    "amount": {"lower": "80", "upper": "120"},
                    "category": "Boodschappen",
                    "source": "bank.csv: supermarkt; verwachtingen.txt: weekband; exclusief hypotheek/verzekering/abonnement",
                },
                {
                    **base,
                    "id": "housing",
                    "label": "Hypotheekbetaling",
                    "amount": "900",
                    "debt_id": "mortgage",
                },
                {
                    **base,
                    "id": "insurance",
                    "label": "Verzekering",
                    "amount": "1200",
                    "frequency": "yearly",
                },
                {
                    **base,
                    "id": "subscription",
                    "label": "Abonnement",
                    "amount": "75",
                    "frequency": "quarterly",
                },
                {
                    **base,
                    "id": "loan_payment",
                    "label": "Onbekende leningbetaling",
                    "amount": None,
                    "debt_id": "unknown_loan",
                },
                {
                    **base,
                    "id": "dollar_income",
                    "label": "Dollarinkomen",
                    "kind": "income",
                    "amount": "50",
                    "currency": "USD",
                },
                {
                    **base,
                    "id": "old",
                    "label": "Oude last",
                    "amount": "1000",
                    "start_date": "2026-01-01",
                    "end_date": "2026-10-13",
                },
                {
                    **base,
                    "id": "future",
                    "label": "Nieuwe last",
                    "amount": "1000",
                    "start_date": "2026-10-15",
                },
            ]
        },
        "cashflow_settings": {
            "EUR": {
                "minimum_reserve": "5000",
                "note": "Boodschappen flexibel; buffer heeft prioriteit",
            }
        },
    }
