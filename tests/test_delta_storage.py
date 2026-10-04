from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_storage_recovery import initialize, run_topo, submit_salary_proposal

from topo.canonical_validation import load_and_validate_generation
from topo.delta_storage import decode_generation, encode_generation
from topo.engine import EngineCore
from topo.errors import PackageIntegrityError
from topo.identifiers import uuid7
from topo.models import Actor, ContextRestoreRequest
from topo.storage import FileSystemStorageAdapter, migrate_storage


def _migrated_package(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    old = tmp_path / "old.topo"
    new = tmp_path / "new.topo"
    initialized = initialize(old)
    submitted = submit_salary_proposal(old, initialized)
    migrate_storage(old, new, validate=load_and_validate_generation)
    return new, submitted


def test_delta_round_trip_and_physical_size(tmp_path: Path) -> None:
    package, submitted = _migrated_package(tmp_path)
    old_snapshot = FileSystemStorageAdapter(tmp_path / "old.topo").load()
    new_snapshot = FileSystemStorageAdapter(package).load()
    assert old_snapshot is not None and new_snapshot is not None
    assert new_snapshot.current_generation == old_snapshot.current_generation
    assert new_snapshot.generation_files == old_snapshot.generation_files
    assert (
        new_snapshot.retained_generation_files == old_snapshot.retained_generation_files
    )
    assert new_snapshot.journal == old_snapshot.journal
    assert new_snapshot.evidence_records == old_snapshot.evidence_records
    generation = package / "generations" / str(submitted["generation_after"])
    assert {path.name for path in generation.iterdir()} == {
        "manifest.json",
        "changes.json",
        "storage.json",
    }
    snapshot = new_snapshot
    assert snapshot.retained_generation_files is not None
    first = next(iter(snapshot.retained_generation_files.values()))
    assert (
        decode_generation(
            str(submitted["generation_after"]),
            {path.name: path.read_bytes() for path in generation.iterdir()},
            first,
        )
        == snapshot.generation_files
    )
    assert len(
        encode_generation(snapshot.generation_files, first, checkpoint=False)[
            "changes.json"
        ]
    ) < len(snapshot.generation_files["assertions.json"]) + len(
        snapshot.generation_files["proposals.json"]
    )


def test_corrupt_current_cache_rebuilds_from_canonical_delta(tmp_path: Path) -> None:
    package, submitted = _migrated_package(tmp_path)
    adapter = FileSystemStorageAdapter(package)
    original = adapter.load_current()
    assert original is not None
    cache = package / "derived" / "current" / str(submitted["generation_after"])
    (cache / "entities.json").write_text("{}", encoding="utf-8")
    rebuilt = adapter.load_current()
    assert rebuilt is not None
    assert rebuilt.generation_files == original.generation_files
    assert (cache / "entities.json").read_bytes() == original.generation_files[
        "entities.json"
    ]


def test_corrupt_delta_and_missing_checkpoint_block_verification(
    tmp_path: Path,
) -> None:
    package, submitted = _migrated_package(tmp_path)
    delta = (
        package / "generations" / str(submitted["generation_after"]) / "changes.json"
    )
    delta.write_text("{}", encoding="utf-8")
    with pytest.raises(PackageIntegrityError):
        EngineCore(FileSystemStorageAdapter(package)).verify_context()

    package, submitted = _migrated_package(tmp_path / "second")
    assert submitted["generation_after"]
    initial_generation = next(
        path
        for path in (package / "generations").iterdir()
        if "changes.json" not in {file.name for file in path.iterdir()}
    )
    shutil.rmtree(initial_generation)
    with pytest.raises(PackageIntegrityError):
        EngineCore(FileSystemStorageAdapter(package)).verify_context()


def test_tampered_retained_delta_blocks_mutation_even_with_old_receipt(
    tmp_path: Path,
) -> None:
    package, submitted = _migrated_package(tmp_path)
    rejected = run_topo(
        "proposal",
        "reject",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000000099",
            "context_id": submitted["context_id"],
            "expected_generation": submitted["generation_after"],
            "actor": {"actor_type": "human", "actor_id": "local-user"},
            "reason": "Reject synthetic proposal",
            "proposal_ref": submitted["result"]["proposal_id"],
        },
    )
    assert rejected.returncode == 0, rejected.stderr
    generation = package / "generations" / str(submitted["generation_after"])
    physical = {path.name: path.read_bytes() for path in generation.iterdir()}
    metadata = json.loads(physical["storage.json"])
    metadata["changes_checksum"] = "sha256:" + "0" * 64
    (generation / "storage.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(PackageIntegrityError):
        EngineCore(FileSystemStorageAdapter(package))._load_full_existing()


def test_current_read_rejects_delta_with_recomputed_physical_checksum(
    tmp_path: Path,
) -> None:
    package, submitted = _migrated_package(tmp_path)
    adapter = FileSystemStorageAdapter(package)
    assert adapter.load_current() is not None
    generation = package / "generations" / str(submitted["generation_after"])
    changed = b"{}\n"
    (generation / "changes.json").write_bytes(changed)
    metadata_path = generation / "storage.json"
    metadata = json.loads(metadata_path.read_bytes())
    metadata["changes_checksum"] = "sha256:" + hashlib.sha256(changed).hexdigest()
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(PackageIntegrityError):
        adapter.load_current()


def test_recovery_discards_orphan_delta_generation(tmp_path: Path) -> None:
    package, submitted = _migrated_package(tmp_path)
    generation = package / "generations" / str(submitted["generation_after"])
    orphan = package / "generations" / "0198f1a0-0000-7000-8000-000000000099"
    shutil.copytree(generation, orphan)
    snapshot = FileSystemStorageAdapter(package).load()
    assert snapshot is not None
    assert not orphan.exists()


def test_seventeenth_generation_is_a_checkpoint(tmp_path: Path) -> None:
    old = tmp_path / "old.topo"
    package = tmp_path / "delta.topo"
    initialized = initialize(old)
    migrate_storage(old, package, validate=load_and_validate_generation)
    engine = EngineCore(FileSystemStorageAdapter(package))
    first = initialized["generation_after"]
    current = first
    for index in range(16):
        restored = engine.restore_context(
            ContextRestoreRequest(
                contract_version="topo.cli/0.1",
                operation_id=uuid7(),
                context_id=initialized["context_id"],
                expected_generation=current,
                actor=Actor(actor_type="human", actor_id="test-user"),
                reason="Exercise periodic checkpoint",
                restore_generation=first,
            )
        )
        current = restored.generation_after
        files = {path.name for path in (package / "generations" / current).iterdir()}
        if index == 15:
            assert "entities.json" in files
            assert "changes.json" not in files
        else:
            assert "changes.json" in files
    assert engine.verify_context().generations_verified == 17


def test_wrong_engine_change_set_cannot_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from topo.models import ProposalSubmitRequest

    package, submitted = _migrated_package(tmp_path)
    initialized = json.loads((package / "history" / "journal.json").read_bytes())[
        "entries"
    ][0]["result"]
    adapter = FileSystemStorageAdapter(package)
    snapshot = adapter.load()
    assert snapshot is not None and snapshot.retained_generation_files is not None
    evidence_id = json.loads(
        next(iter(snapshot.retained_generation_files.values()))["evidence.json"]
    )["records"][0]["id"]
    commit = adapter.commit

    def corrupt_change_set(
        publication: Any, *, expected_generation: str | None
    ) -> None:
        commit(
            replace(publication, collection_changes={}),
            expected_generation=expected_generation,
        )

    monkeypatch.setattr(adapter, "commit", corrupt_change_set)
    request = ProposalSubmitRequest.model_validate_json(
        json.dumps(
            {
                "contract_version": "topo.cli/0.1",
                "operation_id": uuid7(),
                "context_id": submitted["context_id"],
                "expected_generation": submitted["generation_after"],
                "actor": {"actor_type": "human", "actor_id": "test"},
                "reason": "Test invalid changes",
                "proposal": {
                    "proposal_type": "assertion",
                    "producer": {
                        "producer_type": "agent",
                        "producer_id": "agent.test",
                        "producer_version": "0.1",
                    },
                    "proposed_assertion": {
                        "subject_ref": {
                            "ref_type": "entity",
                            "id": initialized["person_id"],
                        },
                        "predicate": "domain.cashflow/monthly_salary",
                        "object_value": {
                            "value_type": "money",
                            "value": {"amount": "100.00", "currency": "EUR"},
                        },
                        "valid_time": {"start": "2026-01-01", "end_exclusive": None},
                        "knowledge_type": "inferred",
                        "module_data": {},
                    },
                    "evidence_refs": [
                        {
                            "ref_type": "evidence",
                            "id": evidence_id,
                        }
                    ],
                    "reason_ref": "synthetic:changeset",
                },
            }
        ),
        strict=True,
    )
    before = (package / "CURRENT").read_bytes()
    with pytest.raises((PackageIntegrityError, ValueError)):
        EngineCore(adapter).submit_proposal(request)
    assert (package / "CURRENT").read_bytes() == before
    EngineCore(FileSystemStorageAdapter(package)).verify_context()


def test_scandir_digest_matches_complete_path_digest(tmp_path: Path) -> None:
    package, submitted = _migrated_package(tmp_path)
    expected = hashlib.sha256()
    paths = [package / "CURRENT", package / "storage-format.json"]
    for relative in ("generations", "history", "evidence/records"):
        paths.extend((package / relative).rglob("*"))
    for path in sorted(paths):
        expected.update(b"D" if path.is_dir() else b"F")
        expected.update(str(path.relative_to(package)).encode())
        expected.update(b"\0")
        if path.is_file():
            expected.update(path.read_bytes())
        expected.update(b"\0")
    adapter = FileSystemStorageAdapter(package)
    assert adapter._canonical_digest_locked() == expected.hexdigest()
    assert adapter.load_verified_current() is not None
    generation = package / "generations" / str(submitted["generation_after"])
    payload = (generation / "changes.json").read_bytes()
    (generation / "changes.json").write_bytes(payload + b" ")
    assert adapter.load_verified_current() is None
    with pytest.raises(PackageIntegrityError):
        EngineCore(adapter).verify_context()
