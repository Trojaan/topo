from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate
from test_topo_v2_transactions_journey import run
from topo2_input_fixture import FIXTURES, convert_export, export_change, first_request


def test_sources_combined_repeated_updated_and_explicit_clear(tmp_path: Path) -> None:
    context = tmp_path / "context.json"
    options = ("--context", str(context))
    run("init", *options)
    schemas = run("contract")["result"]["commands"]
    source = tmp_path / "converted.json"
    source.write_text(json.dumps(convert_export(FIXTURES / "bank.csv")))
    binding = tuple(
        arg
        for path in [
            FIXTURES / "bank.csv",
            FIXTURES / "saldo-betaal.png",
            FIXTURES / "saldo-spaar.png",
            FIXTURES / "doel.txt",
            source,
        ]
        for arg in ("--source", str(path))
    )
    request = first_request()
    validate(request, schemas["change"]["input"])
    raw = context.read_bytes()
    preview = run("change", *options, *binding, request=request)["result"]
    validate(preview, schemas["change"]["output"])
    assert len(preview["changes"]) == 7 and context.read_bytes() == raw
    request["confirmation_token"] = preview["confirmation_token"]
    source.write_bytes(source.read_bytes() + b" ")
    error = run("change", *options, *binding, request=request, success=False)
    assert error["error"]["code"] == "STALE_CONFIRMATION"
    assert context.read_bytes() == raw
    del request["confirmation_token"]
    preview = run("change", *options, *binding, request=request)["result"]
    request["confirmation_token"] = preview["confirmation_token"]
    # Scripted confirmation proves mechanics, not human authorization.
    assert (
        run("change", *options, *binding, request=request)["result"]["status"]
        == "applied"
    )
    summary = run("summary", *options)["result"]
    assert summary["subtotals"][0]["known_total"] == "8914.50"
    assert summary["goals"][0]["known_amount"] == "6400.00"
    assert summary["goals"][0]["percentage"] == "64.00"
    shown = run("show", *options)["result"]
    repeated = {
        "contract_version": "topo2.cli/3",
        **{
            section: {"update": shown[section]}
            for section in ("accounts", "goals", "transactions")
        },
    }
    raw = context.read_bytes()
    unchanged = run("change", *options, *binding, request=repeated)["result"]
    validate(unchanged, schemas["change"]["output"])
    assert unchanged == {
        "status": "unchanged",
        "confirmation_token": None,
        "changes": [],
    }
    assert context.read_bytes() == raw
    updated_rows = convert_export(FIXTURES / "bank-updated.csv")
    assert {row["id"] for row in updated_rows[:4]} == {
        row["id"] for row in convert_export(FIXTURES / "bank.csv")
    }
    source.write_text(json.dumps(updated_rows))
    import_args = (
        "import-transactions",
        *options,
        "--file",
        str(source),
        "--format",
        "json",
        "--details",
    )
    imported_preview = run(*import_args)["result"]
    assert (
        imported_preview["added"],
        imported_preview["updated"],
        imported_preview["skipped"],
    ) == (1, 1, 3)
    correction = next(
        item for item in imported_preview["changes"] if item["id"] == "syn_SYN004"
    )
    assert correction["after"]["category"] == "Boodschappen"
    assert correction["after"]["source"] == "Synthetische bankexport"
    updated_request = export_change(shown, updated_rows)
    updated_binding = (*binding, "--source", str(FIXTURES / "bank-updated.csv"))
    preview = run("change", *options, *updated_binding, request=updated_request)[
        "result"
    ]
    assert len(preview["changes"]) == 2
    assert preview["changes"] == imported_preview["changes"]
    updated_request["confirmation_token"] = preview["confirmation_token"]
    run("change", *options, *updated_binding, request=updated_request)
    current = run("show", *options)["result"]
    assert (
        current["accounts"] == shown["accounts"] and current["goals"] == shown["goals"]
    )
    assert run(*import_args)["result"]["status"] == "unchanged"
    # Demonstrate the standalone path also applies preservation, not just previews it.
    rows = [dict(updated_rows[0], amount="-87.50")]
    source.write_text(json.dumps(rows))
    preview = run(*import_args)["result"]
    run(*import_args, "--confirmation-token", preview["confirmation_token"])
    record = run("transactions", *options, "--search", "gecorrigeerd")["result"][
        "records"
    ][0]
    assert (
        record["category"] == "Boodschappen"
        and record["source"] == "Synthetische bankexport"
    )
    source.write_text(
        json.dumps([{**rows[0], "category": None, "source": "Expliciete vervanging"}])
    )
    preview = run(*import_args)["result"]
    assert preview["changes"][0]["before"]["category"] == "Boodschappen"
    assert preview["changes"][0]["after"]["category"] is None
    run(*import_args, "--confirmation-token", preview["confirmation_token"])
    record = run("transactions", *options, "--search", "gecorrigeerd")["result"][
        "records"
    ][0]
    assert record["category"] is None and record["source"] == "Expliciete vervanging"
    raw = context.read_bytes()
    invalid = export_change(current, [{**updated_rows[0], "account_id": "unknown"}])
    assert (
        run("change", *options, request=invalid, success=False)["error"]["code"]
        == "INVALID_DATA"
    )
    assert context.read_bytes() == raw
    assert run("summary", *options)["result"] == summary
    assert (
        run(
            "change",
            *options,
            request={"contract_version": "topo2.cli/2"},
            success=False,
        )["error"]["code"]
        == "INVALID_DATA"
    )
