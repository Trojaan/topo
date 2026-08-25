from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict

from topo.identifiers import uuid7


CONTEXT_SCHEMA_VERSION = "topo.context/0.1"
MANIFEST_SCHEMA_VERSION = "topo.manifest/0.1"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_durable(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _collection(records: list[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "records": sorted(records, key=lambda record: record["id"]),
    }


def initialize_package(package: Path) -> Dict[str, Any]:
    """Create and publish the complete first canonical generation."""
    if package.exists():
        raise FileExistsError(str(package))

    now = datetime.now(timezone.utc)
    instant = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    effective_date = now.date().isoformat()
    context_id = uuid7()
    household_id = uuid7()
    person_id = uuid7()
    evidence_id = uuid7()
    membership_id = uuid7()
    generation_id = uuid7()
    mutation_id = uuid7()

    entities = _collection(
        [
            {
                "id": context_id,
                "entity_type": "context",
                "module_id": "topo.core",
                "created_at": instant,
            },
            {
                "id": household_id,
                "entity_type": "household",
                "module_id": "domain.parties",
                "created_at": instant,
            },
            {
                "id": person_id,
                "entity_type": "person",
                "module_id": "domain.parties",
                "created_at": instant,
            },
        ]
    )
    evidence = _collection(
        [
            {
                "id": evidence_id,
                "evidence_type": "user_statement",
                "recorded_at": instant,
                "statement_type": "context_initialization",
            }
        ]
    )
    assertions = _collection(
        [
            {
                "id": membership_id,
                "subject_ref": {"ref_type": "entity", "id": person_id},
                "predicate": "domain.parties/household_membership",
                "object_ref": {"ref_type": "entity", "id": household_id},
                "valid_time": {"start": effective_date, "end_exclusive": None},
                "recorded_at": instant,
                "knowledge_type": "user_provided",
                "verification_status": "confirmed",
                "provenance": [{"ref_type": "evidence", "id": evidence_id}],
                "supersedes": None,
                "module_data": {},
            }
        ]
    )
    collections = {
        "entities.json": _json_bytes(entities),
        "assertions.json": _json_bytes(assertions),
        "evidence.json": _json_bytes(evidence),
        "proposals.json": _json_bytes(_collection([])),
    }
    checksums = {
        filename: f"sha256:{hashlib.sha256(payload).hexdigest()}"
        for filename, payload in collections.items()
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "context_id": context_id,
        "generation_id": generation_id,
        "based_on": None,
        "package_version": "0.1",
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "mutation_id": mutation_id,
        "recorded_at": instant,
        "modules": [
            {
                "module_id": "topo.core",
                "module_version": "0.1.0",
                "checksum": "sha256:" + hashlib.sha256(b"topo.core/0.1.0").hexdigest(),
            },
            {
                "module_id": "domain.parties",
                "module_version": "0.1.0",
                "checksum": "sha256:" + hashlib.sha256(b"domain.parties/0.1.0").hexdigest(),
            },
        ],
        "active_rule_packages": [],
        "files": checksums,
    }
    journal = {
        "schema_version": "topo.journal/0.1",
        "entries": [
            {
                "mutation_id": mutation_id,
                "operation": "context.init",
                "generation_before": None,
                "generation_after": generation_id,
                "recorded_at": instant,
            }
        ],
    }

    created_package = False
    try:
        package.mkdir(mode=0o700, parents=False)
        created_package = True
        generations = package / "generations"
        staging = package / "staging"
        evidence_records = package / "evidence" / "records"
        history = package / "history"
        for directory in (generations, staging, evidence_records, history):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)

        staged_generation = staging / generation_id
        staged_generation.mkdir(mode=0o700)
        for filename, payload in collections.items():
            _write_durable(staged_generation / filename, payload)
        _write_durable(staged_generation / "manifest.json", _json_bytes(manifest))
        _sync_directory(staged_generation)

        published_generation = generations / generation_id
        os.replace(staged_generation, published_generation)
        _sync_directory(generations)

        _write_durable(history / "journal.json", _json_bytes(journal))
        _sync_directory(history)

        current_temporary = package / (".CURRENT." + uuid7())
        _write_durable(current_temporary, (generation_id + "\n").encode("ascii"))
        os.replace(current_temporary, package / "CURRENT")
        _sync_directory(package)
    except BaseException:
        if created_package and not (package / "CURRENT").exists():
            shutil.rmtree(package)
        raise

    return {
        "context_id": context_id,
        "generation_id": generation_id,
        "mutation_id": mutation_id,
        "person_id": person_id,
        "household_id": household_id,
        "membership_assertion_id": membership_id,
    }
