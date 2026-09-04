from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).parents[1]


def _run(*arguments: str, request: dict[str, Any] | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "topo", *arguments, "--json"],
        cwd=PROJECT_ROOT,
        input=None if request is None else json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout or completed.stderr)
    return cast(dict[str, Any], json.loads(completed.stdout))


def _operation_id(index: int) -> str:
    return f"0198f1a0-0000-7000-8000-{index:012d}"


def _records(offset: int, count: int) -> list[dict[str, Any]]:
    first_day = date(2025, 1, 1)
    return [
        {
            "source_id": "synthetic-checking",
            "record_id": f"synthetic-{index:08d}",
            "booking_date": (first_day + timedelta(days=index % 365)).isoformat(),
            "money": {"amount": "1.00", "currency": "EUR"},
            "description": f"Synthetic performance record {index}",
        }
        for index in range(offset, offset + count)
    ]


def _build_fixture(
    package: Path, record_count: int, generations: int
) -> dict[str, Any]:
    initialized = _run("context", "init", "--package", str(package))
    context_id = cast(str, initialized["context_id"])
    generation_id = cast(str, initialized["generation_after"])
    batches = generations - 1
    base_size, remainder = divmod(record_count, batches)
    offset = 0
    for batch in range(batches):
        batch_size = base_size + (1 if batch < remainder else 0)
        request = {
            "contract_version": "topo.cli/0.1",
            "operation_id": _operation_id(batch + 1),
            "context_id": context_id,
            "expected_generation": generation_id,
            "actor": {
                "actor_type": "source_adapter",
                "actor_id": "adapter.synthetic-performance",
            },
            "reason": "Build a synthetic read-performance fixture",
            "adapter": {
                "adapter_id": "adapter.synthetic-performance",
                "adapter_version": "0.1.0",
            },
            "records": _records(offset, batch_size),
            "authorization": None,
        }
        preview = _run("source", "import", "--package", str(package), request=request)
        request["authorization"] = {
            "preview_ref": preview["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "benchmark"},
            "authorized_at": "2026-09-04T12:00:00+02:00",
        }
        imported = _run("source", "import", "--package", str(package), request=request)
        generation_id = cast(str, imported["generation_after"])
        offset += batch_size
    return {
        "context_id": context_id,
        "generation_id": generation_id,
        "household_id": initialized["result"]["household_id"],
    }


def _measure(arguments: tuple[str, ...], request: dict[str, Any] | None) -> float:
    started = time.perf_counter()
    _run(*arguments, request=request)
    return time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=7_500)
    parser.add_argument("--generations", type=int, default=6)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--budget-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.records < 1 or args.generations < 2 or args.runs < 1:
        parser.error(
            "records and runs must be positive; generations must be at least 2"
        )

    with tempfile.TemporaryDirectory(prefix="topo-read-benchmark-") as directory:
        package = Path(directory) / "synthetic.topo"
        fixture = _build_fixture(package, args.records, args.generations)
        scope = {
            "scope_type": "household",
            "entity_id": fixture["household_id"],
        }
        workflow_request = {
            "contract_version": "topo.cli/0.1",
            "context_id": fixture["context_id"],
            "analysis_id": "analysis.net_worth",
            "analysis_scope": scope,
            "as_of_date": "2026-09-04",
        }
        analysis_request = {
            **workflow_request,
            "analysis_contract_version": "0.1",
            "period": None,
            "reporting_currency": None,
            "scenario": None,
        }
        cases = {
            "context.status": (
                ("context", "status", "--package", str(package)),
                None,
            ),
            "workflow.next": (
                ("workflow", "next", "--package", str(package)),
                workflow_request,
            ),
            "analyze.run": (
                ("analyze", "run", "--package", str(package)),
                analysis_request,
            ),
        }
        failed = False
        for name, (arguments, request) in cases.items():
            _measure(arguments, request)
            timings = tuple(_measure(arguments, request) for _ in range(args.runs))
            median = statistics.median(timings)
            print(
                f"{name}: median={median:.3f}s "
                f"runs={','.join(f'{timing:.3f}' for timing in timings)}"
            )
            failed = failed or median >= args.budget_seconds
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
