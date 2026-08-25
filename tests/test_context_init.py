from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).parents[1]
UUID7 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def run_topo(*args: str, request: dict | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "topo", "--json", *args],
        cwd=PROJECT_ROOT,
        env=environment,
        input=json.dumps(request) if request is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_user_can_initialize_a_complete_first_generation(tmp_path: Path) -> None:
    package = tmp_path / "noor.topo"
    request = {"contract_version": "topo.cli/0.1"}

    completed = run_topo("context", "init", "--package", str(package), request=request)

    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["contract_version"] == "topo.cli/0.1"
    assert response["command"] == "context.init"
    assert response["outcome"] == "succeeded"
    assert response["generation_before"] is None
    assert response["generation_after"] == response["result"]["generation_id"]
    assert response["diagnostics"] == []

    generation_id = (package / "CURRENT").read_text(encoding="utf-8").strip()
    assert UUID7.fullmatch(generation_id)
    generation = package / "generations" / generation_id
    assert generation.is_dir()

    expected_files = {
        "manifest.json",
        "entities.json",
        "assertions.json",
        "evidence.json",
        "proposals.json",
    }
    assert {path.name for path in generation.iterdir()} == expected_files

    entities = read_json(generation / "entities.json")
    assert entities["schema_version"] == "topo.context/0.1"
    assert [record["entity_type"] for record in entities["records"]] == [
        "context",
        "household",
        "person",
    ]
    assert entities["records"] == sorted(entities["records"], key=lambda record: record["id"])

    assertions = read_json(generation / "assertions.json")
    memberships = [
        record
        for record in assertions["records"]
        if record["predicate"] == "domain.parties/household_membership"
    ]
    assert len(memberships) == 1
    membership = memberships[0]
    assert membership["verification_status"] == "confirmed"
    assert membership["knowledge_type"] == "user_provided"
    assert membership["subject_ref"]["id"] == response["result"]["person_id"]
    assert membership["object_ref"]["id"] == response["result"]["household_id"]

    manifest = read_json(generation / "manifest.json")
    assert manifest["schema_version"] == "topo.manifest/0.1"
    assert manifest["context_id"] == response["context_id"]
    assert manifest["generation_id"] == generation_id
    assert manifest["based_on"] is None
    for filename, expected_checksum in manifest["files"].items():
        payload = (generation / filename).read_bytes()
        assert expected_checksum == f"sha256:{hashlib.sha256(payload).hexdigest()}"

    assert read_json(package / "history" / "journal.json")["entries"][0]["operation"] == "context.init"
    assert list((package / "staging").iterdir()) == []


def test_user_can_discover_commands_and_schema_validated_responses(tmp_path: Path) -> None:
    request = {"contract_version": "topo.cli/0.1"}

    described = run_topo("contract", "describe", request=request)

    assert described.returncode == 0, described.stderr
    discovery = json.loads(described.stdout)
    assert discovery["outcome"] == "succeeded"
    assert discovery["result"]["supported_contract_versions"] == ["topo.cli/0.1"]
    assert [command["command"] for command in discovery["result"]["commands"]] == [
        "context.init",
        "contract.describe",
        "contract.schema",
    ]

    schemas: dict[str, dict] = {}
    for command in ("context.init", "contract.describe", "contract.schema"):
        completed = run_topo("contract", "schema", command, request=request)
        assert completed.returncode == 0, completed.stderr
        response = json.loads(completed.stdout)
        assert response["outcome"] == "succeeded"
        assert response["result"]["command"] == command
        Draft202012Validator.check_schema(response["result"]["input_schema"])
        Draft202012Validator.check_schema(response["result"]["output_schema"])
        schemas[command] = response["result"]["output_schema"]

    Draft202012Validator(schemas["contract.describe"]).validate(discovery)

    package = tmp_path / "schema-checked.topo"
    initialized = run_topo("context", "init", "--package", str(package), request=request)
    Draft202012Validator(schemas["context.init"]).validate(json.loads(initialized.stdout))

    schema_response = json.loads(
        run_topo("contract", "schema", "contract.schema", request=request).stdout
    )
    Draft202012Validator(schemas["contract.schema"]).validate(schema_response)


def test_unknown_major_contract_version_fails_without_effect(tmp_path: Path) -> None:
    package = tmp_path / "must-not-exist.topo"
    request = {"contract_version": "topo.cli/1.0"}

    completed = run_topo("context", "init", "--package", str(package), request=request)

    assert completed.returncode != 0
    assert completed.stderr == ""
    response = json.loads(completed.stdout)
    assert response["command"] == "context.init"
    assert response["outcome"] == "rejected"
    assert response["generation_before"] is None
    assert response["generation_after"] is None
    assert response["diagnostics"][0] == {
        "code": "INCOMPATIBLE_CONTRACT_VERSION",
        "message_key": "diagnostic.incompatible_contract_version",
        "severity": "error",
        "path": "/contract_version",
        "params": {
            "requested": "topo.cli/1.0",
            "supported": ["topo.cli/0.1"],
        },
        "retryable": False,
        "effect": "none",
        "related_refs": [],
    }
    assert not package.exists()


def test_reinitialization_never_replaces_a_published_generation(tmp_path: Path) -> None:
    package = tmp_path / "existing.topo"
    request = {"contract_version": "topo.cli/0.1"}
    first = run_topo("context", "init", "--package", str(package), request=request)
    assert first.returncode == 0
    original = {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    }

    repeated = run_topo("context", "init", "--package", str(package), request=request)

    assert repeated.returncode != 0
    response = json.loads(repeated.stdout)
    assert response["diagnostics"][0]["code"] == "CONTEXT_ALREADY_EXISTS"
    assert response["diagnostics"][0]["effect"] == "none"
    assert {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    } == original
