from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from topo.identifiers import uuid7


def _run(package: Path, *words: str, request: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "topo", *words, "--package", str(package), "--json"],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, Any], json.loads(completed.stdout))


def _mutation(context_id: str, generation: str) -> dict[str, Any]:
    return {
        "contract_version": "topo.cli/0.1",
        "operation_id": uuid7(),
        "context_id": context_id,
        "expected_generation": generation,
        "actor": {"actor_type": "human", "actor_id": "test-user"},
        "reason": "Exercise delta storage lifecycle",
    }


def test_legacy_package_migrates_and_keeps_lifecycle_semantics(tmp_path: Path) -> None:
    old = tmp_path / "legacy.topo"
    new = tmp_path / "delta.topo"
    initialized = _run(
        old, "context", "init", request={"contract_version": "topo.cli/0.1"}
    )
    context_id = initialized["context_id"]
    first = initialized["generation_after"]
    evidence_id = json.loads(
        (old / "generations" / first / "evidence.json").read_text()
    )["records"][0]["id"]
    module_versions = {
        item["module_id"]: item["module_version"]
        for item in json.loads(
            (old / "generations" / first / "manifest.json").read_text()
        )["modules"]
    }
    migrated = _run(
        old,
        "context",
        "storage-migrate",
        "--output",
        str(new),
        request={"contract_version": "topo.cli/0.1"},
    )
    assert migrated["result"]["storage_format"] == "topo.storage/0.2"
    assert (old / "CURRENT").read_text() == (new / "CURRENT").read_text()
    assert (new / "storage-format.json").is_file()

    migration_request = {
        **_mutation(context_id, first),
        "target_package_version": "0.2",
        "target_context_schema_version": "topo.context/0.2",
        "target_module_versions": module_versions,
        "authorization": None,
    }
    preview = _run(new, "context", "migrate", request=migration_request)
    migration_request["authorization"] = {
        "preview_ref": preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "test-user"},
        "authorized_at": "2026-09-03T10:00:00Z",
    }
    updated = _run(new, "context", "migrate", request=migration_request)
    second = updated["generation_after"]
    replay = _run(new, "context", "migrate", request=migration_request)
    assert replay["outcome"] == "no_change"
    assert replay["generation_after"] == second
    assert (new / "generations" / second / "changes.json").is_file()
    assert (
        _run(new, "context", "verify", request={"contract_version": "topo.cli/0.1"})[
            "result"
        ]["generations_verified"]
        == 2
    )
    restored = _run(
        new,
        "context",
        "restore",
        request={**_mutation(context_id, second), "restore_generation": first},
    )
    compacted = _run(
        new,
        "context",
        "compact",
        request={
            **_mutation(context_id, restored["generation_after"]),
            "retain_latest": 2,
            "restore_generations": [first],
        },
    )
    assert (
        _run(new, "context", "verify", request={"contract_version": "topo.cli/0.1"})[
            "result"
        ]["generations_verified"]
        == 3
    )
    scrubbed = _run(
        new,
        "context",
        "privacy-scrub",
        request={
            **_mutation(context_id, compacted["generation_after"]),
            "evidence_ids": [evidence_id],
        },
    )
    assert scrubbed["outcome"] == "succeeded"
    assert (
        _run(new, "context", "verify", request={"contract_version": "topo.cli/0.1"})[
            "result"
        ]["generations_verified"]
        == 4
    )
    assert (old / "generations" / first / "evidence.json").is_file()
