"""Partial changes use synthetic records and retain the human preview boundary."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from topo_v2 import engine, storage
from topo_v2.models import ChangeRequest


def submit(path: Path, data: dict[str, Any]) -> None:
    request = ChangeRequest.model_validate(data)
    preview = engine.change(path, request)
    engine.change(
        path,
        request.model_copy(update={"confirmation_token": preview.confirmation_token}),
    )


def fixture(path: Path) -> None:
    engine.initialize(path)
    submit(
        path,
        {
            "accounts": {
                "add": [
                    {
                        "id": "bank",
                        "label": "Synthetic",
                        "type": "savings",
                        "balance": "20",
                        "as_of": "2026-10-17",
                        "availability": "free",
                        "availability_note": "Synthetic note",
                    }
                ]
            },
            "goals": {
                "add": [
                    {
                        "id": "goal",
                        "name": "Synthetic",
                        "target_amount": "100",
                        "reserved_amount": "10",
                        "account_ids": ["bank"],
                    }
                ]
            },
        },
    )


def test_patch_preserves_fields_and_noop_bytes(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    fixture(path)
    request = ChangeRequest.model_validate(
        {"accounts": {"patch": [{"id": "bank", "balance": "30"}]}}
    )
    raw = path.read_bytes()
    preview = engine.change(path, request)
    assert preview.status == "preview" and len(preview.changes) == 1
    assert path.read_bytes() == raw
    submit(path, {"accounts": {"patch": [{"id": "bank", "balance": "30"}]}})
    account = storage.read(path)[1].accounts[0]
    assert str(account.balance) == "30" and account.availability == "free"
    assert account.availability_note == "Synthetic note"
    raw, modified = path.read_bytes(), path.stat().st_mtime_ns
    assert engine.change(path, request).status == "unchanged"
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == modified
    with pytest.raises(engine.StaleConfirmation):
        engine.change(
            path,
            request.model_copy(
                update={"confirmation_token": preview.confirmation_token}
            ),
        )


def test_patch_clear_and_list_replacement(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    fixture(path)
    submit(
        path,
        {
            "accounts": {"patch": [{"id": "bank", "availability_note": None}]},
            "goals": {
                "patch": [{"id": "goal", "account_ids": [], "reserved_amount": None}]
            },
        },
    )
    context = storage.read(path)[1]
    assert context.accounts[0].availability_note is None
    assert context.accounts[0].availability == "free"
    assert (
        context.goals[0].account_ids == [] and context.goals[0].reserved_amount is None
    )


@pytest.mark.parametrize(
    "record",
    [
        {"id": "bank"},
        {"id": "bank", "label": None},
        {"id": "bank", "surprise": "x"},
        {"id": "bank", "balance": 2},
    ],
)
def test_invalid_patch_shape(record: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ChangeRequest.model_validate({"accounts": {"patch": [record]}})


@pytest.mark.parametrize(
    "data",
    [
        {"accounts": {"patch": [{"id": "absent", "balance": "5"}]}},
        {"accounts": {"patch": [{"id": "bank", "balance": "5"}], "delete": ["bank"]}},
        {
            "accounts": {
                "patch": [{"id": "bank", "balance": "5"}, {"id": "bank", "label": "x"}]
            }
        },
        {"accounts": {"patch": [{"id": "bank", "as_of": None}]}},
        {"goals": {"patch": [{"id": "goal", "account_ids": ["absent"]}]}},
    ],
)
def test_invalid_effective_patch_never_writes(
    tmp_path: Path, data: dict[str, Any]
) -> None:
    path = tmp_path / "synthetic.json"
    fixture(path)
    raw = path.read_bytes()
    with pytest.raises((ValidationError, engine.ChangeError)):
        engine.change(path, ChangeRequest.model_validate(data))
    assert path.read_bytes() == raw


def test_patch_serialization_preserves_omission_and_token_binding(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.json"
    fixture(path)
    request = ChangeRequest.model_validate(
        {"accounts": {"patch": [{"id": "bank", "label": "Renamed"}]}}
    )
    serialized = request.model_dump(mode="json")
    assert serialized["accounts"]["patch"] == [{"id": "bank", "label": "Renamed"}]
    assert ChangeRequest.model_validate(serialized) == request
    token = engine.change(path, request).confirmation_token
    changed = ChangeRequest.model_validate(
        {
            "accounts": {
                "patch": [{"id": "bank", "label": "Renamed", "availability_note": None}]
            },
            "confirmation_token": token,
        }
    )
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, changed)


def test_patch_promotes_schema_only_on_effective_apply(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    engine.initialize(path)
    submit(
        path,
        {
            "goals": {
                "add": [{"id": "goal", "name": "Synthetic", "target_amount": "100"}]
            }
        },
    )
    raw = path.read_bytes()
    request = ChangeRequest.model_validate(
        {"goals": {"patch": [{"id": "goal", "reserved_amount": "0"}]}}
    )
    assert engine.change(path, request).status == "preview"
    assert path.read_bytes() == raw
    submit(path, request.model_dump(mode="json"))
    assert storage.read(path)[1].schema_version == "topo2.context/7"


def test_patches_across_all_record_sections(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    fixture(path)
    submit(
        path,
        {
            "assets": {"add": [{"id": "asset", "label": "Synthetic", "type": "other"}]},
            "debts": {"add": [{"id": "debt", "label": "Synthetic", "type": "loan"}]},
            "transactions": {
                "add": [
                    {
                        "id": "tx",
                        "account_id": "bank",
                        "booking_date": "2026-10-17",
                        "amount": "-2",
                        "currency": "EUR",
                        "description": "Synthetic",
                    }
                ]
            },
            "inventories": {
                "add": [
                    {"id": "cashflows", "status": "partial", "checked_on": "2026-10-17"}
                ]
            },
            "transaction_coverage": {
                "add": [
                    {
                        "id": "coverage",
                        "account_id": "bank",
                        "from_date": "2026-10-01",
                        "to_date": "2026-10-16",
                        "checked_on": "2026-10-17",
                    }
                ]
            },
            "cashflows": {
                "add": [
                    {
                        "id": "flow",
                        "label": "Synthetic",
                        "kind": "income",
                        "frequency": "monthly",
                        "start_date": "2026-10-01",
                        "amount": "10",
                    }
                ]
            },
        },
    )
    submit(
        path,
        {
            "accounts": {"patch": [{"id": "bank", "label": "Changed"}]},
            "assets": {"patch": [{"id": "asset", "availability": "free"}]},
            "debts": {"patch": [{"id": "debt", "interest_rate": "1"}]},
            "goals": {"patch": [{"id": "goal", "priority": "high"}]},
            "transactions": {"patch": [{"id": "tx", "category": "Synthetic category"}]},
            "inventories": {"patch": [{"id": "cashflows", "status": "complete"}]},
            "transaction_coverage": {
                "patch": [{"id": "coverage", "to_date": "2026-10-17"}]
            },
            "cashflows": {
                "patch": [{"id": "flow", "amount": {"lower": "1", "upper": "2"}}]
            },
        },
    )
    context = storage.read(path)[1]
    assert context.accounts[0].label == "Changed"
    assert context.assets[0].availability == "free"
    assert str(context.debts[0].interest_rate) == "1"
    assert context.goals[0].priority == "high"
    assert context.transactions[0].category == "Synthetic category"
    assert context.inventories[0].status == "complete"
    assert context.transaction_coverage[0].to_date.isoformat() == "2026-10-17"
    assert context.cashflows[0].model_dump(mode="json")["amount"] == {
        "lower": "1",
        "upper": "2",
    }


@pytest.mark.parametrize(
    "name",
    [
        "Account",
        "Asset",
        "Debt",
        "Goal",
        "Transaction",
        "Inventory",
        "TransactionCoverage",
        "Cashflow",
    ],
)
def test_patch_schema_tracks_record_fields_and_constraints(name: str) -> None:
    definitions = ChangeRequest.model_json_schema()["$defs"]
    original = definitions[name]["properties"]
    patch = definitions[name + "Patch"]
    assert patch["required"] == ["id"] and patch["minProperties"] == 2
    assert patch["properties"].keys() == original.keys()
    for field, properties in original.items():
        assert patch["properties"][field] == {
            key: value for key, value in properties.items() if key != "default"
        }
