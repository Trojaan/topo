from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from topo.contracts import input_schema, validate_request
from topo.engine import EngineCore
from topo.models import Actor, ContextInitRequest, JsonObject
from topo.storage import PackageCommit, StoredPackageSnapshot

PROJECT_ROOT = Path(__file__).parents[1]
UUID7 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class MemoryStorage:
    def __init__(self) -> None:
        self.snapshot: StoredPackageSnapshot | None = None

    def load(self) -> StoredPackageSnapshot | None:
        return self.snapshot

    def commit(
        self, publication: PackageCommit, *, expected_generation: str | None
    ) -> None:
        assert expected_generation is None
        if self.snapshot is not None:
            raise FileExistsError
        self.snapshot = StoredPackageSnapshot(
            current_generation=publication.generation_id,
            generation_files=publication.generation_files,
            journal=publication.journal,
        )


def run_topo(
    *args: str, request: dict[str, Any] | None = None
) -> subprocess.CompletedProcess[str]:
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


def run_topo_exact(
    *args: str, request: dict[str, Any] | None = None
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "topo", *args],
        cwd=PROJECT_ROOT,
        env=environment,
        input=json.dumps(request) if request is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


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
    assert entities["records"] == sorted(
        entities["records"], key=lambda record: record["id"]
    )

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
    assert "jurisdiction.nl" in {module["module_id"] for module in manifest["modules"]}
    assert manifest["generation_id"] == generation_id
    assert manifest["based_on"] is None
    for filename, expected_checksum in manifest["files"].items():
        payload = (generation / filename).read_bytes()
        assert expected_checksum == f"sha256:{hashlib.sha256(payload).hexdigest()}"

    assert (
        read_json(package / "history" / "journal.json")["entries"][0]["operation"]
        == "context.init"
    )
    assert list((package / "staging").iterdir()) == []


def test_user_can_discover_commands_and_schema_validated_responses(
    tmp_path: Path,
) -> None:
    request = {"contract_version": "topo.cli/0.1"}

    described = run_topo("contract", "describe", request=request)

    assert described.returncode == 0, described.stderr
    discovery = json.loads(described.stdout)
    assert discovery["outcome"] == "succeeded"
    assert discovery["result"]["supported_contract_versions"] == ["topo.cli/0.1"]
    assert [command["command"] for command in discovery["result"]["commands"]][:3] == [
        "context.init",
        "contract.describe",
        "contract.schema",
    ]

    schemas: dict[str, dict[str, Any]] = {}
    discovered_commands = [
        descriptor["command"] for descriptor in discovery["result"]["commands"]
    ]
    for command in discovered_commands:
        completed = run_topo("contract", "schema", command, request=request)
        assert completed.returncode == 0, completed.stderr
        response = json.loads(completed.stdout)
        assert response["outcome"] == "succeeded"
        assert response["result"]["command"] == command
        Draft202012Validator.check_schema(response["result"]["input_schema"])
        Draft202012Validator.check_schema(response["result"]["output_schema"])
        assert response["result"]["input_schema"]["additionalProperties"] is False
        assert response["result"]["output_schema"]["additionalProperties"] is False
        schemas[command] = response["result"]["output_schema"]

    Draft202012Validator(schemas["contract.describe"]).validate(discovery)

    package = tmp_path / "schema-checked.topo"
    initialized = run_topo(
        "context", "init", "--package", str(package), request=request
    )
    Draft202012Validator(schemas["context.init"]).validate(
        json.loads(initialized.stdout)
    )

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

    schema_response = run_topo(
        "contract",
        "schema",
        "context.init",
        request={"contract_version": "topo.cli/0.1"},
    )
    error_schema = json.loads(schema_response.stdout)["result"]["output_schema"]
    Draft202012Validator(error_schema).validate(response)


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


def test_contract_discovery_only_exposes_executable_commands() -> None:
    request = {"contract_version": "topo.cli/0.1"}

    described = run_topo_exact("contract", "describe", "--json", request=request)

    assert described.returncode == 0, described.stderr
    commands = {
        item["command"] for item in json.loads(described.stdout)["result"]["commands"]
    }
    assert commands == {
        "context.init",
        "contract.describe",
        "contract.schema",
        "source.import",
        "discover.run",
        "proposal.submit",
        "proposal.confirm",
        "proposal.correct",
        "proposal.reject",
    }

    unavailable = run_topo_exact(
        "contract", "schema", "analyze.run", "--json", request=request
    )
    assert unavailable.returncode != 0
    assert unavailable.stdout == ""


def test_contract_validation_enforces_date_formats() -> None:
    request: JsonObject = {
        "contract_version": "topo.cli/0.1",
        "analysis_id": "analysis.net_worth",
        "analysis_contract_version": "0.1",
        "context_id": "0198f1a0-0000-7000-8000-000000000001",
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": "0198f1a0-0000-7000-8000-000000000002",
        },
        "as_of_date": "geen-datum",
        "period": None,
        "scenario": None,
    }

    Draft202012Validator(input_schema("analyze.run")).validate(request)
    with pytest.raises(ValidationError):
        validate_request("analyze.run", request)


def test_context_init_pydantic_and_json_schema_validation_stay_in_parity() -> None:
    request: JsonObject = {
        "contract_version": "topo.cli/0.1",
        "package": "/tmp/noor.topo",
        "operation_id": "0198f1a0-0000-7000-8000-000000000001",
        "expected_generation": None,
        "actor": {"actor_type": "human", "actor_id": "local-user"},
        "reason": "Initialize context",
    }
    validate_request("context.init", request)
    ContextInitRequest.model_validate(request, strict=True)

    invalid = {**request, "unexpected": True}
    with pytest.raises(ValidationError):
        validate_request("context.init", invalid)
    with pytest.raises(PydanticValidationError):
        ContextInitRequest.model_validate(invalid, strict=True)


def test_init_normalizes_file_input_and_replays_the_same_operation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "replayable.topo"
    request_path = tmp_path / "init-request.json"
    operation_id = "0198f1a0-0000-7000-8000-000000000001"
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": operation_id,
        "expected_generation": None,
        "actor": {"actor_type": "human", "actor_id": "local-user"},
        "reason": "Initialize Noor's local context",
    }
    request_path.write_text(json.dumps(request), encoding="utf-8")

    first = run_topo_exact(
        "context",
        "init",
        "--package",
        str(package),
        "--request",
        str(request_path),
        "--json",
    )

    assert first.returncode == 0, first.stderr
    first_response = json.loads(first.stdout)
    assert first_response["operation_id"] == operation_id
    assert first_response["trace"]["normalized_request"] == {
        **request,
        "package": str(package),
    }

    current_before = (package / "CURRENT").read_bytes()
    second = run_topo_exact(
        "context",
        "init",
        "--package",
        str(package),
        "--request",
        str(request_path),
        "--json",
    )

    assert second.returncode == 0, second.stderr
    second_response = json.loads(second.stdout)
    assert second_response["outcome"] == "no_change"
    assert second_response["result"] == first_response["result"]
    assert second_response["generation_before"] == first_response["generation_after"]
    assert second_response["generation_after"] == first_response["generation_after"]
    assert (package / "CURRENT").read_bytes() == current_before


def test_engine_core_uses_the_storage_seam_for_publish_and_replay() -> None:
    storage = MemoryStorage()
    ids = iter(f"0198f1a0-0000-7000-8000-{suffix:012d}" for suffix in range(10, 17))
    engine = EngineCore(
        storage,
        clock=lambda: datetime(2026, 8, 27, 12, tzinfo=UTC),
        id_factory=lambda: next(ids),
    )
    request = ContextInitRequest(
        contract_version="topo.cli/0.1",
        package="memory.topo",
        operation_id="0198f1a0-0000-7000-8000-000000000001",
        expected_generation=None,
        actor=Actor(actor_type="human", actor_id="local-user"),
        reason="Initialize memory context",
    )

    first = engine.initialize(request)
    second = engine.initialize(request)

    assert first.replayed is False
    assert second.replayed is True
    assert second.result == first.result
    assert storage.snapshot is not None


def test_corrupted_replay_returns_package_integrity_diagnostic(
    tmp_path: Path,
) -> None:
    package = tmp_path / "corrupted.topo"
    operation_id = "0198f1a0-0000-7000-8000-000000000001"
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": operation_id,
        "expected_generation": None,
        "actor": {"actor_type": "human", "actor_id": "local-user"},
        "reason": "Initialize context",
    }
    initialized = run_topo(
        "context", "init", "--package", str(package), request=request
    )
    assert initialized.returncode == 0

    generation_id = (package / "CURRENT").read_text(encoding="utf-8").strip()
    generation = package / "generations" / generation_id
    entities_path = generation / "entities.json"
    entities = read_json(entities_path)
    entities["records"] = [
        record for record in entities["records"] if record["entity_type"] != "person"
    ]
    entities_payload = (
        json.dumps(entities, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    entities_path.write_bytes(entities_payload)
    manifest_path = generation / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"]["entities.json"] = (
        "sha256:" + hashlib.sha256(entities_payload).hexdigest()
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    replayed = run_topo("context", "init", "--package", str(package), request=request)

    assert replayed.returncode == 2
    response = json.loads(replayed.stdout)
    assert response["diagnostics"][0]["code"] == "PACKAGE_INTEGRITY_FAILED"
    assert response["diagnostics"][0]["effect"] == "none"
    assert response["diagnostics"][0]["params"]["reason"]
