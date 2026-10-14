from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import validate
from test_topo_v2_transactions_journey import run
from topo2_input_fixture import FIXTURES, convert_export, export_change, first_request
from topo2_wealth_fixture import WEALTH_SOURCE, wealth_request


def apply(path: Path, request: dict[str, Any], *binding: str) -> dict[str, Any]:
    """Mechanical test confirmation only; never user-session evidence."""
    preview = run("change", "--context", str(path), *binding, request=request)["result"]
    result: dict[str, Any] = run(
        "change",
        "--context",
        str(path),
        *binding,
        request={**request, "confirmation_token": preview["confirmation_token"]},
    )["result"]

    return result


def test_sources_wealth_compact_read_and_reimport(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    opts = ("--context", str(path))
    run("init", *opts)
    request = first_request()
    for section, operations in wealth_request().items():
        request.setdefault(section, {}).setdefault("add", []).extend(operations["add"])
    source = tmp_path / "converted.json"
    source.write_text(json.dumps(convert_export(FIXTURES / "bank.csv")))
    binding = tuple(
        arg
        for source_path in [
            WEALTH_SOURCE,
            FIXTURES / "bank.csv",
            FIXTURES / "saldo-betaal.png",
            FIXTURES / "saldo-spaar.png",
            FIXTURES / "doel.txt",
            source,
        ]
        for arg in ("--source", str(source_path))
    )
    schemas = run("contract")["result"]["commands"]
    validate(request, schemas["change"]["input"])
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    preview = run("change", *opts, *binding, request=request)["result"]
    validate(preview, schemas["change"]["output"])
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    source.write_bytes(source.read_bytes() + b" ")
    assert (
        run(
            "change",
            *opts,
            *binding,
            request={**request, "confirmation_token": preview["confirmation_token"]},
            success=False,
        )["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    assert path.read_bytes() == raw
    apply(path, request, *binding)
    shown = run("show", *opts)["result"]
    assert shown["schema_version"] == "topo2.context/4"
    summary = run("summary", *opts)["result"]
    validate(summary, schemas["summary"]["output"])
    eur, usd = summary["net_wealth"]["subtotals"]
    assert eur["known_total"] == "118414.50"  # 109500 plus original source balances.
    assert eur["missing_ids"] == ["unknown_loan"] and not eur["complete"]
    assert not eur["inventory_complete"] and eur["linked_debt_ids"] == ["overdraft"]
    assert usd["known_total"] == "900"
    assert summary["goals"][0]["percentage"] == "64.00"
    assert summary["availability"][0]["known_free_total"] == "0"
    assert "home" in summary["availability"][0]["unknown_availability_ids"]
    compact = run(
        "context", *opts, "--reference-date", "2026-10-14", "--max-age-days", "9"
    )["result"]
    validate(compact, schemas["context"]["output"])
    assert "transactions" not in compact and compact["summary"] == summary
    assert compact["debts"] == shown["debts"]
    assert any(
        item["outcome"] == "net_wealth"
        and item["code"] == "inventory_unknown"
        and item["ids"] == ["debts"]
        for item in compact["limitations"]
    )
    repeated = {
        section: {"update": shown[section]}
        for section in ("accounts", "assets", "debts", "goals", "transactions")
    }
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    unchanged = run("change", *opts, *binding, request=repeated)["result"]
    assert unchanged == {
        "status": "unchanged",
        "confirmation_token": None,
        "changes": [],
    }
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    # Availability is optional, and goes through the same joint change mechanism.
    savings = next(item for item in shown["accounts"] if item["id"] == "savings")
    home = shown["assets"][0]
    apply(
        path,
        {
            "accounts": {
                "update": [
                    {
                        **savings,
                        "availability": "free",
                        "availability_note": "Expliciete synthetische verklaring",
                    }
                ]
            },
            "assets": {"update": [{**home, "availability": "restricted"}]},
        },
    )
    enriched = run("show", *opts)["result"]
    summary = run("summary", *opts)["result"]
    assert summary["availability"][0]["known_free_total"] == "10000"
    assert summary["availability"][0]["known_restricted_total"] == "300000"
    rows = convert_export(FIXTURES / "bank-updated.csv")
    source.write_text(json.dumps(rows))
    prepared = export_change(enriched, rows)
    preview = run("change", *opts, *binding, request=prepared)["result"]
    assert len(preview["changes"]) == 2
    correction = next(item for item in preview["changes"] if item["id"] == "syn_SYN004")
    assert correction["after"]["category"] == "Boodschappen"
    assert correction["after"]["source"] == "Synthetische bankexport"
    apply(path, prepared, *binding)
    # Actual standalone import correction also preserves every new record/field.
    source.write_text(json.dumps([{**rows[0], "amount": "-87.50"}]))
    args = ("import-transactions", *opts, "--file", str(source), "--format", "json")
    preview = run(*args)["result"]
    run(*args, "--confirmation-token", preview["confirmation_token"])
    after = run("show", *opts)["result"]
    for section in ("accounts", "assets", "debts", "goals"):
        assert after[section] == enriched[section]
    assert run("summary", *opts)["result"] == summary
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    assert run(*args)["result"]["status"] == "unchanged"
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime


def test_overdraft_validation_and_joint_correction(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    opts = ("--context", str(path))
    run("init", *opts)
    request = wealth_request()
    apply(path, request)
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    debt = request["debts"]["add"][1]
    bank = request["accounts"]["add"][1]
    invalid: list[dict[str, Any]] = [
        {"debts": {"update": [{**debt, **patch}]}}
        for patch in (
            {"amount": "501"},
            {"amount": None},
            {"currency": "USD"},
            {"as_of": "2026-10-05"},
            {"account_id": "missing"},
            {"type": "loan"},
            {"id": "home"},
        )
    ] + [
        {"debts": {"add": [{**debt, "id": "second"}]}},
        {"accounts": {"delete": ["overdrawn"]}},
        {"accounts": {"update": [{**bank, "balance": "-600"}]}},
        {"accounts": {"update": [{**bank, "balance": None}]}},
        {"accounts": {"update": [{**bank, "balance": "1"}]}},
        {"debts": {"add": [{**debt, "id": "home", "account_id": None}]}},
    ]
    for bad in invalid:
        run("change", *opts, request=bad, success=False)
        assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    corrected = {
        "accounts": {"update": [{**bank, "balance": "-600"}]},
        "debts": {"update": [{**debt, "amount": "600"}]},
    }
    preview = run("change", *opts, request=corrected)["result"]
    assert (
        run(
            "change",
            *opts,
            request={
                **corrected,
                "confirmation_token": preview["confirmation_token"],
                "debts": {"delete": ["overdraft"]},
            },
            success=False,
        )["error"]["code"]
        == "STALE_CONFIRMATION"
    )
    assert path.read_bytes() == raw
    apply(path, corrected)
    assert (
        run("summary", *opts)["result"]["net_wealth"]["subtotals"][0]["known_total"]
        == "109400"
    )
    apply(
        path,
        {"accounts": {"delete": ["overdrawn"]}, "debts": {"delete": ["overdraft"]}},
    )
    apply(path, {"debts": {"delete": ["mortgage", "usd_loan", "unknown_loan"]}})
    assert run("show", *opts)["result"]["schema_version"] == "topo2.context/4"


@pytest.mark.parametrize("version", [1, 2, 3])
def test_old_context_reads_preview_and_noop_without_migration(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "old.json"
    account = {
        "id": "bank",
        "label": "Oud",
        "type": "savings",
        "balance": "100",
        "as_of": "2026-10-04",
    }
    path.write_text(
        json.dumps(
            {
                "schema_version": f"topo2.context/{version}",
                "context_id": "synthetic",
                "accounts": [account],
            }
        )
    )
    opts = ("--context", str(path))
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    for command in ("show", "summary", "context"):
        run(command, *opts)
    assert (
        run("change", *opts, request={"accounts": {"update": [account]}})["result"][
            "status"
        ]
        == "unchanged"
    )
    request = {"accounts": {"update": [{**account, "availability": "free"}]}}
    run("change", *opts, request=request)
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    apply(path, request)
    assert run("show", *opts)["result"]["schema_version"] == "topo2.context/4"
    apply(path, {"accounts": {"update": [account]}})
    assert run("show", *opts)["result"]["schema_version"] == "topo2.context/4"


def test_inventory_declaration_does_not_fill_unknown_debt(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    opts = ("--context", str(path))
    run("init", *opts)
    request = wealth_request()
    request["inventories"] = {
        "add": [
            {"id": domain, "status": "complete", "checked_on": "2026-10-14"}
            for domain in ("accounts", "assets", "debts")
        ]
    }
    apply(path, request)
    eur = run("summary", *opts)["result"]["net_wealth"]["subtotals"][0]
    assert eur["inventory_complete"] and not eur["complete"]
    assert eur["missing_ids"] == ["unknown_loan"]
    apply(
        path,
        {
            "debts": {
                "update": [
                    {
                        "id": "unknown_loan",
                        "label": "Bevestigd nul",
                        "type": "loan",
                        "amount": "0",
                        "as_of": "2026-10-14",
                    }
                ]
            }
        },
    )
    eur = run("summary", *opts)["result"]["net_wealth"]["subtotals"][0]
    assert eur["complete"] and eur["inventory_complete"]
    assert eur["known_total"] == "109500" and eur["missing_ids"] == []
    apply(
        path,
        {
            "inventories": {
                "update": [
                    {"id": "debts", "status": "partial", "checked_on": "2026-10-14"}
                ]
            }
        },
    )
    eur = run("summary", *opts)["result"]["net_wealth"]["subtotals"][0]
    assert eur["complete"] and not eur["inventory_complete"]
