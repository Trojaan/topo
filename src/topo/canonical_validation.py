from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from topo.identifiers import UUID7_PATTERN


def _uuid7() -> Dict[str, Any]:
    return {"type": "string", "pattern": UUID7_PATTERN}


def _collection_schema(record_schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "records"],
        "properties": {
            "schema_version": {"const": "topo.context/0.1"},
            "records": {"type": "array", "items": record_schema},
        },
    }


def _entity_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "entity_type", "module_id", "created_at"],
        "properties": {
            "id": _uuid7(),
            "entity_type": {"enum": ["context", "person", "household"]},
            "module_id": {"enum": ["topo.core", "domain.parties"]},
            "created_at": {"type": "string", "format": "date-time"},
        },
    }


def _ref() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref_type", "id"],
        "properties": {
            "ref_type": {"type": "string"},
            "id": _uuid7(),
        },
    }


def _assertion_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "subject_ref",
            "predicate",
            "object_ref",
            "valid_time",
            "recorded_at",
            "knowledge_type",
            "verification_status",
            "provenance",
            "supersedes",
            "module_data",
        ],
        "properties": {
            "id": _uuid7(),
            "subject_ref": _ref(),
            "predicate": {"const": "domain.parties/household_membership"},
            "object_ref": _ref(),
            "valid_time": {
                "type": "object",
                "additionalProperties": False,
                "required": ["start", "end_exclusive"],
                "properties": {
                    "start": {"type": "string", "format": "date"},
                    "end_exclusive": {"type": ["string", "null"], "format": "date"},
                },
            },
            "recorded_at": {"type": "string", "format": "date-time"},
            "knowledge_type": {"const": "user_provided"},
            "verification_status": {"const": "confirmed"},
            "provenance": {"type": "array", "minItems": 1, "items": _ref()},
            "supersedes": {"type": "null"},
            "module_data": {"type": "object"},
        },
    }


def _evidence_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "evidence_type", "recorded_at", "statement_type"],
        "properties": {
            "id": _uuid7(),
            "evidence_type": {"const": "user_statement"},
            "recorded_at": {"type": "string", "format": "date-time"},
            "statement_type": {"const": "context_initialization"},
        },
    }


COLLECTION_SCHEMAS = {
    "entities.json": _collection_schema(_entity_schema()),
    "assertions.json": _collection_schema(_assertion_schema()),
    "evidence.json": _collection_schema(_evidence_schema()),
    "proposals.json": _collection_schema({"type": "object"}),
}


MANIFEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "context_id",
        "generation_id",
        "based_on",
        "package_version",
        "context_schema_version",
        "mutation_id",
        "recorded_at",
        "modules",
        "active_rule_packages",
        "files",
    ],
    "properties": {
        "schema_version": {"const": "topo.manifest/0.1"},
        "context_id": _uuid7(),
        "generation_id": _uuid7(),
        "based_on": {"type": "null"},
        "package_version": {"const": "0.1"},
        "context_schema_version": {"const": "topo.context/0.1"},
        "mutation_id": _uuid7(),
        "recorded_at": {"type": "string", "format": "date-time"},
        "modules": {"type": "array", "minItems": 1, "items": {"type": "object"}},
        "active_rule_packages": {"type": "array", "maxItems": 0},
        "files": {
            "type": "object",
            "additionalProperties": False,
            "required": list(COLLECTION_SCHEMAS),
            "properties": {
                filename: {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}$"}
                for filename in COLLECTION_SCHEMAS
            },
        },
    },
}


def validate_initial_generation(
    generation_files: Dict[str, bytes], result: Dict[str, Any]
) -> None:
    expected_files = {*COLLECTION_SCHEMAS, "manifest.json"}
    if set(generation_files) != expected_files:
        raise ValueError("initial generation is incomplete")

    parsed = {
        filename: json.loads(payload.decode("utf-8"))
        for filename, payload in generation_files.items()
    }
    checker = FormatChecker()
    manifest = parsed["manifest.json"]
    Draft202012Validator(MANIFEST_SCHEMA, format_checker=checker).validate(manifest)
    for filename, schema in COLLECTION_SCHEMAS.items():
        collection = parsed[filename]
        Draft202012Validator(schema, format_checker=checker).validate(collection)
        ids = [record["id"] for record in collection["records"]]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{filename} records must have unique sorted ids")
        checksum = "sha256:" + hashlib.sha256(generation_files[filename]).hexdigest()
        if manifest["files"][filename] != checksum:
            raise ValueError(f"checksum mismatch for {filename}")

    if manifest["context_id"] != result["context_id"]:
        raise ValueError("manifest context does not match initialization result")
    if manifest["generation_id"] != result["generation_id"]:
        raise ValueError("manifest generation does not match initialization result")

    entity_ids = {record["id"] for record in parsed["entities.json"]["records"]}
    evidence_ids = {record["id"] for record in parsed["evidence.json"]["records"]}
    for assertion in parsed["assertions.json"]["records"]:
        if assertion["subject_ref"]["id"] not in entity_ids:
            raise ValueError("assertion subject does not resolve")
        if assertion["object_ref"]["id"] not in entity_ids:
            raise ValueError("assertion object does not resolve")
        if any(ref["id"] not in evidence_ids for ref in assertion["provenance"]):
            raise ValueError("assertion provenance does not resolve")
