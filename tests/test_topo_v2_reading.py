from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from topo_v2 import engine, storage
from topo_v2.models import Account, ChangeRequest, Context, ContextQuery
from topo_v2.reading import read_context


def test_goal_uncertainty_is_limited_to_its_links() -> None:
    context = Context.model_validate(
        {
            "context_id": "synthetic",
            "accounts": [
                {
                    "id": "known",
                    "label": "Known",
                    "type": "savings",
                    "balance": "0",
                    "as_of": "2026-10-14",
                },
                {"id": "missing", "label": "Unknown", "type": "payment"},
            ],
            "assets": [
                {
                    "id": "usd",
                    "label": "USD",
                    "type": "cash",
                    "value": "20",
                    "currency": "USD",
                    "as_of": "2026-09-01",
                }
            ],
            "goals": [
                {
                    "id": "goal",
                    "name": "Buffer",
                    "target_amount": "100",
                    "account_ids": ["known"],
                }
            ],
        }
    )
    result = read_context(
        context, ContextQuery(reference_date=date(2026, 10, 14), max_age_days=30)
    )
    assert result.summary.goals[0].complete
    assert result.summary.goals[0].known_amount == 0
    assert not any(
        item.outcome == "goal_progress"
        and item.code in ("missing_values", "stale_values")
        for item in result.limitations
    )
    assert [
        (item.currency, item.known_total, item.missing_ids)
        for item in result.summary.subtotals
    ] == [("EUR", Decimal(0), ["missing"]), ("USD", 20, [])]
    assert any(
        item.code == "stale_values" and item.ids == ["usd"]
        for item in result.limitations
    )


def test_empty_complete_inventory_and_schema_boundary() -> None:
    declaration = {"id": "accounts", "status": "complete", "checked_on": "2026-10-14"}
    with pytest.raises(ValidationError, match="require topo2.context/3"):
        Context.model_validate(
            {"context_id": "synthetic", "inventories": [declaration]}
        )
    context = Context.model_validate(
        {
            "schema_version": "topo2.context/3",
            "context_id": "synthetic",
            "inventories": [declaration],
        }
    )
    result = read_context(context, ContextQuery())
    assert result.summary.subtotals == []
    assert result.inventories[0].status == "complete"
    assert not any(item.ids == ["accounts"] for item in result.limitations)
    with pytest.raises(ValidationError, match="domains must be unique"):
        Context.model_validate(
            {**context.model_dump(), "inventories": [declaration, declaration]}
        )


def test_declarations_share_token_and_preserve_data(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    engine.initialize(path)
    request = ChangeRequest.model_validate(
        {
            "accounts": {"add": [{"id": "bank", "label": "Bank", "type": "payment"}]},
            "inventories": {
                "add": [
                    {"id": "accounts", "status": "partial", "checked_on": "2026-10-14"}
                ]
            },
            "transaction_coverage": {
                "add": [
                    {
                        "id": "period",
                        "account_id": "bank",
                        "from_date": "2026-10-14",
                        "to_date": "2026-10-14",
                        "checked_on": "2026-10-14",
                    },
                    {
                        "id": "next",
                        "account_id": "bank",
                        "from_date": "2026-10-16",
                        "to_date": "2026-10-17",
                        "checked_on": "2026-10-14",
                    },
                ]
            },
        }
    )
    preview = engine.change(path, request)
    request.confirmation_token = preview.confirmation_token
    changed = request.model_copy(deep=True)
    changed.inventories.add[0].status = "complete"
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, changed)
    engine.change(path, request)
    before = storage.read(path)[1]
    update = ChangeRequest.model_validate(
        {
            "accounts": {
                "update": [
                    Account(id="bank", label="New name", type="payment").model_dump()
                ]
            }
        }
    )
    update.confirmation_token = engine.change(path, update).confirmation_token
    engine.change(path, update)
    after = storage.read(path)[1]
    assert (
        after.inventories == before.inventories
        and after.transaction_coverage == before.transaction_coverage
    )
    result = read_context(after, ContextQuery())
    assert len(result.transaction_coverage[0].intervals) == 2
    # A gap remains a gap; no transactions or inferred merged interval appears.
    assert (
        result.transaction_coverage[0].intervals[0].to_date.isoformat() == "2026-10-14"
    )
    remove = ChangeRequest.model_validate(
        {
            "accounts": {"delete": ["bank"]},
            "inventories": {"delete": ["accounts"]},
            "transaction_coverage": {"delete": ["period", "next"]},
        }
    )
    remove.confirmation_token = engine.change(path, remove).confirmation_token
    engine.change(path, remove)
    assert storage.read(path)[1].schema_version == "topo2.context/3"
    assert (
        read_context(storage.read(path)[1], ContextQuery()).inventories[0].status
        == "unknown"
    )
