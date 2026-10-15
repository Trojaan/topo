from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

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

GOAL_SOURCES = Path(__file__).parent / "fixtures" / "topo2-goals"


def test_short_goal_preview_unknown_zero_and_noop(tmp_path: Path) -> None:
    assert "€10.000" in (GOAL_SOURCES / "doel-kort.txt").read_text()
    path = tmp_path / "context.json"
    opts = ("--context", str(path))
    run("init", *opts)
    # No clarification/inventory/allocation/preference requirement. "Volgend jaar"
    # supplies no exact date, so we leave target_date unknown in the joint preview.
    goal = {"id": "renovation", "name": "Verbouwing", "target_amount": "10000"}
    request = {"goals": {"add": [goal]}}
    binding = ("--source", str(GOAL_SOURCES / "doel-kort.txt"))
    original = fingerprint(path)
    schemas = run("contract")["result"]["commands"]
    validate(request, schemas["change"]["input"])
    preview = run("change", *opts, *binding, request=request)["result"]
    validate(preview, schemas["change"]["output"])
    assert len(preview["changes"]) == 1 and fingerprint(path) == original
    assert preview["changes"][0]["after"]["target_date"] is None
    apply(path, request, *binding)  # Mechanical proof only.
    raw = json.loads(path.read_text())
    assert raw["schema_version"] == "topo2.context/2"
    assert "reserved_amount" not in raw["goals"][0]
    assert "monthly_contribution" not in raw["goals"][0]
    assert "priority" not in raw["goals"][0] and "note" not in raw["goals"][0]
    summary = run("summary", *opts)["result"]
    validate(summary, schemas["summary"]["output"])
    assert summary["goals"][0]["remaining_amount"] is None
    assert summary["goals"][0]["reserved_amount"] is None
    assert summary["reservation_comparison"][0]["coverage_unknown"]
    original = fingerprint(path)
    repeated = {"goals": {"update": [goal]}}
    assert run("change", *opts, request=repeated)["result"] == {
        "status": "unchanged",
        "changes": [],
        "confirmation_token": None,
    }
    assert fingerprint(path) == original
    apply(path, {"goals": {"update": [{**goal, "reserved_amount": "0"}]}})
    result = run("context", *opts)["result"]
    validate(result, schemas["context"]["output"])
    assert result["summary"]["goals"][0]["remaining_amount"] == "10000"
    assert result["summary"]["goals"][0]["reserved_amount"] == "0"
    assert (
        result["summary"]["reservation_comparison"][0]["unknown_reservation_ids"] == []
    )


@pytest.mark.parametrize("version", range(1, 7))
def test_old_contexts_read_preview_noop_migrate_and_clear(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "legacy.json"
    bank = {
        "id": "bank",
        "label": "Bank",
        "type": "savings",
        "balance": "6400",
        "as_of": "2026-10-15",
    }
    goal = {
        "id": "buffer",
        "name": "Buffer",
        "target_amount": "10000",
        "account_ids": ["bank"],
    }
    path.write_text(
        json.dumps(
            {
                "schema_version": f"topo2.context/{version}",
                "context_id": "synthetic",
                "accounts": [bank],
                "goals": [goal],
            }
        )
    )
    opts = ("--context", str(path))
    original = fingerprint(path)
    for command in ("show", "summary", "context"):
        run(command, *opts)
    summary = run("summary", *opts)["result"]["goals"][0]
    assert summary["known_amount"] == summary["linked_value"]["known_amount"] == "6400"
    assert summary["remaining_amount"] is None
    assert (
        run("change", *opts, request={"goals": {"update": [goal]}})["result"]["status"]
        == "unchanged"
    )
    request = {
        "goals": {
            "update": [
                {
                    **goal,
                    "reserved_amount": "4000",
                    "monthly_contribution": "200",
                    "priority": "high",
                    "note": "Buffer",
                }
            ]
        }
    }
    preview = run("change", *opts, request=request)["result"]
    changed = {
        **request,
        "goals": {"update": [{**goal, "reserved_amount": "4001"}]},
        "confirmation_token": preview["confirmation_token"],
    }
    assert (
        run("change", *opts, request=changed, success=False)["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    assert fingerprint(path) == original
    apply(path, request)
    assert json.loads(path.read_text())["schema_version"] == "topo2.context/7"
    result = run("summary", *opts)["result"]
    assert result["goals"][0]["remaining_amount"] == "6000"
    assert result["goals"][0]["linked_value"]["known_amount"] == "6400"
    # Falling values and excess destinations are warnings, never storage errors.
    apply(
        path,
        {"accounts": {"update": [{**bank, "balance": "1", "availability": "free"}]}},
    )
    comparison = run("summary", *opts)["result"]["reservation_comparison"][0]
    assert comparison["possible_excess"] and comparison["coverage_unknown"]
    apply(path, {"goals": {"update": [{**goal, "reserved_amount": "12000"}]}})
    assert run("summary", *opts)["result"]["goals"][0]["remaining_amount"] == "0"
    apply(path, {"goals": {"update": [goal]}})
    assert json.loads(path.read_text())["schema_version"] == "topo2.context/7"
    assert run("summary", *opts)["result"]["goals"][0]["remaining_amount"] is None


def test_joint_sources_enrichments_reimport_and_monthly_picture(tmp_path: Path) -> None:
    # Separate synthetic analytical fixture, never a product confirmation step.
    analysis = tmp_path / "analysis.json"
    run("init", "--context", str(analysis))
    apply(analysis, source_request())
    aggregate = run(
        "aggregate-transactions", "--context", str(analysis), "--group-by", "category"
    )["result"]
    request = {**source_request(), **prepared_expectations(aggregate)}
    request["goals"]["add"][0].update(
        reserved_amount="4000",
        monthly_contribution="200",
        priority="high",
        note="Buffer voor onderhoud",
    )
    path = tmp_path / "joint.json"
    opts = ("--context", str(path))
    run("init", *opts)
    converted = tmp_path / "converted.json"
    converted.write_text(json.dumps(convert_export(FIXTURES / "bank.csv")))
    source = tmp_path / "goal.txt"
    source.write_bytes((GOAL_SOURCES / "doel-verrijking.txt").read_bytes())
    bindings = tuple(
        arg
        for item in [
            FIXTURES / "bank.csv",
            FIXTURES / "saldo-betaal.png",
            FIXTURES / "saldo-spaar.png",
            FIXTURES / "doel.txt",
            WEALTH_SOURCE,
            CASHFLOW_SOURCE,
            source,
            converted,
        ]
        for arg in ("--source", str(item))
    )
    schemas = run("contract")["result"]["commands"]
    validate(request, schemas["change"]["input"])
    original = fingerprint(path)
    preview = run("change", *opts, *bindings, request=request)["result"]
    assert {"goals", "transactions", "debts", "cashflows", "cashflow_settings"} <= {
        item["section"] for item in preview["changes"]
    }
    source.write_bytes(source.read_bytes() + b" ")
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
    monthly_args = ("monthly-room", *opts, "--reference-date", "2026-10-14")
    monthly = run(*monthly_args)["result"]
    summary = run("summary", *opts)["result"]
    assert Decimal(summary["goals"][0]["remaining_amount"]) == 6000
    assert Decimal(summary["goals"][0]["linked_value"]["known_amount"]) == 6400
    assert Decimal(monthly["currencies"][0]["known_room"]["lower"]) == 1705
    assert Decimal(monthly["currencies"][0]["minimum_reserve"]) == 5000
    repeated: dict[str, Any] = {
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
    assert (
        run("change", *opts, *bindings, request=repeated)["result"]["status"]
        == "unchanged"
    )
    assert fingerprint(path) == original
    rows = convert_export(FIXTURES / "bank-updated.csv")
    converted.write_text(json.dumps(rows))
    apply(path, export_change(shown, rows), *bindings)
    # Standalone import is also a real correction, followed by a no-op.
    converted.write_text(json.dumps([{**rows[0], "amount": "-87.50"}]))
    imports = (
        "import-transactions",
        *opts,
        "--file",
        str(converted),
        "--format",
        "json",
    )
    token = run(*imports)["result"]["confirmation_token"]
    run(*imports, "--confirmation-token", token)
    after = run("show", *opts)["result"]
    for section in (
        "accounts",
        "assets",
        "debts",
        "goals",
        "cashflows",
        "cashflow_settings",
        "inventories",
        "transaction_coverage",
    ):
        assert after[section] == shown[section]
    for before in shown["transactions"]:
        current = next(
            item for item in after["transactions"] if item["id"] == before["id"]
        )
        for field in ("kind", "category", "source"):
            assert current[field] == before[field]
    assert run("summary", *opts)["result"] == summary
    assert run(*monthly_args)["result"] == monthly
    original = fingerprint(path)
    assert run(*imports)["result"]["status"] == "unchanged"
    assert fingerprint(path) == original
