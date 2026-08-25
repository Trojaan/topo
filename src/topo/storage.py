from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, Optional

from topo.canonical_validation import validate_initial_generation
from topo.identifiers import uuid7


CONTEXT_SCHEMA_VERSION = "topo.context/0.1"
MANIFEST_SCHEMA_VERSION = "topo.manifest/0.1"
COLLECTION_FILES = (
    "entities.json",
    "assertions.json",
    "evidence.json",
    "proposals.json",
)


@dataclass(frozen=True)
class Initialization:
    result: Dict[str, Any]
    replayed: bool


@dataclass(frozen=True)
class InitialPackage:
    result: Dict[str, Any]
    generation_files: Dict[str, bytes]
    journal: bytes


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


def _build_initial_package(
    *, operation_id: str, actor: Dict[str, str], reason: str
) -> InitialPackage:
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
                "operation_id": operation_id,
                "mutation_id": mutation_id,
                "operation": "context.init",
                "actor": actor,
                "reason": reason,
                "generation_before": None,
                "generation_after": generation_id,
                "recorded_at": instant,
            }
        ],
    }
    result = {
        "context_id": context_id,
        "generation_id": generation_id,
        "mutation_id": mutation_id,
        "person_id": person_id,
        "household_id": household_id,
        "membership_assertion_id": membership_id,
    }
    initial = InitialPackage(
        result=result,
        generation_files={**collections, "manifest.json": _json_bytes(manifest)},
        journal=_json_bytes(journal),
    )
    validate_initial_generation(initial.generation_files, initial.result)
    return initial


def _publish_initial_package(package: Path, initial: InitialPackage) -> None:
    parent = package.parent
    temporary = Path(tempfile.mkdtemp(prefix=f".{package.name}.staging-", dir=str(parent)))
    os.chmod(temporary, 0o700)
    try:
        generations = temporary / "generations"
        staging = temporary / "staging"
        evidence_records = temporary / "evidence" / "records"
        history = temporary / "history"
        for directory in (generations, staging, evidence_records, history):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)

        generation_id = initial.result["generation_id"]
        staged_generation = staging / generation_id
        staged_generation.mkdir(mode=0o700)
        for filename, payload in initial.generation_files.items():
            _write_durable(staged_generation / filename, payload)
        _sync_directory(staged_generation)

        os.replace(staged_generation, generations / generation_id)
        _sync_directory(generations)
        _write_durable(history / "journal.json", initial.journal)
        _sync_directory(history)

        temporary_current = temporary / ".CURRENT.tmp"
        _write_durable(temporary_current, (generation_id + "\n").encode("ascii"))
        os.replace(temporary_current, temporary / "CURRENT")
        _sync_directory(temporary)

        if package.exists():
            raise FileExistsError(str(package))
        os.replace(temporary, package)
        _sync_directory(parent)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _replayed_initialization(
    package: Path, operation_id: str
) -> Optional[Initialization]:
    if not package.exists():
        return None
    journal = _read_json(package / "history" / "journal.json")
    entries = journal.get("entries", [])
    if not entries or entries[0].get("operation_id") != operation_id:
        raise FileExistsError(str(package))

    generation_id = (package / "CURRENT").read_text(encoding="utf-8").strip()
    generation = package / "generations" / generation_id
    manifest = _read_json(generation / "manifest.json")
    for filename in COLLECTION_FILES:
        payload = (generation / filename).read_bytes()
        actual = "sha256:" + hashlib.sha256(payload).hexdigest()
        if manifest["files"].get(filename) != actual:
            raise ValueError(f"checksum mismatch for {filename}")

    entities = _read_json(generation / "entities.json")["records"]
    assertions = _read_json(generation / "assertions.json")["records"]
    entity_ids = {record["entity_type"]: record["id"] for record in entities}
    membership = next(
        record
        for record in assertions
        if record["predicate"] == "domain.parties/household_membership"
    )
    result = {
        "context_id": manifest["context_id"],
        "generation_id": generation_id,
        "mutation_id": manifest["mutation_id"],
        "person_id": entity_ids["person"],
        "household_id": entity_ids["household"],
        "membership_assertion_id": membership["id"],
    }
    return Initialization(result=result, replayed=True)


def initialize_package(
    package: Path,
    *,
    operation_id: str,
    actor: Dict[str, str],
    reason: str,
) -> Initialization:
    """Create and atomically publish, or idempotently replay, the first generation."""
    replay = _replayed_initialization(package, operation_id)
    if replay is not None:
        return replay
    initial = _build_initial_package(
        operation_id=operation_id,
        actor=actor,
        reason=reason,
    )
    _publish_initial_package(package, initial)
    return Initialization(result=initial.result, replayed=False)
