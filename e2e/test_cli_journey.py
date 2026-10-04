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


def test_cli_help_and_usage_errors_are_discoverable() -> None:
    assert "upgrade" in run_topo("--help").stdout
    upgrade = run_topo("upgrade", "--json")
    assert upgrade.returncode == 2
    assert "package manager" in parse_json(upgrade)["message"]
    described = parse_json(run_topo("contract", "describe", "--json"))
    commands = {item["command"]: item for item in described["result"]["commands"]}
    assert (
        commands["context.privacy_scrub"]["cli_command"] == "topo context privacy-scrub"
    )
    assert "package-independent" in run_topo("contract", "describe", "--help").stdout
    assert "--request PATH" in run_topo("workflow", "respond", "--help").stdout
    assert (
        "Contract ID: workflow.respond"
        in run_topo("workflow", "respond", "--help").stdout
    )

    invalid = run_topo("analyze", "run", "--package", "unused.topo", "{}", "--json")
    assert invalid.returncode == 2
    body = parse_json(invalid)
    assert body["command"] == "analyze.run"
    assert body["diagnostics"][0]["code"] == "INVALID_USAGE"
    assert "--request PATH" in body["diagnostics"][0]["params"]["hint"]
    missing_path = run_topo(
        "workflow", "respond", "--package", "unused.topo", "--request", "--json"
    )
    assert missing_path.returncode == 2
    assert parse_json(missing_path)["diagnostics"][0]["code"] == "INVALID_USAGE"


def test_context_summary_uses_current_generation_and_explains_blockers(
    tmp_path: Path,
) -> None:
    package = tmp_path / "summary.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    generation = initialized["generation_after"]
    summary = run_topo(
        "context",
        "summary",
        "--package",
        str(package),
        "--as-of",
        "2026-09-29",
        "--json",
    )
    assert summary.returncode == 0, summary.stderr
    body = parse_json(summary)
    result = body["result"]
    assert body["generation_before"] == body["generation_after"] == generation
    assert result["entity_counts"] == {"context": 1, "person": 1, "household": 1}
    assert result["account_balances"] == []
    assert result["diagnostics"][0]["code"] == "MISSING_NET_WORTH_INPUT"
    assert "used_assertion_refs" not in json.dumps(result)
    ref = result["diagnostics"][0]["explain_ref"]
    explained = run_topo(
        "explain",
        "--package",
        str(package),
        "--ref",
        f"{ref['ref_type']}:{ref['id']}",
        "--json",
    )
    assert explained.returncode == 0, explained.stderr
    assert parse_json(explained)["result"]["generation_id"] == generation

    import_request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "01991a00-0000-7000-8000-000000000091",
        "context_id": initialized["context_id"],
        "expected_generation": generation,
        "actor": {"actor_type": "source_adapter", "actor_id": "demo-adapter"},
        "reason": "Synthetic account for summary test",
        "adapter": {"adapter_id": "demo-adapter", "adapter_version": "0.1.0"},
        "records": [
            {
                "source_id": "demo-account",
                "record_id": "demo-1",
                "booking_date": "2026-09-28",
                "money": {"amount": "-5.00", "currency": "EUR"},
                "description": "Synthetic transaction",
            }
        ],
        "authorization": None,
    }
    preview = parse_json(
        run_topo(
            "source",
            "import",
            "--package",
            str(package),
            "--json",
            request=import_request,
        )
    )
    import_request["authorization"] = {
        "preview_ref": preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "test-user"},
        "authorized_at": "2026-09-29T12:00:00+02:00",
    }
    imported = parse_json(
        run_topo(
            "source",
            "import",
            "--package",
            str(package),
            "--json",
            request=import_request,
        )
    )
    newer = parse_json(
        run_topo(
            "context",
            "summary",
            "--package",
            str(package),
            "--as-of",
            "2026-09-29",
            "--json",
        )
    )
    assert newer["result"]["generation_id"] == imported["generation_after"]
    assert newer["result"]["account_balances"] == [
        {
            "account_id": imported["result"]["account_refs"][0]["id"],
            "status": "missing",
        }
    ]


def test_canonical_record_schemas_are_discoverable() -> None:
    for record_type in ("entities", "assertions", "evidence", "proposals"):
        response = run_topo("contract", "record-schema", record_type, "--json")
        assert response.returncode == 0, response.stderr
        result = parse_json(response)["result"]
        assert result["context_schema_version"] == "topo.context/0.2"
        assert result["schema"]["properties"]["schema_version"] == {
            "const": "topo.context/0.2"
        }
        assert result["schema"]["properties"]["records"]["items"]


def test_compact_analysis_and_discovery_views(tmp_path: Path) -> None:
    package = tmp_path / "views.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    request = {
        "contract_version": "topo.cli/0.1",
        "context_id": initialized["context_id"],
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": initialized["result"]["household_id"],
        },
        "as_of_date": "2026-09-29",
    }
    analysis = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--compact",
        "--json",
        request={
            **request,
            "analysis_id": "analysis.context_inventory",
            "analysis_contract_version": "0.1",
            "period": None,
            "scenario": None,
        },
    )
    assert analysis.returncode == 0, analysis.stderr
    compact = parse_json(analysis)["result"]
    assert compact["view"] == "compact"
    assert "inventory_steps" not in compact
    assert "used_assertion_refs" not in json.dumps(compact)

    discovery = run_topo(
        "discover",
        "run",
        "--package",
        str(package),
        "--compact",
        "--json",
        request=request,
    )
    assert discovery.returncode == 0, discovery.stderr
    assert parse_json(discovery)["result"]["view"] == "compact"
    table = run_topo(
        "discover", "run", "--package", str(package), "--table", request=request
    )
    assert table.returncode == 0, table.stderr
    assert "PROJECTED NEXT PERIOD" in table.stdout

    shorthand = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--analysis",
        "context_inventory",
        "--as-of",
        "2026-09-29",
        "--compact",
        "--json",
    )
    assert shorthand.returncode == 0, shorthand.stderr
    assert (
        parse_json(shorthand)["result"]["analysis_id"] == "analysis.context_inventory"
    )
    shorthand_discovery = run_topo(
        "discover",
        "run",
        "--package",
        str(package),
        "--as-of",
        "2026-09-29",
        "--compact",
        "--json",
    )
    assert shorthand_discovery.returncode == 0, shorthand_discovery.stderr
    shorthand_workflow = run_topo(
        "workflow",
        "next",
        "--package",
        str(package),
        "--as-of",
        "2026-09-29",
        "--json",
    )
    assert shorthand_workflow.returncode == 0, shorthand_workflow.stderr


def test_user_discovers_contract_and_publishes_first_context(tmp_path: Path) -> None:
    described = run_topo("contract", "describe", "--json")
    assert described.returncode == 0, described.stderr
    contract = parse_json(described)
    commands = {item["command"] for item in contract["result"]["commands"]}
    assert {
        "context.init",
        "context.verify",
        "proposal.submit",
        "proposal.confirm",
    } <= commands

    package = tmp_path / "journey.topo"
    initialized = run_topo("context", "init", "--package", str(package), "--json")
    assert initialized.returncode == 0, initialized.stderr
    response = parse_json(initialized)
    assert response["outcome"] == "succeeded"
    assert response["command"] == "context.init"
    assert response["result"]["context_id"]
    generation_id = response["result"]["generation_id"]

    verified = run_topo("context", "verify", "--package", str(package), "--json")
    assert verified.returncode == 0, verified.stderr
    verification = parse_json(verified)
    assert verification["command"] == "context.verify"
    assert verification["result"] == {
        "context_id": response["result"]["context_id"],
        "generation_id": generation_id,
        "generations_verified": 1,
        "evidence_records_verified": 0,
    }

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


def test_workflow_next_exposes_and_accepts_a_json_request_file(
    tmp_path: Path,
) -> None:
    help_result = run_topo("workflow", "next", "--help")

    assert help_result.returncode == 0, help_result.stderr
    assert "--request PATH" in help_result.stdout

    package = tmp_path / "workflow.topo"
    initialized = run_topo("context", "init", "--package", str(package), "--json")
    assert initialized.returncode == 0, initialized.stderr
    context = parse_json(initialized)
    request_path = tmp_path / "workflow-next.json"
    request_path.write_text(
        json.dumps(
            {
                "contract_version": "topo.cli/0.1",
                "context_id": context["result"]["context_id"],
                "analysis_id": "analysis.net_worth",
                "analysis_scope": {
                    "scope_type": "household",
                    "entity_id": context["result"]["household_id"],
                },
                "as_of_date": "2026-08-31",
            }
        ),
        encoding="utf-8",
    )

    workflow = run_topo(
        "workflow",
        "next",
        "--package",
        str(package),
        "--request",
        str(request_path),
        "--json",
    )

    assert workflow.returncode == 0, workflow.stderr
    body = parse_json(workflow)
    assert body["outcome"] == "succeeded"
    assert body["trace"]["normalized_request"] == json.loads(
        request_path.read_text(encoding="utf-8")
    )


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
