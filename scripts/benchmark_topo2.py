#!/usr/bin/env python3
"""Synthetic, opt-in Topo 2 CLI latency gate. Never reads personal context."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any


def main() -> int:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    with TemporaryDirectory(prefix="topo2-benchmark-") as directory:
        path = Path(directory) / "context.json"

        def run(
            command: str, request: dict[str, Any] | None = None
        ) -> tuple[dict[str, Any], float]:
            started = perf_counter()
            process = subprocess.run(
                [sys.executable, "-m", "topo_v2", command, "--context", str(path)],
                input=json.dumps(request) if request else None,
                text=True,
                capture_output=True,
                check=True,
                env=environment,
            )
            elapsed = perf_counter() - started
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
        timings = {
            "show": show,
            "summary": summary,
            "preview": preview_time,
            "confirmed_bulk_update": change_time,
        }
        print(
            json.dumps(
                {"records": 1000, "seconds": timings, "limit_seconds": 1.0}, indent=2
            )
        )
        return 0 if all(value < 1.0 for value in timings.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
