from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import validate
from test_topo_v2_aggregate_journey import fingerprint
from test_topo_v2_transactions_journey import run
from test_topo_v2_wealth_journey import apply
from topo2_cashflow_fixture import (
    CASHFLOW_SOURCE,
    prepared_expectations,
    source_request,
)
from topo2_input_fixture import FIXTURES, convert_export, export_change
from topo2_wealth_fixture import WEALTH_SOURCE


def test_export_aggregations_joint_monthly_picture_and_reimport(tmp_path: Path) -> None:
    # Separate temporary fixture seed allows CLI aggregation before the joint
    # target preview. These tokens prove mechanics, never human authorization.
    analysis = tmp_path / "analysis.json"
    run("init", "--context", str(analysis))
    apply(analysis, source_request())
    aggregate = run(
        "aggregate-transactions",
        "--context",
        str(analysis),
        "--from-date",
        "2026-10-01",
        "--to-date",
        "2026-10-31",
        "--group-by",
        "month",
        "--group-by",
        "category",
    )["result"]
    assert aggregate["classification_complete"]
    assert all(item["status"] == "unknown" for item in aggregate["coverage"])
    expectations = prepared_expectations(aggregate)
    request = {**source_request(), **expectations}
    path = tmp_path / "joint.json"
    opts = ("--context", str(path))
    run("init", *opts)
    converted = tmp_path / "converted.json"
    converted.write_text(json.dumps(convert_export(FIXTURES / "bank.csv")))
    bindings = tuple(
        arg
        for source in [
            FIXTURES / "bank.csv",
            FIXTURES / "saldo-betaal.png",
            FIXTURES / "saldo-spaar.png",
            FIXTURES / "doel.txt",
            WEALTH_SOURCE,
            CASHFLOW_SOURCE,
            converted,
        ]
        for arg in ("--source", str(source))
    )
    schemas = run("contract")["result"]["commands"]
    validate(request, schemas["change"]["input"])
    original = fingerprint(path)
    preview = run("change", *opts, *bindings, request=request)["result"]
    validate(preview, schemas["change"]["output"])
    assert {"cashflows", "cashflow_settings", "transactions", "debts"} <= {
        item["section"] for item in preview["changes"]
    }
    assert fingerprint(path) == original
    changed = {
        **request,
        "cashflow_settings": {"EUR": {"minimum_reserve": "1"}},
        "confirmation_token": preview["confirmation_token"],
    }
    assert (
        run("change", *opts, *bindings, request=changed, success=False)["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    converted.write_bytes(converted.read_bytes() + b" ")
    assert (
        run(
            "change",
            *opts,
            *bindings,
            request={**request, "confirmation_token": preview["confirmation_token"]},
            success=False,
        )["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    assert fingerprint(path) == original
    apply(path, request, *bindings)
    shown = run("show", *opts)["result"]
    assert shown["schema_version"] == "topo2.context/6"
    monthly_args = ("monthly-room", *opts, "--reference-date", "2026-10-14")
    monthly = run(*monthly_args)["result"]
    validate(monthly, schemas["monthly-room"]["output"])
    eur, usd = monthly["currencies"]
    assert Decimal(eur["known_income"]["lower"]) == 3250
    assert Decimal(eur["known_expenses"]["upper"]) == 1545
    assert Decimal(eur["known_room"]["lower"]) == 1705
    assert Decimal(eur["known_room"]["upper"]) == Decimal("1878.33333334")
    assert eur["room"] is None and eur["missing_ids"] == ["loan_payment"]
    assert monthly["inventory"]["status"] == "unknown"
    assert Decimal(eur["minimum_reserve"]) == 5000  # Not a monthly deduction.
    assert Decimal(usd["known_room"]["lower"]) == 50 and usd["room"] is None
    assert {item["id"] for item in eur["records"]} == {
        "salary",
        "groceries",
        "housing",
        "insurance",
        "subscription",
        "loan_payment",
    }
    compact = run(
        "context", *opts, "--reference-date", "2026-10-14", "--max-age-days", "30"
    )["result"]
    validate(compact, schemas["context"]["output"])
    assert compact["monthly_room"] == monthly and "transactions" not in compact
    assert not any(
        item["code"] == "not_supported" and item["outcome"] == "monthly_room"
        for item in compact["limitations"]
    )
    assert run("context", *opts)["result"]["monthly_room"] is None
    # Repeat the complete effective input: no additional token or write.
    repeated = {
        section: {"update": shown[section]}
        for section in (
            "accounts",
            "assets",
            "debts",
            "goals",
            "transactions",
            "cashflows",
        )
    }
    repeated["cashflow_settings"] = shown["cashflow_settings"]
    original = fingerprint(path)
    unchanged = run("change", *opts, *bindings, request=repeated)["result"]
    assert unchanged == {
        "status": "unchanged",
        "confirmation_token": None,
        "changes": [],
    }
    assert fingerprint(path) == original
    summary = run("summary", *opts)["result"]
    rows = convert_export(FIXTURES / "bank-updated.csv")
    converted.write_text(json.dumps(rows))
    update = export_change(shown, rows)
    assert (
        len(run("change", *opts, *bindings, request=update)["result"]["changes"]) == 2
    )
    apply(path, update, *bindings)
    after = run("show", *opts)["result"]
    for section in (
        "accounts",
        "assets",
        "debts",
        "goals",
        "cashflows",
        "cashflow_settings",
    ):
        assert after[section] == shown[section]
    for prior in shown["transactions"]:
        current = next(
            item for item in after["transactions"] if item["id"] == prior["id"]
        )
        for field in ("kind", "category", "source"):
            assert current[field] == prior[field]
    assert run(*monthly_args)["result"] == monthly
    assert run("summary", *opts)["result"] == summary
    # Standalone changed import preserves expectations as well as enrichments.
    converted.write_text(json.dumps([{**rows[0], "amount": "-87.50"}]))
    import_args = (
        "import-transactions",
        *opts,
        "--file",
        str(converted),
        "--format",
        "json",
    )
    import_preview = run(*import_args)["result"]
    run(*import_args, "--confirmation-token", import_preview["confirmation_token"])
    after = run("show", *opts)["result"]
    for section in (
        "accounts",
        "assets",
        "debts",
        "goals",
        "cashflows",
        "cashflow_settings",
    ):
        assert after[section] == shown[section]
    assert run(*monthly_args)["result"] == monthly
    assert run("summary", *opts)["result"] == summary
    original = fingerprint(path)
    assert run(*import_args)["result"]["status"] == "unchanged"
    assert fingerprint(path) == original
    realized = run("aggregate-transactions", *opts)["result"]
    assert (
        realized["count"] == 5
        and realized["totals"][0]["internal_transfers"]["count"] == 2
    )
    assert realized["totals"][0]["unknown_count"] == 1


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_legacy_monthly_read_preview_noop_and_migration(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "legacy.json"
    bank = {"id": "bank", "label": "Bank", "type": "payment"}
    path.write_text(
        json.dumps(
            {
                "schema_version": f"topo2.context/{version}",
                "context_id": "synthetic",
                "accounts": [bank],
            }
        )
    )
    opts = ("--context", str(path))
    original = fingerprint(path)
    monthly = ("monthly-room", *opts, "--reference-date", "2026-10-14")
    assert run(*monthly)["result"]["currencies"] == []
    assert (
        run("change", *opts, request={"accounts": {"update": [bank]}})["result"][
            "status"
        ]
        == "unchanged"
    )
    flow = {
        "id": "income",
        "label": "Synthetic",
        "kind": "income",
        "amount": "12",
        "frequency": "yearly",
        "start_date": "2026-10-14",
    }
    request = {
        "cashflows": {"add": [flow]},
        "cashflow_settings": {"EUR": {"minimum_reserve": "0"}},
    }
    run("change", *opts, request=request)
    assert fingerprint(path) == original
    for bad in ({"debt_id": "missing"}, {"end_date": "2026-10-13"}, {"id": "bank"}):
        run(
            "change",
            *opts,
            request={"cashflows": {"add": [{**flow, **bad}]}},
            success=False,
        )
        assert fingerprint(path) == original
    apply(path, request)
    assert run("show", *opts)["result"]["schema_version"] == "topo2.context/6"
    assert run(*monthly)["result"]["currencies"][0]["room"] is None
    apply(
        path,
        {
            "inventories": {
                "add": [
                    {
                        "id": "cashflows",
                        "status": "complete",
                        "checked_on": "2026-10-14",
                    }
                ]
            }
        },
    )
    assert Decimal(run(*monthly)["result"]["currencies"][0]["room"]["lower"]) == 1
    apply(
        path, {"cashflows": {"delete": ["income"]}, "cashflow_settings": {"EUR": None}}
    )
    assert run("show", *opts)["result"]["schema_version"] == "topo2.context/6"
    assert run(*monthly)["result"]["currencies"] == []
    run("monthly-room", *opts, "--reference-date", "invalid", success=False)
