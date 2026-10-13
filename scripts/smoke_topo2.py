#!/usr/bin/env python3
"""Exercise an installed Topo 2 using synthetic data and the standard library."""

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

        def run(command: str, request: dict[str, Any] | None = None) -> dict[str, Any]:
            args = [str(executable), command, "--json"]
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
        preview = run("change", request)
        assert preview["status"] == "preview" and len(preview["changes"]) == 3
        assert context.read_bytes() == original
        request["confirmation_token"] = preview["confirmation_token"]
        assert run("change", request)["status"] == "applied"
        summary = run("summary")
        assert summary["subtotals"][0]["known_total"] == "300.30"
        assert summary["goals"][0]["percentage"] == "30.0300"
        state = run("show")
        assert (
            len(state["accounts"]) == len(state["assets"]) == len(state["goals"]) == 1
        )
        assert "history" not in state
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
        f"{proof['version']}: synthetic init, preview, confirm, summary and show passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
