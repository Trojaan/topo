"""Versioned, meaning-free physical representation of generation snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

FORMAT_VERSION = "topo.storage/0.2"
COLLECTIONS = ("entities.json", "assertions.json", "evidence.json", "proposals.json")
CHECKPOINT_INTERVAL = 16


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _object(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("delta payload must be an object")
    return cast(dict[str, Any], value)


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_physical_current(physical: dict[str, bytes]) -> None:
    """Check the current delta's physical bytes before using a materialized view."""
    if "storage.json" not in physical:
        return
    if "changes.json" not in physical:
        raise ValueError("current delta is missing changes")
    metadata = _object(physical["storage.json"])
    if (
        metadata.get("schema_version") != FORMAT_VERSION
        or metadata.get("kind") != "delta"
    ):
        raise ValueError("current delta format is invalid")
    if metadata.get("changes_checksum") != _digest(physical["changes.json"]):
        raise ValueError("current delta checksum mismatch")


def _records(payload: bytes) -> tuple[str, dict[str, dict[str, Any]]]:
    collection = _object(payload)
    version = collection.get("schema_version")
    raw = collection.get("records")
    if not isinstance(version, str) or not isinstance(raw, list):
        raise TypeError("invalid canonical collection")
    records: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise TypeError("invalid canonical record")
        identifier = cast(str, item["id"])
        if identifier in records:
            raise ValueError("duplicate canonical record")
        records[identifier] = item
    if list(records) != sorted(records):
        raise ValueError("canonical records are not sorted")
    return version, records


def encode_generation(
    generation_files: dict[str, bytes],
    previous_files: dict[str, bytes] | None,
    *,
    checkpoint: bool,
    changes: dict[str, object] | None = None,
) -> dict[str, bytes]:
    """Store a checkpoint or a record-level delta against the preceding state."""
    if checkpoint or previous_files is None:
        return dict(generation_files)
    supplied = changes
    changes = {} if supplied is None else supplied
    for filename in () if supplied is not None else COLLECTIONS:
        version, current = _records(generation_files[filename])
        previous_version, previous = _records(previous_files[filename])
        removed = sorted(set(previous) - set(current))
        upsert = [
            current[identifier]
            for identifier in sorted(current)
            if identifier not in previous or current[identifier] != previous[identifier]
        ]
        if removed or upsert or version != previous_version:
            changes[filename] = {
                "schema_version": version,
                "removed": removed,
                "upsert": upsert,
            }
    payload = _json_bytes(changes)
    physical = {
        "manifest.json": generation_files["manifest.json"],
        "changes.json": payload,
        "storage.json": _json_bytes(
            {
                "schema_version": FORMAT_VERSION,
                "kind": "delta",
                "changes_checksum": _digest(payload),
                "base_generation": _object(previous_files["manifest.json"])[
                    "generation_id"
                ],
            }
        ),
    }
    for filename, content in generation_files.items():
        if filename.startswith("rule-package."):
            physical[filename] = content
    return physical


def _record_fragment(record: dict[str, Any]) -> bytes:
    return b"\n".join(
        b"    " + line for line in _json_bytes(record).rstrip(b"\n").split(b"\n")
    )


def decode_generation(
    generation_id: str,
    physical: dict[str, bytes],
    previous_files: dict[str, bytes] | None,
    *,
    cached_collections: dict[str, tuple[str, dict[str, dict[str, Any]]]] | None = None,
    cached_fragments: dict[str, dict[str, bytes]] | None = None,
) -> dict[str, bytes]:
    """Reconstruct and checksum the logical snapshot; reject malformed deltas."""
    if "storage.json" not in physical:
        if previous_files is None or all(name in physical for name in COLLECTIONS):
            logical = physical
        else:
            raise ValueError("delta chain has no checkpoint")
    else:
        if previous_files is None:
            raise ValueError("delta chain has no base checkpoint")
        metadata = _object(physical["storage.json"])
        expected_base = _object(previous_files["manifest.json"])["generation_id"]
        if metadata != {
            "schema_version": FORMAT_VERSION,
            "kind": "delta",
            "changes_checksum": _digest(physical["changes.json"]),
            "base_generation": expected_base,
        }:
            raise ValueError("delta metadata mismatch")
        changes = _object(physical["changes.json"])
        if set(changes) - set(COLLECTIONS):
            raise ValueError("delta contains an unsupported collection")
        logical = {"manifest.json": physical["manifest.json"]}
        for filename in COLLECTIONS:
            if filename not in changes:
                logical[filename] = previous_files[filename]
                continue
            version, records = (
                cached_collections[filename]
                if cached_collections is not None
                else _records(previous_files[filename])
            )
            fragments = None
            if cached_fragments is not None:
                if filename not in cached_fragments:
                    cached_fragments[filename] = {
                        identifier: _record_fragment(record)
                        for identifier, record in records.items()
                    }
                fragments = cached_fragments[filename]
            change = changes[filename]
            if not isinstance(change, dict) or set(change) != {
                "schema_version",
                "removed",
                "upsert",
            }:
                raise TypeError("invalid collection delta")
            version = change["schema_version"]
            removed = change["removed"]
            upsert = change["upsert"]
            if (
                not isinstance(version, str)
                or not isinstance(removed, list)
                or not isinstance(upsert, list)
            ):
                raise TypeError("invalid collection delta")
            if removed != sorted(set(removed)) or any(
                not isinstance(identifier, str) or identifier not in records
                for identifier in removed
            ):
                raise ValueError("invalid delta removal")
            for identifier in removed:
                del records[identifier]
                if fragments is not None:
                    del fragments[identifier]
            ids: list[str] = []
            for record in upsert:
                if not isinstance(record, dict) or not isinstance(
                    record.get("id"), str
                ):
                    raise TypeError("invalid delta upsert")
                ids.append(record["id"])
                records[record["id"]] = record
                if fragments is not None:
                    fragments[record["id"]] = _record_fragment(record)
            if ids != sorted(set(ids)):
                raise ValueError("invalid delta upsert order")
            if cached_collections is not None:
                cached_collections[filename] = (version, records)
            if fragments is not None and records:
                logical[filename] = (
                    b'{\n  "records": [\n'
                    + b",\n".join(fragments[key] for key in sorted(records))
                    + b'\n  ],\n  "schema_version": '
                    + json.dumps(version, ensure_ascii=False).encode()
                    + b"\n}\n"
                )
            else:
                logical[filename] = _json_bytes(
                    {
                        "schema_version": version,
                        "records": [records[key] for key in sorted(records)],
                    }
                )
        for filename, content in physical.items():
            if filename.startswith("rule-package."):
                logical[filename] = content
        if set(physical) != {
            "manifest.json",
            "changes.json",
            "storage.json",
            *(name for name in physical if name.startswith("rule-package.")),
        }:
            raise ValueError("delta contains an unexpected file")
    manifest = _object(logical["manifest.json"])
    if manifest.get("generation_id") != generation_id:
        raise ValueError("generation ID mismatch")
    expected = manifest.get("files")
    if not isinstance(expected, dict) or set(logical) != {"manifest.json", *expected}:
        raise ValueError("logical snapshot file set mismatch")
    for filename, checksum in expected.items():
        if not isinstance(filename, str) or checksum != _digest(logical[filename]):
            raise ValueError(f"logical snapshot checksum mismatch: {filename}")
    return logical


class DeltaReader:
    """Reuse parsed record maps while walking an immutable generation chain."""

    def __init__(self) -> None:
        self.previous: dict[str, bytes] | None = None
        self.collections: dict[str, tuple[str, dict[str, dict[str, Any]]]] = {}
        self.fragments: dict[str, dict[str, bytes]] = {}

    def reset(self) -> None:
        self.previous = None
        self.collections = {}
        self.fragments = {}

    def read(self, generation_id: str, physical: dict[str, bytes]) -> dict[str, bytes]:
        checkpoint = "storage.json" not in physical
        logical = decode_generation(
            generation_id,
            physical,
            self.previous,
            cached_collections=(None if checkpoint else self.collections),
            cached_fragments=(None if checkpoint else self.fragments),
        )
        if checkpoint:
            self.fragments = {}
            self.collections = {
                filename: _records(logical[filename]) for filename in COLLECTIONS
            }
        self.previous = logical
        return logical
