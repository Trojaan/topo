#!/usr/bin/env python3
"""Synthetic, opt-in Topo 2 CLI latency gate. Never reads personal context."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transactions", type=int, choices=(10_000, 100_000), default=10_000
    )
    args = parser.parse_args()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    with TemporaryDirectory(prefix="topo2-benchmark-") as directory:
        path = Path(directory) / "context.json"

        measurements: list[dict[str, Any]] = []

        def run(
            command: str, request: dict[str, Any] | None = None, *arguments: str
        ) -> tuple[dict[str, Any], float]:
            started = perf_counter()
            process = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import resource, sys; from topo_v2.cli import main; "
                        "code = main(); print('__TOPO_RSS__' + str(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss), file=sys.stderr); sys.exit(code)"
                    ),
                    command,
                    "--context",
                    str(path),
                    *arguments,
                ],
                input=json.dumps(request) if request else None,
                text=True,
                capture_output=True,
                check=True,
                env=environment,
            )
            elapsed = perf_counter() - started
            rss = float(process.stderr.split("__TOPO_RSS__")[-1].strip())
            measurements.append(
                {
                    "command": command,
                    "seconds": elapsed,
                    "stdout_bytes": len(process.stdout.encode()),
                    "peak_rss_bytes": int(
                        rss if sys.platform == "darwin" else rss * 1024
                    ),
                }
            )
            return json.loads(process.stdout)["result"], elapsed

        run("init")
        records = [
            {
                "id": f"bank_{i}",
                "label": f"Synthetic {i}",
                "type": "savings",
                "balance": "1234.56",
                "as_of": "2026-10-04",
            }
            for i in range(1000)
        ]
        request: dict[str, Any] = {"accounts": {"add": records}}
        preview, _ = run("change", request)
        request["confirmation_token"] = preview["confirmation_token"]
        run("change", request)
        _, show = run("show")
        _, summary = run("summary")
        updated = [{**record, "balance": "1235.56"} for record in records]
        request = {"accounts": {"update": updated}}
        preview, preview_time = run("change", request)
        request["confirmation_token"] = preview["confirmation_token"]
        result, change_time = run("change", request)
        assert result["status"] == "applied" and len(result["changes"]) == 1000
        summary_result, _ = run("summary")
        assert summary_result["subtotals"][0]["known_total"] == "1235560.00"
        transactions = [
            {
                "id": f"transaction_{i:05d}",
                "account_id": f"bank_{i % 1000}",
                "booking_date": f"2026-10-{i % 28 + 1:02d}",
                "amount": "-123.45",
                "currency": "EUR",
                "description": f"Synthetic transaction {i}",
                "category": "Free category",
            }
            for i in range(args.transactions)
        ]
        source = Path(directory) / "transactions.json"
        source.write_text(json.dumps(transactions), encoding="utf-8")
        import_args = ("--file", str(source), "--format", "json")
        preview, initial_import_preview = run("import-transactions", None, *import_args)
        imported, initial_import_update = run(
            "import-transactions",
            None,
            *import_args,
            "--confirmation-token",
            preview["confirmation_token"],
        )
        assert imported["added"] == args.transactions
        selected, search_time = run(
            "transactions",
            None,
            "--account",
            "bank_0",
            "--from-date",
            "2026-10-01",
            "--to-date",
            "2026-10-31",
            "--search",
            "SYNTHETIC",
        )
        assert selected["total"] == args.transactions // 1000
        request = {
            "transactions": {
                "update": [
                    {**record, "amount": "-123.46"} for record in transactions[:1000]
                ]
            }
        }
        preview, transaction_preview = run("change", request)
        request["confirmation_token"] = preview["confirmation_token"]
        changed, transaction_update = run("change", request)
        assert changed["status"] == "applied" and len(changed["changes"]) == 1000
        selected, _ = run(
            "transactions", None, "--account", "bank_0", "--max-amount", "-123.46"
        )
        assert selected["total"] == 1
        # Re-measure reads with the full transaction fixture present.
        _, show = run("show")
        _, summary = run("summary")
        updated = [{**record, "balance": "1235.57"} for record in records]
        request = {"accounts": {"update": updated}}
        preview, preview_time = run("change", request)
        request["confirmation_token"] = preview["confirmation_token"]
        _, change_time = run("change", request)
        # Omitted labels must survive a changed import, then a repeated import.
        preserved = [
            {key: value for key, value in record.items() if key != "category"}
            for record in transactions[:1000]
        ]
        for record in preserved:
            record["amount"] = "-123.47"
        source.write_text(json.dumps(preserved), encoding="utf-8")
        preview, import_preview = run("import-transactions", None, *import_args)
        assert preview["updated"] == 1000
        assert all(
            item["after"]["category"] == "Free category" for item in preview["changes"]
        )
        _, import_update = run(
            "import-transactions",
            None,
            *import_args,
            "--confirmation-token",
            preview["confirmation_token"],
        )
        unchanged, import_unchanged = run("import-transactions", None, *import_args)
        assert unchanged["status"] == "unchanged"
        request = {
            "transactions": {
                "update": [
                    {**record, "amount": "-123.48"} for record in transactions[:1000]
                ]
            }
        }
        preview, source_preview = run("change", request, "--source", str(source))
        request["confirmation_token"] = preview["confirmation_token"]
        _, source_update = run("change", request, "--source", str(source))
        del request["confirmation_token"]
        unchanged, source_unchanged = run("change", request, "--source", str(source))
        assert unchanged["status"] == "unchanged"
        timings = {
            "show": show,
            "summary": summary,
            "preview": preview_time,
            "confirmed_bulk_update": change_time,
            f"transaction_search_{args.transactions}": search_time,
            "initial_import_preview": initial_import_preview,
            "initial_import_update": initial_import_update,
            "transaction_preview_1000": transaction_preview,
            "transaction_update_1000": transaction_update,
            "preserving_import_preview_1000": import_preview,
            "preserving_import_update_1000": import_update,
            "preserving_import_unchanged_1000": import_unchanged,
            "source_bound_preview_1000": source_preview,
            "source_bound_update_1000": source_update,
            "source_bound_unchanged_1000": source_unchanged,
        }
        print(
            json.dumps(
                {
                    "accounts": 1000,
                    "transactions": args.transactions,
                    "environment": {
                        "platform": platform.platform(),
                        "python": platform.python_version(),
                    },
                    "measurements": measurements,
                    "seconds": timings,
                    "limit_seconds": 1.0 if args.transactions == 10_000 else None,
                },
                indent=2,
            )
        )
        return (
            0
            if args.transactions == 100_000
            or all(value < 1.0 for value in timings.values())
            else 1
        )


if __name__ == "__main__":
    raise SystemExit(main())
