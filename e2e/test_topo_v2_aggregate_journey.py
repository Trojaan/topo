from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import validate
from test_topo_v2_transactions_journey import run


def fingerprint(path: Path) -> tuple[str, int]:
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


def apply(context: tuple[str, str], request: dict[str, Any]) -> None:
    # Mechanical contract proof only: never represents human consent.
    request["confirmation_token"] = run("change", *context, request=request)["result"][
        "confirmation_token"
    ]
    assert run("change", *context, request=request)["result"]["status"] == "applied"


def test_aggregate_import_preservation_and_storage_journey(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    args = ("--context", str(path))
    run("init", *args)
    apply(
        args,
        {
            "accounts": {
                "add": [
                    {
                        "id": "bank",
                        "label": "Bank",
                        "type": "payment",
                        "balance": "100",
                        "as_of": "2026-10-01",
                        "availability": "free",
                        "availability_note": "Synthetic",
                    }
                ]
            },
            "debts": {"add": [{"id": "loan", "label": "Loan", "type": "loan"}]},
            "transaction_coverage": {
                "add": [
                    {
                        "id": "coverage",
                        "account_id": "bank",
                        "from_date": "2026-10-01",
                        "to_date": "2026-10-31",
                        "checked_on": "2026-10-14",
                    }
                ]
            },
        },
    )
    before_summary = run("summary", *args)["result"]
    tx = {
        "id": "purchase",
        "account_id": "bank",
        "booking_date": "2026-10-01",
        "amount": "-100",
        "currency": "EUR",
        "description": "Synthetic",
        "category": "Winkel",
        "source": "Export",
        "kind": "expense",
    }
    request = {
        "transactions": {
            "add": [
                tx,
                {**tx, "id": "refund", "amount": "20"},
                {**tx, "id": "usd", "currency": "USD", "kind": "unknown"},
            ]
        }
    }
    original = fingerprint(path)
    preview = run("change", *args, request=request)["result"]
    assert preview["changes"][0]["after"]["kind"] == "expense"
    assert fingerprint(path) == original
    assert json.loads(path.read_bytes())["schema_version"] == "topo2.context/4"
    stale = {
        "transactions": {
            "add": [
                {**record, "kind": "income"}
                for record in request["transactions"]["add"]
            ]
        },
        "confirmation_token": preview["confirmation_token"],
    }
    assert (
        run("change", *args, request=stale, success=False)["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    assert fingerprint(path) == original
    apply(args, request)
    assert json.loads(path.read_bytes())["schema_version"] == "topo2.context/5"
    schema = run("contract", "aggregate-transactions")["result"]
    aggregate_args = (
        "aggregate-transactions",
        *args,
        "--from-date",
        "2026-10-01",
        "--to-date",
        "2026-10-31",
        "--account",
        "bank",
        "--currency",
        "EUR",
        "--category",
        "Winkel",
        "--group-by",
        "month",
        "--group-by",
        "category",
    )
    original = fingerprint(path)
    result = run(*aggregate_args)["result"]
    validate(result, schema["output"])
    assert result["count"] == 2 and result["totals"][0]["expenses"] == "80"
    assert result["groups"][0]["month"] == "2026-10"
    assert (
        result["classification_complete"] is True
        and result["coverage"][0]["status"] == "complete"
    )
    assert fingerprint(path) == original
    assert run("summary", *args)["result"] == before_summary
    # Older exports, omitted enrichments and empty CSV cells all preserve.
    legacy = {
        key: value
        for key, value in tx.items()
        if key not in ("kind", "category", "source")
    }
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps([legacy]))
    import_args = (
        "import-transactions",
        *args,
        "--file",
        str(source),
        "--format",
        "json",
    )
    unchanged = run(*import_args)["result"]
    assert (
        unchanged["status"] == "unchanged" and unchanged["confirmation_token"] is None
    )
    assert fingerprint(path) == original
    csv_source = tmp_path / "legacy.csv"
    with csv_source.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(tx))
        writer.writeheader()
        writer.writerow({**legacy, "kind": "", "category": "", "source": ""})
    assert (
        run("import-transactions", *args, "--file", str(csv_source), "--format", "csv")[
            "result"
        ]["status"]
        == "unchanged"
    )
    assert fingerprint(path) == original
    for enrichment in (
        {"kind": "income", "category": "New", "source": "Replacement"},
        {"kind": None, "category": None, "source": None},
    ):
        source.write_text(json.dumps([{**legacy, **enrichment}]))
        original = fingerprint(path)
        preview = run(*import_args, "--details")["result"]
        assert fingerprint(path) == original
        for key, value in enrichment.items():
            assert preview["changes"][0]["after"][key] == value
        run(*import_args, "--confirmation-token", preview["confirmation_token"])
        original = fingerprint(path)
        assert run(*import_args)["result"]["status"] == "unchanged"
        assert fingerprint(path) == original
    # change.update still replaces the entire record, and v5 is sticky.
    apply(
        args,
        {
            "transactions": {
                "update": [
                    {**tx, "id": "refund", "amount": "20", "kind": None},
                    {**tx, "id": "usd", "currency": "USD", "kind": None},
                ]
            }
        },
    )
    apply(args, {"transactions": {"update": [tx]}})
    apply(args, {"transactions": {"update": [legacy]}})
    shown = run("show", *args)["result"]
    assert shown["schema_version"] == "topo2.context/5"
    assert all(record["kind"] is None for record in shown["transactions"])
    purchase = next(
        record for record in shown["transactions"] if record["id"] == "purchase"
    )
    assert purchase["category"] is None and purchase["source"] is None
    assert (
        shown["accounts"][0]["availability_note"] == "Synthetic"
        and len(shown["debts"]) == 1
    )
    assert run("summary", *args)["result"] == before_summary
    empty = run("aggregate-transactions", *args, "--currency", "GBP")["result"]
    assert empty["count"] == 0 and empty["classification_complete"] is None


def test_old_versions_only_migrate_on_effective_confirmation(tmp_path: Path) -> None:
    for version in range(1, 5):
        path = tmp_path / f"v{version}.json"
        args = ("--context", str(path))
        path.write_text(
            json.dumps(
                {
                    "schema_version": f"topo2.context/{version}",
                    "context_id": "synthetic",
                    "accounts": [{"id": "bank", "label": "Bank", "type": "payment"}],
                }
            )
        )
        original = fingerprint(path)
        run("context", *args)
        run("aggregate-transactions", *args)
        same = {
            "accounts": {"update": [{"id": "bank", "label": "Bank", "type": "payment"}]}
        }
        assert run("change", *args, request=same)["result"]["status"] == "unchanged"
        tx = {
            "id": "tx",
            "account_id": "bank",
            "booking_date": "2026-10-01",
            "amount": "-1",
            "currency": "EUR",
            "description": "Synthetic",
            "kind": "expense",
        }
        request = {"transactions": {"add": [tx]}}
        preview = run("change", *args, request=request)["result"]
        assert preview["status"] == "preview" and fingerprint(path) == original
        bad = {"transactions": {"add": [{**tx, "kind": "guessed"}]}}
        run("change", *args, request=bad, success=False)
        assert fingerprint(path) == original
        apply(args, request)
        assert json.loads(path.read_bytes())["schema_version"] == "topo2.context/5"
        apply(args, {"transactions": {"delete": ["tx"]}})
        assert json.loads(path.read_bytes())["schema_version"] == "topo2.context/5"


def test_grouping_coverage_gaps_and_unknown_classification(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    args = ("--context", str(path))
    run("init", *args)
    base = {
        "account_id": "bank",
        "currency": "EUR",
        "description": "Synthetic",
        "amount": "-10",
    }
    apply(
        args,
        {
            "accounts": {
                "add": [
                    {"id": "bank", "label": "Bank", "type": "payment"},
                    {"id": "empty", "label": "Empty", "type": "savings"},
                ]
            },
            "transactions": {
                "add": [
                    {
                        **base,
                        "id": "oct",
                        "booking_date": "2026-10-01",
                        "kind": "expense",
                    },
                    {
                        **base,
                        "id": "sep",
                        "booking_date": "2026-09-01",
                        "category": "Inkomen",
                        "kind": "unknown",
                    },
                ]
            },
            "transaction_coverage": {
                "add": [
                    {
                        "id": "first",
                        "account_id": "bank",
                        "from_date": "2026-09-01",
                        "to_date": "2026-09-15",
                        "checked_on": "2026-10-14",
                    },
                    {
                        "id": "last",
                        "account_id": "bank",
                        "from_date": "2026-09-17",
                        "to_date": "2026-10-31",
                        "checked_on": "2026-10-14",
                    },
                ]
            },
        },
    )
    original = fingerprint(path)
    result = run(
        "aggregate-transactions",
        *args,
        "--from-date",
        "2026-09-01",
        "--to-date",
        "2026-10-31",
        "--group-by",
        "month",
        "--group-by",
        "category",
    )["result"]
    assert [item["status"] for item in result["coverage"]] == ["partial", "unknown"]
    assert [item["month"] for item in result["groups"]] == ["2026-09", "2026-10"]
    assert (
        result["groups"][0]["income"] == "0"
        and result["groups"][0]["unknown_count"] == 1
    )
    assert result["groups"][1]["classification_complete"] is True
    assert result["classification_complete"] is False
    for dimensions in [("category",), ("month",), ("category", "month")]:
        options = tuple(
            value for dimension in dimensions for value in ("--group-by", dimension)
        )
        grouped = run("aggregate-transactions", *args, *options)["result"]
        assert sum(item["count"] for item in grouped["groups"]) == 2
    run(
        "aggregate-transactions",
        *args,
        "--group-by",
        "month",
        "--group-by",
        "month",
        success=False,
    )
    assert fingerprint(path) == original
