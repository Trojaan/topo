#!/usr/bin/env python3
"""Synthetic, opt-in Topo 2 CLI latency gate. Never reads personal context."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from hashlib import sha256
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
                    "arguments": list(arguments),
                    "seconds": elapsed,
                    "stdout_bytes": len(process.stdout.encode()),
                    "peak_rss_bytes": int(
                        rss if sys.platform == "darwin" else rss * 1024
                    ),
                }
            )
            result = json.loads(process.stdout)["result"]
            if command == "report":
                measurements[-1]["html_bytes"] = result["html_bytes"]
                assert Path(result["output"]).stat().st_size == result["html_bytes"]
            return result, elapsed

        run("init")
        records = [
            {
                "id": f"bank_{i}",
                "label": f"Synthetic {i}",
                "type": "savings",
                "balance": "1234.56",
                "as_of": "2026-10-04",
                "availability": "free" if i % 2 == 0 else "restricted",
            }
            for i in range(1000)
        ]
        request: dict[str, Any] = {
            "accounts": {"add": records},
            "goals": {
                "add": [
                    {
                        "id": f"goal_{i}",
                        "name": f"Synthetic goal {i}",
                        "target_amount": "10000",
                        "reserved_amount": "4000"
                        if i % 3 == 0
                        else "0"
                        if i % 3 == 1
                        else None,
                        "monthly_contribution": "200",
                        "priority": "normal",
                        "note": "Synthetic intention",
                    }
                    for i in range(100)
                ]
            },
            "cashflows": {
                "add": [
                    {
                        "id": "salary",
                        "label": "Synthetic income",
                        "kind": "income",
                        "amount": "3000",
                        "frequency": "four_weekly",
                        "start_date": "2026-10-14",
                    },
                    {
                        "id": "costs",
                        "label": "Synthetic costs",
                        "kind": "expense",
                        "amount": {"lower": "80", "upper": "120"},
                        "frequency": "weekly",
                        "start_date": "2026-10-14",
                    },
                    {
                        "id": "insurance",
                        "label": "Synthetic annual cost",
                        "kind": "expense",
                        "amount": "1200",
                        "frequency": "yearly",
                        "start_date": "2026-10-14",
                    },
                    {
                        "id": "unknown_cost",
                        "label": "Unknown cost",
                        "kind": "expense",
                        "frequency": "monthly",
                        "start_date": "2026-10-14",
                        "debt_id": "synthetic_unknown",
                    },
                    {
                        "id": "dollar_income",
                        "label": "Synthetic dollar income",
                        "kind": "income",
                        "amount": "50",
                        "currency": "USD",
                        "frequency": "monthly",
                        "start_date": "2026-10-14",
                    },
                ]
            },
            "cashflow_settings": {
                "EUR": {"minimum_reserve": "5000", "note": "Synthetic flexibility"}
            },
            "assets": {
                "add": [
                    {
                        "id": "synthetic_home",
                        "label": "Synthetic home",
                        "type": "property",
                        "value": "300000",
                        "as_of": "2026-10-04",
                        "availability": "restricted",
                    }
                ]
            },
            "debts": {
                "add": [
                    {
                        "id": "synthetic_mortgage",
                        "label": "Synthetic mortgage",
                        "type": "mortgage",
                        "amount": "200000",
                        "as_of": "2026-10-04",
                    },
                    {
                        "id": "synthetic_unknown",
                        "label": "Synthetic unknown debt",
                        "type": "loan",
                    },
                    {
                        "id": "synthetic_usd",
                        "label": "Synthetic dollar debt",
                        "type": "loan",
                        "amount": "100",
                        "currency": "USD",
                        "as_of": "2026-10-04",
                    },
                ]
            },
        }
        preview, _ = run("change", request)
        request["confirmation_token"] = preview["confirmation_token"]
        run("change", request)
        _, show = run("show")
        summary_before, summary = run("summary")
        compact_before, _ = run(
            "context", None, "--reference-date", "2026-10-14", "--max-age-days", "30"
        )
        monthly_before, _ = run("monthly-room", None, "--reference-date", "2026-10-14")
        updated = [{**record, "balance": "1235.56"} for record in records]
        request = {"accounts": {"update": updated}}
        preview, preview_time = run("change", request)
        request["confirmation_token"] = preview["confirmation_token"]
        result, change_time = run("change", request)
        assert result["status"] == "applied" and len(result["changes"]) == 1000
        summary_result, _ = run("summary")
        assert summary_result["subtotals"][0]["known_total"] == "1535560.00"
        transactions = [
            {
                "id": f"transaction_{i:05d}",
                "account_id": f"bank_{i % 1000}",
                "booking_date": f"2026-{i % 3 + 8:02d}-{i % 28 + 1:02d}",
                "amount": "123.45" if i % 5 == 0 else "-123.45",
                "currency": "USD" if i % 7 == 0 else "EUR",
                "description": f"Synthetic transaction {i}",
                "category": f"Category {i % 11}",
                "source": "Synthetic export",
                "kind": ("income", "expense", "internal_transfer", "unknown")[i % 4],
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
            "2026-08-01",
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
        summary_after, summary = run("summary")
        assert "transactions" not in summary_after
        assert summary_after["goals"] == summary_result["goals"]
        assert (
            summary_after["reservation_comparison"]
            == summary_result["reservation_comparison"]
        )
        assert summary_after["goals"][0]["remaining_amount"] == "6000"
        assert summary_after["goals"][2]["remaining_amount"] is None
        assert len(json.dumps(summary_after)) == len(json.dumps(summary_before))
        assert (
            summary_after["net_wealth"]["subtotals"][0]["known_total"] == "1335560.00"
        )
        assert summary_after["net_wealth"]["subtotals"][0]["missing_ids"] == [
            "synthetic_unknown"
        ]
        updated = [{**record, "balance": "1235.57"} for record in records]
        request = {"accounts": {"update": updated}}
        preview, preview_time = run("change", request)
        request["confirmation_token"] = preview["confirmation_token"]
        _, change_time = run("change", request)
        compact, compact_time = run(
            "context", None, "--reference-date", "2026-10-14", "--max-age-days", "30"
        )
        assert "transactions" not in compact
        assert len(json.dumps(compact)) == len(json.dumps(compact_before))
        # Omitted labels must survive a changed import, then a repeated import.
        preserved = [
            {
                key: value
                for key, value in record.items()
                if key not in ("category", "source", "kind")
            }
            for record in transactions[:1000]
        ]
        for record in preserved:
            record["amount"] = "-123.47"
        source.write_text(json.dumps(preserved), encoding="utf-8")
        preview, import_preview = run("import-transactions", None, *import_args)
        assert preview["updated"] == 1000
        assert all(
            item["after"]["category"]
            == transactions[int(item["id"].split("_")[-1])]["category"]
            and item["after"]["kind"]
            == transactions[int(item["id"].split("_")[-1])]["kind"]
            and item["after"]["source"] == "Synthetic export"
            for item in preview["changes"]
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
        aggregate, aggregate_time = run("aggregate-transactions")
        assert aggregate["count"] == args.transactions
        assert len(aggregate["totals"]) == 2 and aggregate["groups"] == []
        grouped, grouped_time = run(
            "aggregate-transactions",
            None,
            "--group-by",
            "month",
            "--group-by",
            "category",
        )
        assert sum(group["count"] for group in grouped["groups"]) == args.transactions
        assert len(grouped["groups"]) == 66
        filtered, filtered_time = run(
            "aggregate-transactions",
            None,
            "--from-date",
            "2026-08-01",
            "--to-date",
            "2026-10-31",
            "--account",
            "bank_0",
            "--currency",
            "EUR",
            "--category",
            "Category 10",
            "--group-by",
            "month",
        )
        assert filtered["count"] > 0 and len(filtered["coverage"]) == 1
        monthly_after, monthly_time = run(
            "monthly-room", None, "--reference-date", "2026-10-14"
        )
        assert monthly_after == monthly_before
        assert compact["monthly_room"] == monthly_before
        assert "transactions" not in monthly_after
        goal_request = {
            "goals": {
                "update": [
                    {**record, "monthly_contribution": "250"}
                    for record in compact["goals"]
                ]
            }
        }
        goal_preview, goal_preview_time = run("change", goal_request)
        assert len(goal_preview["changes"]) == 100
        goal_request["confirmation_token"] = goal_preview["confirmation_token"]
        _, goal_update_time = run("change", goal_request)
        goal_request.pop("confirmation_token")
        goal_noop, goal_noop_time = run("change", goal_request)
        assert goal_noop["status"] == "unchanged"
        assert goal_noop["confirmation_token"] is None
        assert (
            run("monthly-room", None, "--reference-date", "2026-10-14")[0]
            == monthly_before
        )
        report_timings: dict[str, float] = {}
        report_phases: list[dict[str, Any]] = []
        for label, period in (
            ("all", ()),
            ("bounded", ("--from-date", "2026-08-01", "--to-date", "2026-10-31")),
        ):
            result, elapsed = run(
                "report",
                None,
                "--output",
                str(Path(directory) / f"{label}.html"),
                "--reference-date",
                "2026-10-14",
                *period,
            )
            report_timings["report_" + label] = elapsed
            # Separate process: read/validation, projection and pure rendering
            # wall times. RSS is cumulative for this diagnostic process; the
            # production CLI process peak is recorded independently above.
            profile_code = """
import hashlib, json, resource, sys
from pathlib import Path
from time import perf_counter
from topo_v2.storage import read
from topo_v2.reports import build_report
from topo_v2.report_models import ReportQuery
from topo_v2.report_html import render_report
started = perf_counter()
raw, context = read(Path(sys.argv[1]))
read_seconds = perf_counter() - started
query = ReportQuery(reference_date='2026-10-14',
    from_date='2026-08-01' if sys.argv[2] == 'bounded' else None,
    to_date='2026-10-31' if sys.argv[2] == 'bounded' else None)
started = perf_counter()
data = build_report(context, raw, query)
calculation_seconds = perf_counter() - started
started = perf_counter()
html = render_report(data).encode('utf-8')
rendering_seconds = perf_counter() - started
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps(dict(read_validation_seconds=read_seconds,
    calculation_seconds=calculation_seconds, rendering_seconds=rendering_seconds,
    html_bytes=len(html), html_sha256=hashlib.sha256(html).hexdigest(),
    peak_rss_bytes=int(rss if sys.platform == 'darwin' else rss * 1024))))
"""
            profile = subprocess.run(
                [sys.executable, "-c", profile_code, str(path), label],
                capture_output=True,
                text=True,
                check=True,
                env=environment,
            )
            phases = json.loads(profile.stdout)
            phases["selection"] = label
            report_phases.append(phases)
            assert phases["html_bytes"] == result["html_bytes"]
            assert (
                phases["html_sha256"]
                == sha256(Path(result["output"]).read_bytes()).hexdigest()
            )
        timings = {
            **report_timings,
            "goal_preview_100": goal_preview_time,
            "goal_update_100": goal_update_time,
            "goal_unchanged_100": goal_noop_time,
            "monthly_room": monthly_time,
            "aggregate": aggregate_time,
            "aggregate_month_category": grouped_time,
            "aggregate_filtered": filtered_time,
            "show": show,
            "summary": summary,
            "context": compact_time,
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
                    "goals": 100,
                    "transactions": args.transactions,
                    "environment": {
                        "platform": platform.platform(),
                        "python": platform.python_version(),
                    },
                    "measurements": measurements,
                    "report_phases": report_phases,
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
