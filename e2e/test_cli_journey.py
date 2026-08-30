from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_topo(
    *arguments: str, request: dict[str, Any] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "topo", *arguments],
        check=False,
        capture_output=True,
        input=json.dumps(request) if request is not None else None,
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

    analysis_request = {
        "contract_version": "topo.cli/0.1",
        "analysis_id": "analysis.context_inventory",
        "analysis_contract_version": "0.1",
        "context_id": response["result"]["context_id"],
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": response["result"]["household_id"],
        },
        "as_of_date": "2026-08-25",
        "period": None,
        "reporting_currency": None,
        "scenario": None,
    }
    analyzed = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request=analysis_request,
    )
    assert analyzed.returncode == 0, analyzed.stderr
    analysis = parse_json(analyzed)
    components = {
        component["component_id"]: component
        for component in analysis["result"]["components"]
    }
    assert components["analysis.context_inventory/inventory"]["status"] == "complete"
    assert components["analysis.net_worth/total"]["status"] == "unavailable"
    assert "value" not in components["analysis.net_worth/total"]
    assert analysis["generation_before"] == generation_id
    assert analysis["generation_after"] == generation_id

    workflow = run_topo(
        "workflow",
        "next",
        "--package",
        str(package),
        "--json",
        request={
            "contract_version": "topo.cli/0.1",
            "context_id": response["result"]["context_id"],
            "analysis_id": "analysis.net_worth",
            "analysis_scope": analysis_request["analysis_scope"],
            "as_of_date": "2026-08-25",
        },
    )
    assert workflow.returncode == 0, workflow.stderr
    workflow_body = parse_json(workflow)
    action = workflow_body["result"]["actions"][0]
    assert action["reason_code"] == "NET_WORTH_NEEDS_ACCOUNT_BALANCE"
    assert action["command"] == "proposal.submit"
    assert action["request_template"] == {"proposal_type": "account_balance"}
    assert "shell" not in json.dumps(action).lower()
    assert workflow_body["generation_before"] == generation_id
    assert workflow_body["generation_after"] == generation_id
    assert (package / "CURRENT").read_text().strip() == generation_id

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


def test_unknown_major_contract_version_fails_without_creating_context(
    tmp_path: Path,
) -> None:
    package = tmp_path / "incompatible.topo"
    completed = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        "--json",
        request={"contract_version": "topo.cli/1.0"},
    )

    assert completed.returncode != 0
    refusal = parse_json(completed)
    assert refusal["diagnostics"][0]["code"] == "INCOMPATIBLE_CONTRACT_VERSION"
    assert refusal["diagnostics"][0]["effect"] == "none"
    assert not package.exists()


def test_checksum_tampering_blocks_publication_without_switching_generation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "tampered.topo"
    initialized = run_topo("context", "init", "--package", str(package), "--json")
    assert initialized.returncode == 0, initialized.stderr
    generation_id = parse_json(initialized)["result"]["generation_id"]
    entities = package / "generations" / generation_id / "entities.json"
    entities.write_bytes(entities.read_bytes() + b" ")
    current_before = (package / "CURRENT").read_bytes()

    blocked = run_topo("context", "init", "--package", str(package), "--json")

    assert blocked.returncode != 0
    refusal = parse_json(blocked)
    assert refusal["diagnostics"][0]["code"] == "PACKAGE_INTEGRITY_FAILED"
    assert refusal["diagnostics"][0]["effect"] == "none"
    assert (package / "CURRENT").read_bytes() == current_before
