from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).parents[1]


def run_topo(*args: str, request: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "topo", *args, "--json"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def current_generation(package: Path) -> tuple[str, Path]:
    generation_id = (package / "CURRENT").read_text(encoding="utf-8").strip()
    return generation_id, package / "generations" / generation_id


def initialize(package: Path) -> dict[str, Any]:
    response = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000000001",
            "expected_generation": None,
            "actor": {"actor_type": "human", "actor_id": "local-user"},
            "reason": "Initialize context",
        },
    )
    assert response.returncode == 0, response.stdout + response.stderr
    return cast(dict[str, Any], json.loads(response.stdout))


def mutation_metadata(
    initialization: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    return {
        "contract_version": "topo.cli/0.1",
        "operation_id": operation_id,
        "context_id": initialization["context_id"],
        "expected_generation": initialization["generation_after"],
        "actor": {"actor_type": "human", "actor_id": "local-user"},
        "reason": "Review the proposed salary pattern",
    }


def proposal_payload(initialization: dict[str, Any], package: Path) -> dict[str, Any]:
    _, generation = current_generation(package)
    evidence_id = read_json(generation / "evidence.json")["records"][0]["id"]
    return {
        "proposal_type": "assertion",
        "producer": {
            "producer_type": "agent",
            "producer_id": "agent.topo",
            "producer_version": "0.1.0",
        },
        "proposed_assertion": {
            "subject_ref": {
                "ref_type": "entity",
                "id": initialization["result"]["person_id"],
            },
            "predicate": "domain.cashflow/monthly_salary",
            "object_value": {
                "value_type": "money",
                "value": {"amount": "3200.00", "currency": "EUR"},
            },
            "valid_time": {"start": "2026-08-01", "end_exclusive": None},
            "knowledge_type": "inferred",
            "module_data": {},
        },
        "evidence_refs": [{"ref_type": "evidence", "id": evidence_id}],
        "reason_ref": "agent:salary-review/0.1.0",
        "detection": {
            "scheme": "domain.cashflow.pattern_score/0.1",
            "score": "0.94",
        },
    }


def submit_proposal(package: Path, initialization: dict[str, Any]) -> dict[str, Any]:
    request = {
        **mutation_metadata(initialization, "0198f1a0-0000-7000-8000-000000000002"),
        "proposal": proposal_payload(initialization, package),
    }
    response = run_topo(
        "proposal", "submit", "--package", str(package), request=request
    )
    assert response.returncode == 0, response.stdout + response.stderr
    return cast(dict[str, Any], json.loads(response.stdout))


def test_user_submits_previews_and_confirms_an_immutable_proposal(
    tmp_path: Path,
) -> None:
    package = tmp_path / "proposal.topo"
    initialization = initialize(package)
    submitted = submit_proposal(package, initialization)

    assert submitted["outcome"] == "succeeded"
    assert submitted["generation_after"] != submitted["generation_before"]
    proposal_id = submitted["result"]["proposal_id"]
    submitted_generation_id, submitted_generation = current_generation(package)
    original = read_json(submitted_generation / "proposals.json")["records"][0]
    assert original["id"] == proposal_id
    assert original["status"] == "open"
    assert original["producer"]["producer_id"] == "agent.topo"

    preview_request = {
        **mutation_metadata(
            {
                **initialization,
                "generation_after": submitted_generation_id,
            },
            "0198f1a0-0000-7000-8000-000000000003",
        ),
        "proposal_ref": proposal_id,
        "authorization": None,
    }
    preview = run_topo(
        "proposal", "confirm", "--package", str(package), request=preview_request
    )
    assert preview.returncode == 0, preview.stderr
    preview_body = json.loads(preview.stdout)
    assert preview_body["outcome"] == "requires_authorization"
    assert preview_body["generation_before"] == submitted_generation_id
    assert preview_body["generation_after"] == submitted_generation_id
    assert preview_body["result"]["effects"] == [
        {"action": "create_confirmed_assertion", "proposal_ref": proposal_id}
    ]
    assert (package / "CURRENT").read_text().strip() == submitted_generation_id

    confirm_request = {
        **preview_request,
        "authorization": {
            "preview_ref": preview_body["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
            "authorized_at": "2026-08-27T12:00:00Z",
        },
    }
    invalid_authorization = run_topo(
        "proposal",
        "confirm",
        "--package",
        str(package),
        request={
            **confirm_request,
            "authorization": {
                **confirm_request["authorization"],
                "preview_ref": "preview:sha256:invalid",
            },
        },
    )
    assert invalid_authorization.returncode == 0
    invalid_body = json.loads(invalid_authorization.stdout)
    assert invalid_body["outcome"] == "rejected"
    assert invalid_body["diagnostics"][0]["code"] == "INVALID_AUTHORIZATION"
    assert (package / "CURRENT").read_text().strip() == submitted_generation_id

    confirmed = run_topo(
        "proposal", "confirm", "--package", str(package), request=confirm_request
    )
    assert confirmed.returncode == 0, confirmed.stderr
    confirmed_body = json.loads(confirmed.stdout)
    assert confirmed_body["outcome"] == "succeeded"
    assert confirmed_body["result"]["proposal_id"] == proposal_id

    _, confirmed_generation = current_generation(package)
    stored_proposal = read_json(confirmed_generation / "proposals.json")["records"][0]
    assertion = next(
        record
        for record in read_json(confirmed_generation / "assertions.json")["records"]
        if record["id"] == confirmed_body["result"]["assertion_id"]
    )
    confirmation_evidence = next(
        record
        for record in read_json(confirmed_generation / "evidence.json")["records"]
        if record["id"] == confirmed_body["result"]["evidence_id"]
    )
    assert stored_proposal["proposed_assertion"] == original["proposed_assertion"]
    assert stored_proposal["status"] == "confirmed"
    assert stored_proposal["decision"]["assertion_id"] == assertion["id"]
    assert assertion["verification_status"] == "confirmed"
    assert assertion["object_value"]["value"]["amount"] == "3200.00"
    assert {ref["id"] for ref in assertion["provenance"]} == {
        *[ref["id"] for ref in original["evidence_refs"]],
        proposal_id,
        confirmation_evidence["id"],
    }
    assert confirmation_evidence["statement"] == {
        "authorization": confirm_request["authorization"],
        "proposal_id": proposal_id,
        "reason": confirm_request["reason"],
    }

    manifest = read_json(confirmed_generation / "manifest.json")
    for filename, checksum in manifest["files"].items():
        payload = (confirmed_generation / filename).read_bytes()
        assert checksum == "sha256:" + hashlib.sha256(payload).hexdigest()


def test_user_can_correct_or_reject_without_losing_the_original_proposal(
    tmp_path: Path,
) -> None:
    corrected_package = tmp_path / "corrected.topo"
    initialization = initialize(corrected_package)
    submitted = submit_proposal(corrected_package, initialization)
    proposal_id = submitted["result"]["proposal_id"]
    generation_id, generation = current_generation(corrected_package)
    original = read_json(generation / "proposals.json")["records"][0]

    correction_base = {
        **mutation_metadata(
            {**initialization, "generation_after": generation_id},
            "0198f1a0-0000-7000-8000-000000000004",
        ),
        "proposal_ref": proposal_id,
        "authorization": None,
        "correction": {
            "object_value": {
                "value_type": "money",
                "value": {"amount": "3250.00", "currency": "EUR"},
            },
            "reason": "The payslip shows the corrected amount",
        },
    }
    preview_response = run_topo(
        "proposal",
        "correct",
        "--package",
        str(corrected_package),
        request=correction_base,
    )
    preview = json.loads(preview_response.stdout)
    assert preview_response.returncode == 0
    assert preview["outcome"] == "requires_authorization"

    corrected_response = run_topo(
        "proposal",
        "correct",
        "--package",
        str(corrected_package),
        request={
            **correction_base,
            "authorization": {
                "preview_ref": preview["result"]["preview_ref"],
                "authorized_by": {
                    "actor_type": "human",
                    "actor_id": "local-user",
                },
                "authorized_at": "2026-08-27T12:00:00Z",
            },
        },
    )
    assert corrected_response.returncode == 0, corrected_response.stderr
    corrected = json.loads(corrected_response.stdout)
    _, corrected_generation = current_generation(corrected_package)
    proposal = read_json(corrected_generation / "proposals.json")["records"][0]
    assertions = read_json(corrected_generation / "assertions.json")["records"]
    evidence = read_json(corrected_generation / "evidence.json")["records"]
    corrected_assertion = next(
        record
        for record in assertions
        if record["id"] == corrected["result"]["assertion_id"]
    )
    correction_evidence = next(
        record
        for record in evidence
        if record["id"] == corrected["result"]["evidence_id"]
    )
    assert proposal["proposed_assertion"] == original["proposed_assertion"]
    assert proposal["status"] == "corrected"
    assert correction_evidence["evidence_type"] == "user_statement"
    assert corrected_assertion["object_value"]["value"]["amount"] == "3250.00"
    assert {ref["id"] for ref in corrected_assertion["provenance"]} == {
        *[ref["id"] for ref in original["evidence_refs"]],
        proposal_id,
        correction_evidence["id"],
    }

    rejected_package = tmp_path / "rejected.topo"
    rejected_initialization = initialize(rejected_package)
    rejected_submit = submit_proposal(rejected_package, rejected_initialization)
    rejected_generation_id, _ = current_generation(rejected_package)
    reject_request = {
        **mutation_metadata(
            {
                **rejected_initialization,
                "generation_after": rejected_generation_id,
            },
            "0198f1a0-0000-7000-8000-000000000005",
        ),
        "proposal_ref": rejected_submit["result"]["proposal_id"],
    }
    rejected_response = run_topo(
        "proposal",
        "reject",
        "--package",
        str(rejected_package),
        request=reject_request,
    )
    assert rejected_response.returncode == 0, rejected_response.stderr
    rejected = json.loads(rejected_response.stdout)
    _, rejected_generation = current_generation(rejected_package)
    proposals = read_json(rejected_generation / "proposals.json")["records"]
    assertions = read_json(rejected_generation / "assertions.json")["records"]
    assert rejected["outcome"] == "succeeded"
    assert proposals[0]["status"] == "rejected"
    assert proposals[0]["decision"]["assertion_id"] is None
    assert len(assertions) == 1


def test_mutations_are_idempotent_and_stale_generations_have_no_effect(
    tmp_path: Path,
) -> None:
    package = tmp_path / "safe.topo"
    initialization = initialize(package)
    submit_request = {
        **mutation_metadata(initialization, "0198f1a0-0000-7000-8000-000000000006"),
        "proposal": proposal_payload(initialization, package),
    }
    first = run_topo(
        "proposal", "submit", "--package", str(package), request=submit_request
    )
    assert first.returncode == 0, first.stderr
    first_body = json.loads(first.stdout)
    current_before_replay, _ = current_generation(package)

    replay = run_topo(
        "proposal", "submit", "--package", str(package), request=submit_request
    )
    replay_body = json.loads(replay.stdout)
    assert replay.returncode == 0
    assert replay_body["outcome"] == "no_change"
    assert replay_body["result"] == first_body["result"]
    assert current_generation(package)[0] == current_before_replay

    stale_request = {
        **mutation_metadata(initialization, "0198f1a0-0000-7000-8000-000000000007"),
        "proposal_ref": first_body["result"]["proposal_id"],
    }
    before = (package / "CURRENT").read_bytes()
    stale = run_topo(
        "proposal", "reject", "--package", str(package), request=stale_request
    )
    stale_body = json.loads(stale.stdout)
    assert stale.returncode == 0
    assert stale_body["outcome"] == "conflict"
    assert stale_body["diagnostics"][0]["code"] == "STALE_GENERATION"
    assert stale_body["diagnostics"][0]["effect"] == "none"
    assert (package / "CURRENT").read_bytes() == before


def test_contract_discovery_includes_executable_proposal_commands() -> None:
    described = run_topo(
        "contract",
        "describe",
        request={"contract_version": "topo.cli/0.1"},
    )
    assert described.returncode == 0, described.stderr
    commands = {
        item["command"] for item in json.loads(described.stdout)["result"]["commands"]
    }
    assert {
        "proposal.submit",
        "proposal.confirm",
        "proposal.correct",
        "proposal.reject",
    } <= commands

    schema_response = run_topo(
        "contract",
        "schema",
        "proposal.confirm",
        request={"contract_version": "topo.cli/0.1"},
    )
    assert schema_response.returncode == 0, schema_response.stderr
    schema = json.loads(schema_response.stdout)["result"]
    Draft202012Validator.check_schema(schema["input_schema"])
    Draft202012Validator.check_schema(schema["output_schema"])
    assert "authorization" in schema["input_schema"]["required"]


def test_user_can_correct_a_relation_proposal(tmp_path: Path) -> None:
    package = tmp_path / "relation.topo"
    initialization = initialize(package)
    payload = proposal_payload(initialization, package)
    proposed = payload["proposed_assertion"]
    del proposed["object_value"]
    proposed["object_ref"] = {
        "ref_type": "entity",
        "id": initialization["result"]["household_id"],
    }
    submitted_response = run_topo(
        "proposal",
        "submit",
        "--package",
        str(package),
        request={
            **mutation_metadata(initialization, "0198f1a0-0000-7000-8000-000000000008"),
            "proposal": payload,
        },
    )
    assert submitted_response.returncode == 0, submitted_response.stdout
    submitted = json.loads(submitted_response.stdout)
    generation_id, _ = current_generation(package)
    decision = {
        **mutation_metadata(
            {**initialization, "generation_after": generation_id},
            "0198f1a0-0000-7000-8000-000000000009",
        ),
        "proposal_ref": submitted["result"]["proposal_id"],
        "authorization": None,
        "correction": {
            "object_ref": {
                "ref_type": "entity",
                "id": initialization["context_id"],
            },
            "reason": "The relation points to the context itself",
        },
    }
    preview_response = run_topo(
        "proposal", "correct", "--package", str(package), request=decision
    )
    preview = json.loads(preview_response.stdout)
    confirmed_response = run_topo(
        "proposal",
        "correct",
        "--package",
        str(package),
        request={
            **decision,
            "authorization": {
                "preview_ref": preview["result"]["preview_ref"],
                "authorized_by": {
                    "actor_type": "human",
                    "actor_id": "local-user",
                },
                "authorized_at": "2026-08-27T12:00:00Z",
            },
        },
    )
    assert confirmed_response.returncode == 0, confirmed_response.stdout
    confirmed = json.loads(confirmed_response.stdout)
    _, generation = current_generation(package)
    assertion = next(
        record
        for record in read_json(generation / "assertions.json")["records"]
        if record["id"] == confirmed["result"]["assertion_id"]
    )
    assert assertion["object_ref"]["id"] == initialization["context_id"]
    assert "object_value" not in assertion
