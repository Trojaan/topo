#!/usr/bin/env python3
"""Mechanically verify installed Topo 2; scripted tokens are not human consent."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def smoke(executable: Path) -> dict[str, Any]:
    executable = executable.resolve()
    version = subprocess.run(
        [str(executable), "--version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    transcript: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="topo2-smoke-") as directory:
        context = Path(directory) / "context.json"

        def run(
            command: str, request: dict[str, Any] | None = None, *arguments: str
        ) -> dict[str, Any]:
            args = [str(executable), command, "--json", *arguments]
            if command != "contract":
                args.extend(["--context", str(context)])
            process = subprocess.run(
                args,
                input=json.dumps(request) if request is not None else None,
                capture_output=True,
                text=True,
                check=True,
            )
            response: dict[str, Any] = json.loads(process.stdout)
            transcript.append({"command": command, "response": response})
            result: dict[str, Any] = response["result"]
            return result

        assert "change" in run("contract")["commands"]
        run("init")
        original = context.read_bytes()
        request: dict[str, Any] = {
            "accounts": {
                "add": [
                    {
                        "id": "broker",
                        "label": "Synthetic broker cash",
                        "type": "investment",
                        "balance": "100.10",
                        "availability": "free",
                        "as_of": "2026-10-13",
                    }
                ]
            },
            "assets": {
                "add": [
                    {
                        "id": "etf",
                        "label": "Synthetic ETF",
                        "type": "etf",
                        "value": "200.20",
                        "availability": "restricted",
                        "as_of": "2026-10-13",
                        "broker_account_id": "broker",
                    }
                ]
            },
            "goals": {
                "add": [
                    {
                        "id": "buffer",
                        "name": "Synthetic buffer",
                        "target_amount": "1000",
                        "account_ids": ["broker"],
                        "asset_ids": ["etf"],
                    }
                ]
            },
        }
        source = Path(directory) / "source.txt"
        source.write_text(
            "Synthetic broker cash 100.10 EUR; ETF 200.20 EUR; buffer 1000 EUR.\n",
            encoding="utf-8",
        )
        binding = ("--source", str(source))
        preview = run("change", request, *binding)
        assert preview["status"] == "preview" and len(preview["changes"]) == 3
        assert context.read_bytes() == original
        request["confirmation_token"] = preview["confirmation_token"]
        assert run("change", request, *binding)["status"] == "applied"
        summary = run("summary")
        assert summary["subtotals"][0]["known_total"] == "300.30"
        assert summary["goals"][0]["percentage"] == "30.0300"
        state = run("show")
        assert (
            len(state["accounts"]) == len(state["assets"]) == len(state["goals"]) == 1
        )
        assert "history" not in state
        transactions = Path(directory) / "transactions.csv"
        transactions.write_text(
            "id,account_id,booking_date,amount,currency,description,category,source\n"
            "posting,broker,2026-10-13,-12.50,EUR,Synthetic groceries,Groceries,Smoke export\n",
            encoding="utf-8",
        )
        args = ("--file", str(transactions), "--format", "csv")
        original = context.read_bytes()
        preview = run("import-transactions", None, *args)
        assert preview["added"] == 1 and preview["status"] == "preview"
        assert context.read_bytes() == original
        assert (
            run(
                "import-transactions",
                None,
                *args,
                "--confirmation-token",
                preview["confirmation_token"],
            )["status"]
            == "applied"
        )
        original = context.read_bytes()
        assert run("import-transactions", None, *args)["status"] == "unchanged"
        selected = run(
            "transactions",
            None,
            "--account",
            "broker",
            "--search",
            "GROCERIES",
            "--from-date",
            "2026-10-13",
            "--to-date",
            "2026-10-13",
        )
        assert selected["total"] == 1 and selected["records"][0]["amount"] == "-12.50"
        assert run("summary")["subtotals"][0]["known_total"] == "300.30"
        assert context.read_bytes() == original
        transactions.write_text(
            "id,account_id,booking_date,amount,currency,description\n"
            "posting,broker,2026-10-13,-13.50,EUR,Synthetic groceries\n",
            encoding="utf-8",
        )
        preview = run("import-transactions", None, *args)
        assert preview["updated"] == 1
        assert preview["changes"][0]["after"]["category"] == "Groceries"
        assert preview["changes"][0]["after"]["source"] == "Smoke export"
        run(
            "import-transactions",
            None,
            *args,
            "--confirmation-token",
            preview["confirmation_token"],
        )
        raw, mtime = context.read_bytes(), context.stat().st_mtime_ns
        assert run("import-transactions", None, *args)["status"] == "unchanged"
        assert context.read_bytes() == raw and context.stat().st_mtime_ns == mtime
        wealth_request: dict[str, Any] = {
            "accounts": {
                "add": [
                    {
                        "id": "overdrawn",
                        "label": "Synthetic overdraft account",
                        "type": "payment",
                        "balance": "-500",
                        "as_of": "2026-10-13",
                    },
                    {
                        "id": "usd",
                        "label": "Synthetic USD",
                        "type": "savings",
                        "balance": "1000",
                        "currency": "USD",
                        "as_of": "2026-10-13",
                    },
                ]
            },
            "assets": {
                "add": [
                    {
                        "id": "home",
                        "label": "Synthetic home",
                        "type": "property",
                        "value": "300000",
                        "as_of": "2026-10-13",
                    }
                ]
            },
            "debts": {
                "add": [
                    {
                        "id": "mortgage",
                        "label": "Synthetic mortgage",
                        "type": "mortgage",
                        "amount": "200000",
                        "as_of": "2026-10-13",
                    },
                    {
                        "id": "overdraft",
                        "label": "Same overdraft",
                        "type": "overdraft",
                        "amount": "500",
                        "account_id": "overdrawn",
                        "as_of": "2026-10-13",
                    },
                    {"id": "unknown", "label": "Unknown debt", "type": "loan"},
                    {
                        "id": "usd_loan",
                        "label": "Synthetic USD loan",
                        "type": "loan",
                        "amount": "100",
                        "currency": "USD",
                        "as_of": "2026-10-13",
                    },
                ]
            },
        }
        preview = run("change", wealth_request)
        assert context.read_bytes() == raw
        wealth_request["confirmation_token"] = preview["confirmation_token"]
        run("change", wealth_request)
        compact = run(
            "context", None, "--reference-date", "2026-10-14", "--max-age-days", "30"
        )
        assert "transactions" not in compact and len(compact["debts"]) == 4
        eur, usd = compact["summary"]["net_wealth"]["subtotals"]
        assert eur["known_total"] == "99800.30" and usd["known_total"] == "900"
        assert eur["missing_ids"] == ["unknown"] and not eur["complete"]
        assert not eur["inventory_complete"] and eur["linked_debt_ids"] == ["overdraft"]
        availability = compact["summary"]["availability"][0]
        assert availability["known_free_total"] == "100.10"
        assert availability["known_restricted_total"] == "200.20"
        assert "home" in availability["unknown_availability_ids"]
        state = run("show")
        assert state["schema_version"] == "topo2.context/4"
        repeated = {"debts": {"update": state["debts"]}}
        raw, mtime = context.read_bytes(), context.stat().st_mtime_ns
        assert run("change", repeated)["status"] == "unchanged"
        assert run("import-transactions", None, *args)["status"] == "unchanged"
        assert run("show")["debts"] == state["debts"]
        assert context.read_bytes() == raw and context.stat().st_mtime_ns == mtime
        return {
            "status": "passed",
            "version": version,
            "data": "synthetic",
            "transcript": transcript,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    proof = smoke(args.executable)
    payload = json.dumps(proof, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(
        f"{proof['version']}: synthetic source-bound changes, import preservation, compact context and net wealth passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
