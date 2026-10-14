from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from topo_v2 import engine, storage
from topo_v2.models import (
    ChangeRequest,
    Context,
    Transaction,
    TransactionImportOptions,
    TransactionQuery,
)
from topo_v2.transactions import parse_transactions, select_transactions


def transaction(identifier: str = "tx", **fields: Any) -> Transaction:
    return Transaction.model_validate(
        {
            "id": identifier,
            "account_id": "bank",
            "booking_date": "2026-10-13",
            "amount": "-12.50",
            "currency": "EUR",
            "description": "Synthetic groceries",
            **fields,
        }
    )


def context_file(tmp_path: Path) -> Path:
    path = tmp_path / "context.json"
    engine.initialize(path)
    apply(
        path,
        {
            "accounts": {
                "add": [
                    {
                        "id": "bank",
                        "label": "Bank",
                        "type": "payment",
                        "balance": "100.00",
                        "as_of": "2026-10-13",
                    }
                ]
            }
        },
    )
    return path


def apply(path: Path, payload: dict[str, Any]) -> None:
    request = ChangeRequest.model_validate(payload)
    request.confirmation_token = engine.change(path, request).confirmation_token
    assert engine.change(path, request).status == "applied"


def data(records: list[Transaction]) -> bytes:
    return json.dumps([record.model_dump(mode="json") for record in records]).encode()


def test_combined_change_and_linked_deletion(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    engine.initialize(path)
    apply(
        path,
        {
            "accounts": {"add": [{"id": "bank", "label": "Bank", "type": "payment"}]},
            "transactions": {"add": [transaction().model_dump(mode="json")]},
        },
    )
    context = storage.read(path)[1]
    assert (
        context.schema_version == "topo2.context/2"
        and context.accounts[0].balance is None
    )
    original = path.read_bytes()
    with pytest.raises(ValidationError, match="unknown account"):
        engine.change(
            path, ChangeRequest.model_validate({"accounts": {"delete": ["bank"]}})
        )
    assert path.read_bytes() == original
    apply(path, {"accounts": {"delete": ["bank"]}, "transactions": {"delete": ["tx"]}})
    assert storage.read(path)[1].accounts == []
    assert storage.read(path)[1].transactions == []


def test_transaction_correction_replaces_without_history_or_balance_change(
    tmp_path: Path,
) -> None:
    path = context_file(tmp_path)
    apply(path, {"transactions": {"add": [transaction().model_dump(mode="json")]}})
    changed = transaction(amount="0", category="My free CATEGORY", source="manual")
    apply(path, {"transactions": {"update": [changed.model_dump(mode="json")]}})
    context = storage.read(path)[1]
    assert context.transactions == [changed]
    assert context.accounts[0].balance == Decimal("100.00")
    assert engine.summarize(context).subtotals[0].known_total == Decimal("100.00")
    assert "history" not in json.loads(path.read_bytes())
    assert b"-12.50" not in path.read_bytes()


@pytest.mark.parametrize(
    "records",
    [
        [transaction(), transaction()],
        [transaction("bank")],
        [transaction(account_id="unknown")],
    ],
)
def test_invalid_import_is_atomic(tmp_path: Path, records: list[Transaction]) -> None:
    path = context_file(tmp_path)
    original = path.read_bytes()
    with pytest.raises((ValidationError, engine.ChangeError)):
        engine.import_transactions(
            path, data(records), TransactionImportOptions(format="json")
        )
    assert path.read_bytes() == original


def test_import_compact_preview_full_details_reimport_and_replacement(
    tmp_path: Path,
) -> None:
    path = context_file(tmp_path)
    records = [transaction(f"tx_{i:02d}") for i in range(25)]
    payload = data(records)
    original = path.read_bytes()
    preview = engine.import_transactions(
        path, payload, TransactionImportOptions(format="json")
    )
    assert (preview.added, preview.updated, preview.skipped, preview.total_changes) == (
        25,
        0,
        0,
        25,
    )
    assert len(preview.changes) == 20 and preview.truncated
    assert path.read_bytes() == original
    detailed = engine.import_transactions(
        path, payload, TransactionImportOptions(format="json", details=True)
    )
    assert len(detailed.changes) == 25 and not detailed.truncated
    assert detailed.confirmation_token == preview.confirmation_token
    confirmed = engine.import_transactions(
        path,
        payload,
        TransactionImportOptions(
            format="json", confirmation_token=preview.confirmation_token
        ),
    )
    assert (
        confirmed.status == "applied" and len(storage.read(path)[1].transactions) == 25
    )
    original = path.read_bytes()
    repeated = engine.import_transactions(
        path, payload, TransactionImportOptions(format="json")
    )
    assert repeated.status == "unchanged" and repeated.confirmation_token is None
    assert repeated.changes == [] and repeated.skipped == 25
    assert path.read_bytes() == original
    records[0] = transaction("tx_00", amount="0.10", category="Changed")
    correction = engine.import_transactions(
        path, data(records), TransactionImportOptions(format="json")
    )
    assert (correction.added, correction.updated, correction.skipped) == (0, 1, 24)
    assert correction.changes[0].before == transaction("tx_00")
    assert correction.changes[0].after == records[0]
    engine.import_transactions(
        path,
        data(records),
        TransactionImportOptions(
            format="json", confirmation_token=correction.confirmation_token
        ),
    )
    assert storage.read(path)[1].transactions[0] == records[0]


def test_import_confirmation_binds_exact_file_including_skipped_records_and_context(
    tmp_path: Path,
) -> None:
    path = context_file(tmp_path)
    apply(
        path,
        {"transactions": {"add": [transaction("existing").model_dump(mode="json")]}},
    )
    payload = data([transaction("new"), transaction("existing")])
    preview = engine.import_transactions(
        path, payload, TransactionImportOptions(format="json")
    )
    options = TransactionImportOptions(
        format="json", confirmation_token=preview.confirmation_token
    )
    original = path.read_bytes()
    for altered in (payload + b" ", data([transaction("new")])):
        with pytest.raises(engine.StaleConfirmation):
            engine.import_transactions(path, altered, options)
        assert path.read_bytes() == original
    apply(
        path,
        {
            "transactions": {
                "update": [
                    transaction("existing", category="Changed elsewhere").model_dump(
                        mode="json"
                    )
                ]
            }
        },
    )
    original = path.read_bytes()
    with pytest.raises(engine.StaleConfirmation):
        engine.import_transactions(path, payload, options)
    assert path.read_bytes() == original


def test_failed_import_save_preserves_context(tmp_path: Path) -> None:
    path = context_file(tmp_path)
    payload = data([transaction()])
    preview = engine.import_transactions(
        path, payload, TransactionImportOptions(format="json")
    )
    original = path.read_bytes()
    with (
        patch("topo_v2.storage.os.replace", side_effect=OSError("disk failure")),
        pytest.raises(OSError, match="disk failure"),
    ):
        engine.import_transactions(
            path,
            payload,
            TransactionImportOptions(
                format="json", confirmation_token=preview.confirmation_token
            ),
        )
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".context.json.*"))


def test_csv_preserves_quoted_newlines_unicode_and_blank_optional_fields() -> None:
    payload = '\ufeffid,account_id,booking_date,amount,currency,description,category,source\r\ntx,bank,2026-10-13,-0.01,USD,"Café,\nsecond line",,export\r\n'.encode()
    records = parse_transactions(payload, "csv")
    assert records == [
        transaction(
            amount="-0.01",
            currency="USD",
            description="Café,\nsecond line",
            category=None,
            source="export",
        )
    ]


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"id,account_id,booking_date,amount,currency\n",
        b"id,id,account_id,booking_date,amount,currency,description\n",
        b"id,account_id,booking_date,amount,currency,description,unknown\n",
        b'id,account_id,booking_date,amount,currency,description\ntx,bank,2026-10-13,1,EUR,"unterminated',
        b"id,account_id,booking_date,amount,currency,description\ntx,bank,2026-10-13,1,EUR,hello,extra\n",
        b"id,account_id,booking_date,amount,currency,description\ntx,bank\n",
        b'"unterminated header',
    ],
)
def test_invalid_csv_has_explicit_errors(payload: bytes) -> None:
    with pytest.raises((ValueError, ValidationError)):
        parse_transactions(payload, "csv")


@pytest.mark.parametrize(
    "fields",
    [
        {"amount": 0.1},
        {"amount": "NaN"},
        {"amount": "Infinity"},
        {"booking_date": "2026-02-30"},
        {"currency": "eur"},
        {"id": ""},
    ],
)
def test_transaction_validation(fields: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        transaction(**fields)


def test_missing_currency_and_non_array_json_are_rejected() -> None:
    record = transaction().model_dump(mode="json")
    del record["currency"]
    with pytest.raises(ValidationError):
        parse_transactions(json.dumps([record]).encode(), "json")
    with pytest.raises(ValidationError):
        parse_transactions(b"{}", "json")


def test_filters_pagination_sorting_and_decimal_precision() -> None:
    records = [
        transaction(
            "b",
            booking_date="2026-10-13",
            amount="-12.50",
            category="Boodschappen",
            source="Straße export",
        ),
        transaction("a", booking_date="2026-10-13", amount="0", description="ZERO"),
        transaction("old", booking_date="2026-10-12", amount="1", currency="USD"),
        transaction(
            "next",
            booking_date="2026-10-14",
            amount="99999999999999999999.12345678",
            account_id="other",
        ),
    ]
    page = select_transactions(records, TransactionQuery(offset=1, limit=2))
    assert page.total == 4 and [record.id for record in page.records] == ["a", "b"]
    combined = TransactionQuery.model_validate(
        {
            "account_id": "bank",
            "from_date": "2026-10-13",
            "to_date": "2026-10-13",
            "currency": "EUR",
            "category": "Boodschappen",
            "min_amount": "-12.50",
            "max_amount": "-12.50",
            "search": "STRASSE",
        }
    )
    assert select_transactions(records, combined).records == [records[0]]
    assert select_transactions(
        records, TransactionQuery(search="BOODSCHAPPEN")
    ).records == [records[0]]
    assert select_transactions(records, TransactionQuery(search="zero")).records == [
        records[1]
    ]
    exact = TransactionQuery.model_validate(
        {"min_amount": "99999999999999999999.12345678"}
    )
    assert select_transactions(records, exact).records == [records[3]]
    assert select_transactions(records, TransactionQuery(offset=100)).records == []
    assert (
        select_transactions(records, TransactionQuery(account_id="absent")).total == 0
    )
    assert (
        select_transactions(records, TransactionQuery(category="boodschappen")).total
        == 0
    )
    assert list(page.model_dump()) == ["records", "total", "offset", "limit"]
    assert records[0].id == "b"


@pytest.mark.parametrize(
    "fields",
    [
        {"from_date": date(2026, 10, 14), "to_date": date(2026, 10, 13)},
        {"min_amount": "1", "max_amount": "-1"},
        {"limit": 0},
        {"limit": 1001},
        {"offset": -1},
    ],
)
def test_invalid_query_ranges(fields: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        TransactionQuery.model_validate(fields)


def test_legacy_context_read_and_noop_preserve_bytes_then_confirmed_change_upgrades(
    tmp_path: Path,
) -> None:
    path = context_file(tmp_path)
    old = json.loads(path.read_bytes())
    old["schema_version"] = "topo2.context/1"
    del old["transactions"]
    path.write_text(json.dumps(old))
    original = path.read_bytes()
    _, context = storage.read(path)
    assert context.schema_version == "topo2.context/1" and context.transactions == []
    assert select_transactions(context.transactions, TransactionQuery()).total == 0
    assert (
        engine.import_transactions(
            path, b"[]", TransactionImportOptions(format="json")
        ).status
        == "unchanged"
    )
    assert path.read_bytes() == original
    request = ChangeRequest.model_validate(
        {"transactions": {"add": [transaction().model_dump(mode="json")]}}
    )
    request.confirmation_token = engine.change(path, request).confirmation_token
    assert path.read_bytes() == original
    engine.change(path, request)
    current = storage.read(path)[1]
    assert current.schema_version == "topo2.context/2"
    assert (
        current.accounts == context.accounts
        and current.context_id == context.context_id
    )
    assert current.transactions == [transaction()]


def test_schema_one_cannot_hide_transactions() -> None:
    with pytest.raises(ValidationError, match="require"):
        Context.model_validate(
            {
                "schema_version": "topo2.context/1",
                "context_id": "test",
                "accounts": [{"id": "bank", "label": "Bank", "type": "payment"}],
                "transactions": [transaction().model_dump(mode="json")],
            }
        )
