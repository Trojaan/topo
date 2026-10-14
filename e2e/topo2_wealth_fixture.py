"""Explicit transcription of synthetic vermogen.txt; no runtime source adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

WEALTH_SOURCE = Path(__file__).parent / "fixtures" / "topo2-wealth" / "vermogen.txt"


def wealth_request() -> dict[str, Any]:
    dated = {"as_of": "2026-10-04"}
    return {
        "accounts": {
            "add": [
                {
                    "id": "savings",
                    "label": "Extra sparen",
                    "type": "savings",
                    "balance": "10000",
                    **dated,
                },
                {
                    "id": "overdrawn",
                    "label": "Extra betaal",
                    "type": "payment",
                    "balance": "-500",
                    **dated,
                },
                {
                    "id": "dollars",
                    "label": "Dollarrekening",
                    "type": "payment",
                    "balance": "1000",
                    "currency": "USD",
                    **dated,
                },
            ]
        },
        "assets": {
            "add": [
                {
                    "id": "home",
                    "label": "Woning",
                    "type": "property",
                    "value": "300000",
                    **dated,
                },
            ]
        },
        "debts": {
            "add": [
                {
                    "id": "mortgage",
                    "label": "Hypotheek",
                    "type": "mortgage",
                    "amount": "200000",
                    "interest_rate": "3.5",
                    "end_date": "2050-10-04",
                    **dated,
                },
                {
                    "id": "overdraft",
                    "label": "Dezelfde roodstand",
                    "type": "overdraft",
                    "amount": "500",
                    "account_id": "overdrawn",
                    **dated,
                },
                {
                    "id": "usd_loan",
                    "label": "Dollarlening",
                    "type": "loan",
                    "amount": "100",
                    "currency": "USD",
                    **dated,
                },
                {"id": "unknown_loan", "label": "Onbekende lening", "type": "loan"},
            ]
        },
    }
