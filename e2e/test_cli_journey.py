from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_topo(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "topo", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def parse_json(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert process.stdout, process.stderr
    value = json.loads(process.stdout)
    assert isinstance(value, dict)
    return value


def test_user_discovers_contract_and_publishes_first_context(tmp_path: Path) -> None:
    described = run_topo("contract", "describe", "--json")
    assert described.returncode == 0, described.stderr
    contract = parse_json(described)
    commands = {item["command"] for item in contract["result"]["commands"]}
    assert {"context.init", "proposal.submit", "proposal.confirm"} <= commands

    package = tmp_path / "journey.topo"
    initialized = run_topo("context", "init", "--package", str(package), "--json")
    assert initialized.returncode == 0, initialized.stderr
    response = parse_json(initialized)
    assert response["outcome"] == "succeeded"
    assert response["command"] == "context.init"
    assert response["result"]["context_id"]
    generation_id = response["result"]["generation_id"]

    # Persistence assertion: the CLI result agrees with the atomically published
    # canonical package, and every declared collection has the promised checksum.
    assert (package / "CURRENT").read_text().strip() == generation_id
    generation = package / "generations" / generation_id
    manifest = json.loads((generation / "manifest.json").read_text())
    assert manifest["context_id"] == response["result"]["context_id"]
    assert manifest["generation_id"] == generation_id
    for filename, expected in manifest["files"].items():
        digest = hashlib.sha256((generation / filename).read_bytes()).hexdigest()
        assert expected == f"sha256:{digest}"

    # Product safety assertion: initialization cannot silently replace a
    # published financial context.
    repeated = run_topo("context", "init", "--package", str(package), "--json")
    assert repeated.returncode != 0
    refusal = parse_json(repeated)
    assert refusal["outcome"] == "rejected"
    assert refusal["diagnostics"][0]["code"] == "CONTEXT_ALREADY_EXISTS"
    assert (package / "CURRENT").read_text().strip() == generation_id
