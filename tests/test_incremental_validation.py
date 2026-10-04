from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_storage_recovery import initialize, run_topo

from topo.canonical_validation import load_and_validate_generation
from topo.errors import PackageIntegrityError
from topo.identifiers import uuid7
from topo.storage import FileSystemStorageAdapter, migrate_storage


def _fixture(tmp_path: Path) -> Any:
    package = tmp_path / "full.topo"
    identity = initialize(package)
    for index in range(3):
        request = {
            "contract_version": "topo.cli/0.1",
            "operation_id": uuid7(),
            "context_id": identity["context_id"],
            "expected_generation": identity["generation_after"],
            "actor": {"actor_type": "source_adapter", "actor_id": "adapter.synthetic"},
            "reason": "Synthetic verification fixture",
            "adapter": {"adapter_id": "adapter.synthetic", "adapter_version": "0.1"},
            "records": [
                {
                    "source_id": "synthetic",
                    "record_id": str(index),
                    "booking_date": "2026-01-01",
                    "money": {"amount": "1.00", "currency": "EUR"},
                    "description": "Synthetic",
                }
            ],
            "authorization": None,
        }
        args = ("source", "import", "--package", str(package))
        preview = run_topo(*args, request=request)
        assert preview.returncode == 0, preview.stdout
        request["authorization"] = {
            "preview_ref": json.loads(preview.stdout)["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "test"},
            "authorized_at": "2026-10-04T12:00:00Z",
        }
        result = run_topo(*args, request=request)
        assert result.returncode == 0, result.stdout
        identity = json.loads(result.stdout)
    delta = tmp_path / "delta.topo"
    migrate_storage(package, delta, validate=load_and_validate_generation)
    snapshot = FileSystemStorageAdapter(delta).load()
    assert snapshot is not None
    return snapshot


@pytest.fixture
def snapshot(tmp_path: Path) -> Any:
    return _fixture(tmp_path)


def test_incremental_and_full_validation_agree(snapshot: Any) -> None:
    assert load_and_validate_generation(snapshot) == load_and_validate_generation(
        snapshot, incremental=False
    )


@pytest.mark.parametrize(
    "corruption", ["literal", "reference", "duplicate", "version", "raw"]
)
def test_semantic_corruption_in_retained_generation_is_never_reused(
    snapshot: Any, corruption: str
) -> None:
    retained = {
        key: dict(value) for key, value in snapshot.retained_generation_files.items()
    }
    generation_id = list(retained)[-1]
    files = retained[generation_id]
    assertions = json.loads(files["assertions.json"])
    observed = next(
        item
        for item in assertions["records"]
        if item["predicate"] == "domain.cashflow/money"
    )
    if corruption == "literal":
        observed["object_value"]["value"]["amount"] = "2.00"
    elif corruption == "reference":
        observed["subject_ref"]["id"] = uuid7()
    elif corruption == "duplicate":
        assertions["records"].append(observed)
    elif corruption == "version":
        assertions["schema_version"] = (
            "topo.context/0.1"
            if assertions["schema_version"] == "topo.context/0.2"
            else "topo.context/0.2"
        )
    if corruption != "raw":
        payload = (json.dumps(assertions, sort_keys=True, indent=2) + "\n").encode()
        files["assertions.json"] = payload
        manifest = json.loads(files["manifest.json"])
        manifest["files"]["assertions.json"] = (
            "sha256:" + hashlib.sha256(payload).hexdigest()
        )
        files["manifest.json"] = json.dumps(manifest).encode()
    evidence = dict(snapshot.evidence_records)
    if corruption == "raw":
        evidence[next(iter(evidence))] = b"{}"
    corrupted = replace(
        snapshot, retained_generation_files=retained, evidence_records=evidence
    )
    errors = []
    for incremental in (False, True):
        with pytest.raises(PackageIntegrityError) as failure:
            load_and_validate_generation(corrupted, incremental=incremental)
        errors.append(str(failure.value))
    assert errors[0] == errors[1]
