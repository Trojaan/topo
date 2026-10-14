from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate
from test_topo_v2_transactions_journey import run
from topo2_input_fixture import first_request


def test_compact_partial_context_and_joint_declarations(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    options = ("--context", str(path))
    # Old context: no transaction list or declaration fields required.
    path.write_text(
        json.dumps(
            {
                "schema_version": "topo2.context/1",
                "context_id": "synthetic-old",
                "accounts": [
                    {"id": "unknown_balance", "label": "Onbekend", "type": "savings"}
                ],
            }
        )
    )
    raw = path.read_bytes()
    stat = path.stat()
    schema = run("contract", "context")["result"]
    partial = run("context", *options)["result"]
    validate(partial, schema["output"])
    assert "transactions" not in partial
    assert partial["summary"]["subtotals"][0] == {
        "currency": "EUR",
        "known_total": "0",
        "missing_ids": ["unknown_balance"],
        "complete": False,
    }
    assert all(item["status"] == "unknown" for item in partial["inventories"])
    assert partial["value_age"] == [
        {"id": "unknown_balance", "age_days": None, "stale": None}
    ]
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == stat.st_mtime_ns
    for invalid_args in (
        ("--reference-date", "2026-10-14"),
        ("--max-age-days", "30"),
        ("--reference-date", "2026-10-14", "--max-age-days", "-1"),
    ):
        assert (
            run("context", *options, *invalid_args, success=False)["error"]["code"]
            == "INVALID_DATA"
        )
    request: dict[str, Any] = first_request()
    request["inventories"] = {
        "add": [
            {"id": "debts", "status": "complete", "checked_on": "2026-10-14"},
            {"id": "accounts", "status": "partial", "checked_on": "2026-10-14"},
        ]
    }
    interval = {
        "id": "september_betaal",
        "account_id": "syn_betaal",
        "from_date": "2026-09-01",
        "to_date": "2026-09-30",
        "checked_on": "2026-10-14",
    }
    request["transaction_coverage"] = {"add": [interval]}
    preview = run("change", *options, request=request)["result"]
    validate(preview, run("contract", "change")["result"]["output"])
    assert path.read_bytes() == raw
    assert {item["section"] for item in preview["changes"]} == {
        "accounts",
        "goals",
        "transactions",
        "inventories",
        "transaction_coverage",
    }
    request["confirmation_token"] = preview["confirmation_token"]
    assert run("change", *options, request=request)["result"]["status"] == "applied"
    assert json.loads(path.read_bytes())["schema_version"] == "topo2.context/3"
    raw = path.read_bytes()
    stat = path.stat()
    compact = run(
        "context", *options, "--reference-date", "2026-10-14", "--max-age-days", "9"
    )["result"]
    validate(compact, schema["output"])
    assert compact["summary"]["subtotals"][0]["known_total"] == "8914.50"
    assert compact["summary"]["goals"][0]["percentage"] == "64.00"
    assert next(item for item in compact["inventories"] if item["id"] == "debts") == {
        "id": "debts",
        "status": "complete",
        "checked_on": "2026-10-14",
    }
    assert not any(item["ids"] == ["debts"] for item in compact["limitations"])
    assert {item["id"] for item in compact["value_age"] if item["stale"]} == {
        "syn_betaal",
        "syn_spaar",
    }
    assert any(
        item["outcome"] == "goal_progress" and item["code"] == "stale_values"
        for item in compact["limitations"]
    )
    coverage = {item["account_id"]: item for item in compact["transaction_coverage"]}
    assert coverage["syn_betaal"]["intervals"] == [interval]
    assert coverage["syn_spaar"]["status"] == "unknown"
    assert run("transactions", *options)["result"]["total"] == 4
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == stat.st_mtime_ns
    boundary = run(
        "context", *options, "--reference-date", "2026-10-14", "--max-age-days", "10"
    )["result"]
    assert not any(item["stale"] for item in boundary["value_age"])
    # Declaration-only no-op, then invalid cross-reference: neither writes.
    repeated = {
        section: {"update": request[section]["add"]}
        for section in ("inventories", "transaction_coverage")
    }
    assert run("change", *options, request=repeated)["result"]["status"] == "unchanged"
    for bad in (
        {"transaction_coverage": {"update": [{**interval, "from_date": "2026-10-01"}]}},
        {"transaction_coverage": {"update": [{**interval, "account_id": "missing"}]}},
        {
            "accounts": {"delete": ["syn_betaal"]},
            "transactions": {"delete": ["syn_SYN001", "syn_SYN002", "syn_SYN004"]},
        },
        {
            "inventories": {
                "add": [
                    {
                        "id": "unsupported",
                        "status": "complete",
                        "checked_on": "2026-10-14",
                    }
                ]
            }
        },
    ):
        run("change", *options, request=bad, success=False)
        assert path.read_bytes() == raw
    # Import must preserve optional declarations, including after removal of one.
    source = tmp_path / "export.json"
    source.write_text(
        json.dumps([{**first_request()["transactions"]["add"][0], "amount": "2501"}])
    )
    imported = run(
        "import-transactions", *options, "--file", str(source), "--format", "json"
    )["result"]
    run(
        "import-transactions",
        *options,
        "--file",
        str(source),
        "--format",
        "json",
        "--confirmation-token",
        imported["confirmation_token"],
    )
    assert (
        run("context", *options)["result"]["transaction_coverage"]
        == compact["transaction_coverage"]
    )
    removal = {"inventories": {"delete": ["debts"]}}
    preview = run("change", *options, request=removal)["result"]
    removal["confirmation_token"] = preview["confirmation_token"]
    run("change", *options, request=removal)
    unknown = run("context", *options)["result"]
    assert any(
        item["outcome"] == "net_wealth"
        and item["code"] == "inventory_unknown"
        and item["ids"] == ["debts"]
        for item in unknown["limitations"]
    )
    assert unknown["summary"]["subtotals"] == compact["summary"]["subtotals"]
