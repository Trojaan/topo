from __future__ import annotations

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
    body: dict[str, Any] = json.loads(process.stdout)
    return body


def test_twenty_accounts_five_etfs_and_goals(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    options = ("--context", str(path), "--json")
    schemas = run("contract")["result"]["commands"]
    run("init", *options)
    original = path.read_bytes()
    accounts = [
        {
            "id": f"account_{i}",
            "label": f"Account {i}",
            "type": "investment" if i == 0 else "savings",
            "balance": "100.10",
            "as_of": "2026-10-04",
        }
        for i in range(20)
    ]
    assets = [
        {
            "id": f"etf_{i}",
            "label": f"ETF {i}",
            "type": "etf",
            "value": "200.20",
            "as_of": "2026-10-04",
            "broker_account_id": "account_0",
        }
        for i in range(5)
    ]
    request = {
        "accounts": {"add": accounts},
        "assets": {"add": assets},
        "goals": {
            "add": [
                {
                    "id": "buffer",
                    "name": "Buffer",
                    "target_amount": "1000",
                    "account_ids": ["account_1"],
                }
            ]
        },
    }
    validate(request, schemas["change"]["input"])
    preview = run("change", *options, request=request)["result"]
    validate(preview, schemas["change"]["output"])
    assert preview["status"] == "preview" and len(preview["changes"]) == 26
    assert path.read_bytes() == original
    request["confirmation_token"] = preview["confirmation_token"]
    applied = run("change", *options, request=request)["result"]
    validate(applied, schemas["change"]["output"])
    assert applied["status"] == "applied"
    summary = run("summary", *options)["result"]
    validate(summary, schemas["summary"]["output"])
    assert summary["kind"] == "wealth_overview"
    assert summary["subtotals"][0]["known_total"] == "3003.00"
    assert summary["goals"][0]["percentage"] == "10.0100"
    shown = run("show", *options)["result"]
    validate(shown, schemas["show"]["output"])
    assert len(shown["accounts"]) == 20 and len(shown["assets"]) == 5
    update = {
        "accounts": {
            "update": [{**accounts[1], "balance": "500.50", "as_of": "2026-10-05"}]
        }
    }
    update["confirmation_token"] = run("change", *options, request=update)["result"][
        "confirmation_token"
    ]
    run("change", *options, request=update)
    summary = run("summary", *options)["result"]
    assert summary["subtotals"][0]["known_total"] == "3403.40"
    assert summary["goals"][0]["percentage"] == "50.0500"
    assert (
        run("change", *options, request=request, success=False)["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    persisted = json.loads(path.read_text())
    assert persisted["accounts"][1]["balance"] == "500.50"
    assert "history" not in persisted and "generations" not in persisted
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "context.json",
        "context.json.lock",
    ]


def test_request_file_and_invalid_input(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    run("init", "--context", str(path))
    original = path.read_bytes()
    request = tmp_path / "request.json"
    request.write_text(
        '{"accounts":{"add":[{"id":"bank","label":"Bank","type":"savings","balance":"1"}]}}'
    )
    result = run(
        "change", "--context", str(path), "--request", str(request), success=False
    )
    assert result["error"]["code"] == "INVALID_DATA"
    assert path.read_bytes() == original
