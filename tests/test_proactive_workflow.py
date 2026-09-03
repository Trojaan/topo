from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from topo.contracts import input_schema

PROJECT_ROOT = Path(__file__).parents[1]


def write_canonical_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def downgrade_to_context_01(package: Path, generation: str) -> None:
    generation_path = package / "generations" / generation
    collection_names = (
        "entities.json",
        "assertions.json",
        "evidence.json",
        "proposals.json",
    )
    for name in collection_names:
        path = generation_path / name
        value = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        value["schema_version"] = "topo.context/0.1"
        write_canonical_json(path, value)
    manifest_path = generation_path / "manifest.json"
    manifest = cast(
        dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    manifest["package_version"] = "0.1"
    manifest["context_schema_version"] = "topo.context/0.1"
    manifest["files"] = {
        name: "sha256:"
        + hashlib.sha256((generation_path / name).read_bytes()).hexdigest()
        for name in collection_names
    }
    write_canonical_json(manifest_path, manifest)


def run_topo(*args: str, request: dict[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "topo", *args, "--json"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return cast(dict[str, Any], json.loads(completed.stdout))


def test_account_inventory_batch_recalculates_net_worth_and_continues(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context.topo"
    initialized = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    context_id = initialized["context_id"]
    household_id = initialized["result"]["household_id"]
    generation = initialized["generation_after"]
    workflow_request = {
        "contract_version": "topo.cli/0.1",
        "context_id": context_id,
        "workflow_contract_version": "topo.workflow/0.2",
        "analysis_id": "analysis.net_worth",
        "analysis_scope": {"scope_type": "household", "entity_id": household_id},
        "as_of_date": "2026-08-31",
        "include_basis_context": True,
        "since_generation": generation,
        "reporting_currency": {
            "currency": "EUR",
            "allowed_rate_assertion_refs": [],
        },
    }
    first = run_topo(
        "workflow", "next", "--package", str(package), request=workflow_request
    )["result"]
    action = first["next_action"]
    assert action["reason_code"] == "BASIS_CONTEXT_NEEDS_ACCOUNTS"

    response = action["request_template"]
    response["actor"]["actor_id"] = "agent.topo"
    response["workflow_response"]["producer"] = {
        "producer_type": "agent",
        "producer_id": "agent.topo",
        "producer_version": "0.2.0",
    }
    response["workflow_response"]["items"] = [
        {
            "item_id": "01991a00-0000-7000-8000-000000000001",
            "label": "Hoofdrekening",
            "entity_type": "account",
            "classification": "payment_account",
            "money": {"amount": "685.22", "currency": "EUR"},
            "household_share": "1",
            "source": {"adapter_id": "csv-bank", "source_id": "main-account"},
        },
        {
            "item_id": "01991a00-0000-7000-8000-000000000002",
            "label": "Vakantierekening",
            "entity_type": "account",
            "classification": "savings_account",
            "money": {"amount": "0.00", "currency": "EUR"},
            "household_share": "1",
        },
    ]
    Draft202012Validator(input_schema("workflow.respond")).validate(response)
    proposed = run_topo(
        "workflow", "respond", "--package", str(package), request=response
    )
    assert proposed["outcome"] == "succeeded", proposed
    assert proposed["result"]["batch_id"]

    after_proposal = run_topo(
        "workflow",
        "next",
        "--package",
        str(package),
        request={
            **workflow_request,
            "since_generation": generation,
        },
    )["result"]
    authorization_action = after_proposal["next_action"]
    assert authorization_action["command"] == "proposal.confirm-batch"
    preview_request = authorization_action["request_template"]
    preview_request["actor"]["actor_id"] = "agent.topo"
    preview = run_topo(
        "proposal",
        "confirm-batch",
        "--package",
        str(package),
        request=preview_request,
    )
    assert preview["outcome"] == "requires_authorization"
    authorized_request = {
        **preview_request,
        "authorization": {
            "preview_ref": preview["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
            "authorized_at": "2026-09-03T10:00:00Z",
        },
    }
    confirmed = run_topo(
        "proposal",
        "confirm-batch",
        "--package",
        str(package),
        request=authorized_request,
    )
    assert confirmed["outcome"] == "succeeded"
    assert len(confirmed["result"]["entity_ids"]) == 2
    replayed = run_topo(
        "proposal",
        "confirm-batch",
        "--package",
        str(package),
        request=authorized_request,
    )
    assert replayed["outcome"] == "no_change"
    assert replayed["result"] == confirmed["result"]

    final = run_topo(
        "workflow",
        "next",
        "--package",
        str(package),
        request={
            **workflow_request,
            "since_generation": proposed["generation_after"],
        },
    )["result"]
    assert len(final["change_summary"]["confirmed"]) == 1
    assert final["next_action"]["reason_code"] == "BASIS_CONTEXT_NEEDS_ASSETS"
    net_worth = next(
        item
        for item in final["analysis_results"]
        if item["analysis_id"] == "analysis.net_worth"
    )
    total = next(
        item
        for item in net_worth["components"]
        if item["component_id"] == "net_worth/total"
    )
    assert net_worth["status"] == "provisional"
    assert total["value"] == {"amount": "685.22", "currency": "EUR"}

    current = final
    for expected_section in (
        "assets",
        "debts",
        "household",
        "cashflow",
        "pensions",
        "contracts_insurance",
        "goals",
    ):
        next_action = current["next_action"]
        assert next_action["affected_component"] == f"basis_context/{expected_section}"
        inventory_request = next_action["request_template"]
        inventory_request["actor"]["actor_id"] = "agent.topo"
        inventory_request["workflow_response"]["producer"] = {
            "producer_type": "agent",
            "producer_id": "agent.topo",
            "producer_version": "0.2.0",
        }
        submitted = run_topo(
            "workflow",
            "respond",
            "--package",
            str(package),
            request=inventory_request,
        )
        pending = run_topo(
            "workflow",
            "next",
            "--package",
            str(package),
            request=workflow_request,
        )["result"]
        batch_request = pending["next_action"]["request_template"]
        batch_request["actor"]["actor_id"] = "agent.topo"
        Draft202012Validator(input_schema("proposal.confirm-batch")).validate(
            batch_request
        )
        batch_preview = run_topo(
            "proposal",
            "confirm-batch",
            "--package",
            str(package),
            request=batch_request,
        )
        batch_request["authorization"] = {
            "preview_ref": batch_preview["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
            "authorized_at": "2026-09-03T10:00:00Z",
        }
        accepted = run_topo(
            "proposal",
            "confirm-batch",
            "--package",
            str(package),
            request=batch_request,
        )
        current = run_topo(
            "workflow",
            "next",
            "--package",
            str(package),
            request={
                **workflow_request,
                "since_generation": submitted["generation_after"],
            },
        )["result"]
        assert accepted["outcome"] == "succeeded"

    assert current["next_action"] is None
    assert current["actions"] == []
    assert all(
        section["coverage"] == "complete" for section in current["context_sections"]
    )
    assets = next(
        section
        for section in current["context_sections"]
        if section["section_id"] == "assets"
    )
    assert assets["confirmed_items"] == []

    import_request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "01991a00-0000-7000-8000-000000000100",
        "context_id": context_id,
        "expected_generation": current["used_generation"],
        "actor": {"actor_type": "source_adapter", "actor_id": "csv-bank"},
        "reason": "Import a later record for the manually linked account",
        "adapter": {"adapter_id": "csv-bank", "adapter_version": "0.2.0"},
        "records": [
            {
                "source_id": "main-account",
                "record_id": "posting-1",
                "booking_date": "2026-08-31",
                "money": {"amount": "1.00", "currency": "EUR"},
                "description": "Synthetic posting",
            }
        ],
        "authorization": None,
    }
    import_preview = run_topo(
        "source", "import", "--package", str(package), request=import_request
    )
    import_request["authorization"] = {
        "preview_ref": import_preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
        "authorized_at": "2026-09-03T12:00:00Z",
    }
    imported = run_topo(
        "source", "import", "--package", str(package), request=import_request
    )
    assert imported["result"]["account_refs"] == [
        {"ref_type": "entity", "id": "01991a00-0000-7000-8000-000000000001"}
    ]
    possible_duplicate = {
        **import_request,
        "operation_id": "01991a00-0000-7000-8000-000000000101",
        "expected_generation": imported["generation_after"],
        "records": [
            {
                "source_id": "vacation-source",
                "record_id": "posting-2",
                "booking_date": "2026-08-31",
                "money": {"amount": "2.00", "currency": "EUR"},
                "description": "Synthetic possible duplicate",
            }
        ],
        "authorization": None,
    }
    duplicate_preview = run_topo(
        "source", "import", "--package", str(package), request=possible_duplicate
    )
    merge_effect = next(
        effect
        for effect in duplicate_preview["result"]["effects"]
        if effect["action"] == "merge_external_account_identity"
    )
    assert merge_effect["account_ref"]["id"] == ("01991a00-0000-7000-8000-000000000002")
    possible_duplicate["authorization"] = {
        "preview_ref": duplicate_preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
        "authorized_at": "2026-09-03T12:05:00Z",
    }
    merged_import = run_topo(
        "source", "import", "--package", str(package), request=possible_duplicate
    )
    assert merged_import["result"]["account_refs"] == [
        {"ref_type": "entity", "id": "01991a00-0000-7000-8000-000000000002"}
    ]


def test_workflow_text_uses_fixed_dutch_headings(tmp_path: Path) -> None:
    package = tmp_path / "context.topo"
    initialized = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    request = {
        "contract_version": "topo.cli/0.1",
        "context_id": initialized["context_id"],
        "analysis_id": "analysis.net_worth",
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": initialized["result"]["household_id"],
        },
        "as_of_date": "2026-08-31",
        "include_basis_context": True,
    }
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "topo", "workflow", "next", "--package", str(package)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    headings = [
        line
        for line in completed.stdout.splitlines()
        if line
        in {
            "Zojuist gewijzigd",
            "Bevestigde context",
            "Openstaand en onzeker",
            "Actuele inzichten",
            "Volgende vraag",
        }
    ]
    assert headings == [
        "Zojuist gewijzigd",
        "Bevestigde context",
        "Openstaand en onzeker",
        "Actuele inzichten",
        "Volgende vraag",
    ]


def test_context_01_requires_one_authorized_migration(tmp_path: Path) -> None:
    package = tmp_path / "legacy.topo"
    initialized = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    generation = initialized["generation_after"]
    downgrade_to_context_01(package, generation)
    workflow = run_topo(
        "workflow",
        "next",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "context_id": initialized["context_id"],
            "analysis_id": "analysis.net_worth",
            "analysis_scope": {
                "scope_type": "household",
                "entity_id": initialized["result"]["household_id"],
            },
            "as_of_date": "2026-08-31",
            "include_basis_context": True,
        },
    )["result"]
    assert workflow["analysis_results"] == []
    action = workflow["next_action"]
    assert action["reason_code"] == "CONTEXT_MIGRATION_REQUIRED"
    preview_request = action["request_template"]
    preview_request["actor"]["actor_id"] = "agent.topo"
    preview = run_topo(
        "context", "migrate", "--package", str(package), request=preview_request
    )
    assert preview["outcome"] == "requires_authorization"
    authorized = {
        **preview_request,
        "authorization": {
            "preview_ref": preview["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
            "authorized_at": "2026-09-03T11:00:00Z",
        },
    }
    migrated = run_topo(
        "context", "migrate", "--package", str(package), request=authorized
    )
    assert migrated["outcome"] == "succeeded"
    assert migrated["result"]["context_schema_version"] == "topo.context/0.2"
    assert migrated["generation_after"] != generation


def test_reject_batch_is_collective_and_workflow_asks_again(tmp_path: Path) -> None:
    package = tmp_path / "rejected.topo"
    initialized = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    workflow_request = {
        "contract_version": "topo.cli/0.1",
        "context_id": initialized["context_id"],
        "analysis_id": "analysis.net_worth",
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": initialized["result"]["household_id"],
        },
        "as_of_date": "2026-08-31",
        "include_basis_context": True,
    }
    action = run_topo(
        "workflow", "next", "--package", str(package), request=workflow_request
    )["result"]["next_action"]
    inventory_request = action["request_template"]
    inventory_request["actor"]["actor_id"] = "agent.topo"
    inventory_request["workflow_response"]["producer"] = {
        "producer_type": "agent",
        "producer_id": "agent.topo",
        "producer_version": "0.2.0",
    }
    inventory_request["workflow_response"]["items"] = []
    proposed = run_topo(
        "workflow", "respond", "--package", str(package), request=inventory_request
    )
    rejected = run_topo(
        "proposal",
        "reject-batch",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "01991a00-0000-7000-8000-000000000200",
            "context_id": initialized["context_id"],
            "expected_generation": proposed["generation_after"],
            "actor": {"actor_type": "human", "actor_id": "local-user"},
            "reason": "The account inventory is not complete",
            "batch_id": proposed["result"]["batch_id"],
        },
    )
    assert rejected["outcome"] == "succeeded"
    assert rejected["result"]["proposal_ids"] == proposed["result"]["proposal_ids"]
    next_result = run_topo(
        "workflow", "next", "--package", str(package), request=workflow_request
    )["result"]
    assert next_result["next_action"]["reason_code"] == "BASIS_CONTEXT_NEEDS_ACCOUNTS"
