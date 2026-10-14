"""Agent-side conversion for one documented synthetic source layout, not an adapter."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "topo2-input"
ACCOUNT_IDS = {"SYN-BETAAL": "syn_betaal", "SYN-SPAAR": "syn_spaar"}


def convert_export(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {
                "id": "syn_" + row["Bankreferentie"],
                "account_id": ACCOUNT_IDS[row["Rekening"]],
                "booking_date": row["Boekdatum"],
                "amount": row["Bedrag"].replace(",", "."),
                "currency": row["Valuta"],
                "description": row["Omschrijving"],
            }
            for row in csv.DictReader(handle, delimiter=";")
        ]


def first_request() -> dict[str, Any]:
    # Independently read from the PNG sources during the recorded agent session.
    accounts = [
        {
            "id": "syn_betaal",
            "label": "Betaalrekening",
            "type": "payment",
            "balance": "2514.50",
            "currency": "EUR",
            "as_of": "2026-10-04",
        },
        {
            "id": "syn_spaar",
            "label": "Spaarrekening",
            "type": "savings",
            "balance": "6400.00",
            "currency": "EUR",
            "as_of": "2026-10-04",
        },
    ]
    categories = {
        "syn_SYN001": "Inkomen",
        "syn_SYN002": "Eigen overboeking",
        "syn_SYN003": "Eigen overboeking",
        "syn_SYN004": "Boodschappen",
    }
    transactions = [
        {
            **record,
            "category": categories[record["id"]],
            "source": "Synthetische bankexport",
        }
        for record in convert_export(FIXTURES / "bank.csv")
    ]
    return {
        "contract_version": "topo2.cli/3",
        "accounts": {"add": accounts},
        "goals": {
            "add": [
                {
                    "id": "syn_buffer",
                    "name": "Buffer",
                    "target_amount": "10000",
                    "target_date": "2027-12-31",
                    "currency": "EUR",
                    "account_ids": ["syn_spaar"],
                }
            ]
        },
        "transactions": {"add": transactions},
    }


def export_change(
    current: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    # Full-record change.update: explicitly carry forward the known enrichment.
    known = {record["id"]: record for record in current["transactions"]}
    return {
        "contract_version": "topo2.cli/3",
        "transactions": {
            "add": [row for row in rows if row["id"] not in known],
            "update": [
                {**known[row["id"]], **row} for row in rows if row["id"] in known
            ],
        },
    }
