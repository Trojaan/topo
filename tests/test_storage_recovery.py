from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from topo.errors import PackageIntegrityError
from topo.storage import FileSystemStorageAdapter, PackageCommit

PROJECT_ROOT = Path(__file__).parents[1]


def run_topo(*args: str, request: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "topo", "--json", *args],
        cwd=PROJECT_ROOT,
        env=environment,
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
    )


def initialize(package: Path) -> dict[str, Any]:
    completed = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    assert completed.returncode == 0, completed.stderr
    return cast(dict[str, Any], json.loads(completed.stdout))


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def submit_salary_proposal(
    package: Path, initialization: dict[str, Any]
) -> dict[str, Any]:
    generation = package / "generations" / initialization["generation_after"]
    evidence_id = read_json(generation / "evidence.json")["records"][0]["id"]
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "0198f1a0-0000-7000-8000-000000000010",
        "context_id": initialization["context_id"],
        "expected_generation": initialization["generation_after"],
        "actor": {"actor_type": "human", "actor_id": "local-user"},
        "reason": "Review salary pattern",
        "proposal": {
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
        },
    }
    completed = run_topo(
        "proposal", "submit", "--package", str(package), request=request
    )
    assert completed.returncode == 0, completed.stderr
    return cast(dict[str, Any], json.loads(completed.stdout))


def test_opening_package_discards_crash_staging_and_unpublished_generation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "recovery.topo"
    initialized = initialize(package)
    current_id = initialized["generation_after"]
    current_path = package / "generations" / current_id
    current_before = {path.name: path.read_bytes() for path in current_path.iterdir()}

    orphan_id = "0198f1a0-0000-7000-8000-000000000099"
    orphan_path = package / "generations" / orphan_id
    shutil.copytree(current_path, orphan_path)
    orphan_manifest = read_json(orphan_path / "manifest.json")
    orphan_manifest["generation_id"] = orphan_id
    orphan_manifest["based_on"] = current_id
    (orphan_path / "manifest.json").write_text(
        json.dumps(orphan_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    complete_staging = package / "staging" / "complete"
    incomplete_staging = package / "staging" / "incomplete"
    shutil.copytree(orphan_path, complete_staging)
    incomplete_staging.mkdir()
    (incomplete_staging / "entities.json").write_text("{}", encoding="utf-8")
    orphan_evidence = (
        package / "evidence" / "records" / "0198f1a0-0000-7000-8000-000000000098.json"
    )
    orphan_evidence.write_text('{"sensitive":"orphaned"}\n', encoding="utf-8")
    orphan_inventory = (
        package / "history" / "evidence-inventory" / f"{orphan_id}-{'0' * 64}.json"
    )
    orphan_inventory.write_text('{"paths":[]}\n', encoding="utf-8")

    snapshot = FileSystemStorageAdapter(package).load_current()

    assert snapshot is not None
    assert snapshot.retained_generation_files is not None
    assert snapshot.current_generation == current_id
    assert (package / "CURRENT").read_text(encoding="utf-8").strip() == current_id
    assert not orphan_path.exists()
    assert not orphan_evidence.exists()
    assert not orphan_inventory.exists()
    assert list((package / "staging").iterdir()) == []
    assert {
        path.name: path.read_bytes() for path in current_path.iterdir()
    } == current_before


def test_pre_inventory_package_is_bootstrapped_before_its_next_mutation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "legacy.topo"
    initialized = initialize(package)
    shutil.rmtree(package / "history" / "evidence-inventory")
    abandoned_bootstrap = package / "history" / ".evidence-inventory-crash"
    abandoned_bootstrap.mkdir()
    (abandoned_bootstrap / "partial.json").write_text(
        '{"paths":[]}\n', encoding="utf-8"
    )

    submitted = submit_salary_proposal(package, initialized)

    assert submitted["generation_after"] != initialized["generation_after"]
    assert not abandoned_bootstrap.exists()
    inventories = tuple((package / "history" / "evidence-inventory").iterdir())
    assert len(inventories) == 2


def test_current_load_omits_retained_generations_without_recovery_artifacts(
    tmp_path: Path,
) -> None:
    package = tmp_path / "current-only.topo"
    initialized = initialize(package)
    submitted = submit_salary_proposal(package, initialized)

    snapshot = FileSystemStorageAdapter(package).load_current()

    assert snapshot is not None
    assert snapshot.current_generation == submitted["generation_after"]
    assert snapshot.retained_generation_files is None


def test_context_verify_checks_the_complete_retained_package(tmp_path: Path) -> None:
    package = tmp_path / "verify.topo"
    initialized = initialize(package)
    submitted = submit_salary_proposal(package, initialized)

    verified = run_topo(
        "context",
        "verify",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )

    assert verified.returncode == 0, verified.stderr
    response = json.loads(verified.stdout)
    assert response["command"] == "context.verify"
    assert response["generation_before"] == submitted["generation_after"]
    assert response["generation_after"] == submitted["generation_after"]
    assert response["result"] == {
        "context_id": initialized["context_id"],
        "generation_id": submitted["generation_after"],
        "generations_verified": 2,
        "evidence_records_verified": 0,
    }


def test_manifest_tampering_keeps_raw_read_available_and_blocks_mutation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "tampered.topo"
    initialized = initialize(package)
    current_id = initialized["generation_after"]
    generation = package / "generations" / current_id
    manifest_path = generation / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"]["entities.json"] = "sha256:" + "0" * 64
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    snapshot = FileSystemStorageAdapter(package).load()
    before = (package / "CURRENT").read_bytes()
    status = run_topo(
        "context",
        "status",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    replayed = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )

    assert snapshot is not None
    assert snapshot.generation_files["manifest.json"] == manifest_path.read_bytes()
    assert status.returncode == 2
    assert json.loads(status.stdout)["diagnostics"][0]["code"] == (
        "PACKAGE_INTEGRITY_FAILED"
    )
    assert replayed.returncode == 2
    response = json.loads(replayed.stdout)
    assert response["diagnostics"][0]["code"] == "PACKAGE_INTEGRITY_FAILED"
    assert response["diagnostics"][0]["effect"] == "none"
    assert (package / "CURRENT").read_bytes() == before


def test_startup_finishes_journal_switch_after_current_was_published(
    tmp_path: Path,
) -> None:
    package = tmp_path / "journal-recovery.topo"
    initialized = initialize(package)
    submitted = submit_salary_proposal(package, initialized)
    journal_path = package / "history" / "journal.json"
    complete_journal = journal_path.read_bytes()
    old_journal = read_json(journal_path)
    old_journal["entries"] = old_journal["entries"][:-1]
    journal_path.write_text(
        json.dumps(old_journal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (package / "history" / ".journal.tmp").write_bytes(complete_journal)

    snapshot = FileSystemStorageAdapter(package).load()

    assert snapshot is not None
    assert snapshot.current_generation == submitted["generation_after"]
    assert journal_path.read_bytes() == complete_journal
    assert not (package / "history" / ".journal.tmp").exists()
    assert {path.name for path in (package / "generations").iterdir()} == {
        initialized["generation_after"],
        submitted["generation_after"],
    }


def test_tampered_retained_generation_blocks_a_new_mutation(tmp_path: Path) -> None:
    package = tmp_path / "retained-tamper.topo"
    initialized = initialize(package)
    submitted = submit_salary_proposal(package, initialized)
    historical_entities = (
        package / "generations" / initialized["generation_after"] / "entities.json"
    )
    entities = read_json(historical_entities)
    entities["records"] = [
        record for record in entities["records"] if record["entity_type"] != "person"
    ]
    entities_payload = (
        json.dumps(entities, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    historical_entities.write_bytes(entities_payload)
    historical_manifest_path = historical_entities.parent / "manifest.json"
    historical_manifest = read_json(historical_manifest_path)
    historical_manifest["files"]["entities.json"] = (
        "sha256:" + hashlib.sha256(entities_payload).hexdigest()
    )
    historical_manifest_path.write_text(
        json.dumps(historical_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    status = run_topo(
        "context",
        "status",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    verified = run_topo(
        "context",
        "verify",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    snapshot = FileSystemStorageAdapter(package).load()
    rejected = run_topo(
        "proposal",
        "reject",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000000011",
            "context_id": initialized["context_id"],
            "expected_generation": submitted["generation_after"],
            "actor": {"actor_type": "human", "actor_id": "local-user"},
            "reason": "Reject salary pattern",
            "proposal_ref": submitted["result"]["proposal_id"],
        },
    )

    assert snapshot is not None
    assert status.returncode == 0, status.stderr
    assert verified.returncode == 2
    assert json.loads(verified.stdout)["diagnostics"][0]["code"] == (
        "PACKAGE_INTEGRITY_FAILED"
    )
    assert snapshot.current_generation == submitted["generation_after"]
    assert rejected.returncode == 2
    response = json.loads(rejected.stdout)
    assert response["diagnostics"][0]["code"] == "PACKAGE_INTEGRITY_FAILED"
    assert response["diagnostics"][0]["effect"] == "none"
    assert (package / "CURRENT").read_text(encoding="utf-8").strip() == submitted[
        "generation_after"
    ]


def test_symlinked_staging_is_not_followed_and_blocks_all_publication(
    tmp_path: Path,
) -> None:
    package = tmp_path / "symlink.topo"
    initialized = initialize(package)
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "must-remain.txt"
    sentinel.write_text("outside package", encoding="utf-8")
    (package / "staging").rmdir()
    (package / "staging").symlink_to(external, target_is_directory=True)
    adapter = FileSystemStorageAdapter(package)

    snapshot = adapter.load()

    assert snapshot is not None
    assert snapshot.current_generation == initialized["generation_after"]
    assert sentinel.read_text(encoding="utf-8") == "outside package"
    with pytest.raises(PackageIntegrityError):
        adapter.commit(
            PackageCommit(
                generation_id=snapshot.current_generation,
                generation_files=snapshot.generation_files,
                journal=snapshot.journal,
            ),
            expected_generation=snapshot.current_generation,
        )
    assert sentinel.read_text(encoding="utf-8") == "outside package"
