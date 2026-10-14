from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import validate


def run(
    *args: str, request: dict[str, Any] | None = None, success: bool = True
) -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, "-m", "topo_v2", *args],
        input=json.dumps(request) if request is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == (0 if success else 1), process.stdout + process.stderr
    result: dict[str, Any] = json.loads(process.stdout)
    assert result["contract_version"] == "topo2.cli/3"
    return result


def test_import_query_correct_delete_and_balance_isolation(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    context = ("--context", str(path))
    schemas = run("contract")["result"]["commands"]
    run("init", *context)
    request = {
        "accounts": {
            "add": [
                {
                    "id": "bank",
                    "label": "Synthetic bank",
                    "type": "payment",
                    "balance": "1000.00",
                    "as_of": "2026-10-13",
                }
            ]
        },
        "transactions": {
            "add": [
                {
                    "id": "manual",
                    "account_id": "bank",
                    "booking_date": "2026-10-01",
                    "amount": "0",
                    "currency": "EUR",
                    "description": "",
                }
            ]
        },
    }
    request["confirmation_token"] = run("change", *context, request=request)["result"][
        "confirmation_token"
    ]
    run("change", *context, request=request)
    records = [
        {
            "id": f"export_{i:02d}",
            "account_id": "bank",
            "booking_date": "2026-10-13",
            "amount": "-12.50",
            "currency": "EUR",
            "description": f"Shop, synthetic {i}",
            "category": "Boodschappen",
            "source": "Synthetic export",
        }
        for i in range(25)
    ]
    source = tmp_path / "transactions.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    original = path.read_bytes()
    arguments = (
        "import-transactions",
        *context,
        "--file",
        str(source),
        "--format",
        "csv",
    )
    preview = run(*arguments)["result"]
    validate(preview, schemas["import-transactions"]["output"])
    assert preview["status"] == "preview" and preview["added"] == 25
    assert preview["truncated"] and len(preview["changes"]) == 20
    assert path.read_bytes() == original
    detailed = run(*arguments, "--details")["result"]
    assert len(detailed["changes"]) == 25 and not detailed["truncated"]
    assert detailed["confirmation_token"] == preview["confirmation_token"]
    source.write_bytes(source.read_bytes() + b"\n")
    assert (
        run(
            *arguments,
            "--confirmation-token",
            preview["confirmation_token"],
            success=False,
        )["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    assert path.read_bytes() == original
    preview = run(*arguments)["result"]
    applied = run(*arguments, "--confirmation-token", preview["confirmation_token"])[
        "result"
    ]
    assert applied["status"] == "applied" and applied["added"] == 25
    original = path.read_bytes()
    repeated = run(*arguments)["result"]
    assert (
        repeated["status"] == "unchanged"
        and repeated["skipped"] == 25
        and repeated["confirmation_token"] is None
    )
    page = run(
        "transactions",
        *context,
        "--account",
        "bank",
        "--from-date",
        "2026-10-13",
        "--to-date",
        "2026-10-13",
        "--currency",
        "EUR",
        "--category",
        "Boodschappen",
        "--min-amount",
        "-12.50",
        "--max-amount",
        "-12.50",
        "--search",
        "SYNTHETIC EXPORT",
        "--offset",
        "3",
        "--limit",
        "2",
    )["result"]
    validate(page, schemas["transactions"]["output"])
    assert page["total"] == 25 and [record["id"] for record in page["records"]] == [
        "export_03",
        "export_04",
    ]
    assert path.read_bytes() == original
    correction = tmp_path / "correction.json"
    records[0]["amount"] = "99999999999999999999.12345678"
    correction.write_text(json.dumps([records[0]]))
    json_args = (
        "import-transactions",
        *context,
        "--file",
        str(correction),
        "--format",
        "json",
    )
    preview = run(*json_args)["result"]
    assert (preview["added"], preview["updated"]) == (0, 1)
    run(*json_args, "--confirmation-token", preview["confirmation_token"])
    result = run(
        "transactions", *context, "--min-amount", "99999999999999999999.12345678"
    )["result"]
    assert (
        result["total"] == 1 and result["records"][0]["amount"] == records[0]["amount"]
    )
    assert (
        run("summary", *context)["result"]["subtotals"][0]["known_total"] == "1000.00"
    )
    shown = run("show", *context)["result"]
    validate(shown, schemas["show"]["output"])
    assert (
        shown["schema_version"] == "topo2.context/2"
        and len(shown["transactions"]) == 26
    )
    original = path.read_bytes()
    invalid_delete = run(
        "change", *context, request={"accounts": {"delete": ["bank"]}}, success=False
    )
    assert (
        invalid_delete["error"]["code"] == "INVALID_DATA"
        and path.read_bytes() == original
    )
    deletion: dict[str, Any] = {
        "accounts": {"delete": ["bank"]},
        "transactions": {"delete": [record["id"] for record in shown["transactions"]]},
    }
    deletion["confirmation_token"] = run("change", *context, request=deletion)[
        "result"
    ]["confirmation_token"]
    run("change", *context, request=deletion)
    assert run("transactions", *context)["result"]["total"] == 0


def test_legacy_read_preview_then_confirmed_upgrade_preserves_records(
    tmp_path: Path,
) -> None:
    path = tmp_path / "context.json"
    legacy: dict[str, Any] = {
        "schema_version": "topo2.context/1",
        "context_id": "legacy-id",
        "accounts": [
            {
                "id": "bank",
                "label": "Legacy bank",
                "type": "savings",
                "balance": "5.00",
                "currency": "EUR",
                "as_of": "2026-10-01",
            }
        ],
        "assets": [],
        "goals": [],
    }
    path.write_text(json.dumps(legacy))
    original = path.read_bytes()
    context = ("--context", str(path))
    assert run("show", *context)["result"]["schema_version"] == "topo2.context/1"
    assert run("transactions", *context)["result"]["total"] == 0
    assert run("summary", *context)["result"]["subtotals"][0]["known_total"] == "5.00"
    assert path.read_bytes() == original
    update: dict[str, Any] = {
        "accounts": {"update": [{**legacy["accounts"][0], "label": "Updated label"}]}
    }
    update["confirmation_token"] = run("change", *context, request=update)["result"][
        "confirmation_token"
    ]
    assert path.read_bytes() == original
    run("change", *context, request=update)
    stored = json.loads(path.read_bytes())
    assert stored["schema_version"] == "topo2.context/2"
    assert stored["context_id"] == "legacy-id" and stored["transactions"] == []
    assert stored["accounts"][0]["balance"] == "5.00"
    assert stored["accounts"][0]["label"] == "Updated label"


def test_invalid_import_and_query_leave_context_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    context = ("--context", str(path))
    run("init", *context)
    source = tmp_path / "invalid.json"
    source.write_text('[{"id":"missing-fields"}]')
    original = path.read_bytes()
    error = run(
        "import-transactions",
        *context,
        "--file",
        str(source),
        "--format",
        "json",
        success=False,
    )
    assert error["error"]["code"] == "INVALID_DATA"
    assert path.read_bytes() == original
    for arguments in (
        ("--limit", "1001"),
        ("--offset", "-1"),
        ("--from-date", "2026-10-14", "--to-date", "2026-10-13"),
        ("--min-amount", "10", "--max-amount", "1"),
    ):
        error = run("transactions", *context, *arguments, success=False)
        assert error["error"]["code"] == "INVALID_DATA"
        assert path.read_bytes() == original
