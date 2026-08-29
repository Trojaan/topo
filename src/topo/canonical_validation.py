from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from topo.errors import PackageIntegrityError
from topo.identifiers import UUID7_PATTERN
from topo.models import (
    AssertionRecord,
    CanonicalCollection,
    ContextInitResult,
    EntityRecord,
    EvidenceRecord,
    Journal,
    JsonObject,
    Manifest,
    ProposalRecord,
    SourceImportRecord,
    SourceRecordEvidenceRecord,
)
from topo.storage import StoredPackageSnapshot


def _uuid7() -> JsonObject:
    return {"type": "string", "pattern": UUID7_PATTERN}


def _collection_schema(record_schema: JsonObject) -> JsonObject:
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


def _entity_schema() -> JsonObject:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "entity_type", "module_id", "created_at"],
        "properties": {
            "id": _uuid7(),
            "entity_type": {
                "enum": ["context", "person", "household", "account", "transaction"]
            },
            "module_id": {
                "enum": [
                    "topo.core",
                    "domain.parties",
                    "domain.accounts",
                    "domain.cashflow",
                ]
            },
            "created_at": {"type": "string", "format": "date-time"},
        },
    }


def _ref() -> JsonObject:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref_type", "id"],
        "properties": {
            "ref_type": {"type": "string"},
            "id": _uuid7(),
        },
    }


def _validate_acyclic_lineage(
    predecessors: dict[str, str], *, description: str
) -> None:
    for start in predecessors:
        seen: set[str] = set()
        current: str | None = start
        while current is not None:
            if current in seen:
                raise PackageIntegrityError(f"{description} lineage contains a cycle")
            seen.add(current)
            current = predecessors.get(current)


def _assertion_schema() -> JsonObject:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "subject_ref",
            "predicate",
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
            "predicate": {"type": "string", "minLength": 1},
            "object_ref": _ref(),
            "object_value": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value_type", "value"],
                "properties": {
                    "value_type": {"type": "string", "minLength": 1},
                    "value": {},
                },
            },
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
            "knowledge_type": {
                "enum": [
                    "observed",
                    "user_provided",
                    "inferred",
                    "calculated",
                    "assumed",
                    "projected",
                ]
            },
            "verification_status": {"const": "confirmed"},
            "provenance": {"type": "array", "minItems": 1, "items": _ref()},
            "supersedes": {"oneOf": [_uuid7(), {"type": "null"}]},
            "module_data": {"type": "object"},
        },
        "oneOf": [
            {"required": ["object_ref"], "not": {"required": ["object_value"]}},
            {"required": ["object_value"], "not": {"required": ["object_ref"]}},
        ],
    }


def _evidence_schema() -> JsonObject:
    user_statement: JsonObject = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "evidence_type",
            "recorded_at",
            "statement_type",
            "statement",
        ],
        "properties": {
            "id": _uuid7(),
            "evidence_type": {"const": "user_statement"},
            "recorded_at": {"type": "string", "format": "date-time"},
            "statement_type": {
                "enum": [
                    "context_initialization",
                    "proposal_confirmation",
                    "proposal_correction",
                ]
            },
            "statement": {"oneOf": [{"type": "object"}, {"type": "null"}]},
        },
    }
    source_record: JsonObject = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "evidence_type",
            "source",
            "record_path",
            "recorded_at",
            "supersedes",
        ],
        "properties": {
            "id": _uuid7(),
            "evidence_type": {"const": "source_record"},
            "source": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "adapter_id",
                    "adapter_version",
                    "source_id",
                    "record_id",
                    "record_checksum",
                ],
                "properties": {
                    "adapter_id": {"type": "string", "minLength": 1},
                    "adapter_version": {"type": "string", "minLength": 1},
                    "source_id": {"type": "string", "minLength": 1},
                    "record_id": {"type": "string", "minLength": 1},
                    "record_checksum": {
                        "type": "string",
                        "pattern": r"^sha256:[0-9a-f]{64}$",
                    },
                },
            },
            "record_path": {
                "type": "string",
                "pattern": r"^evidence/records/[0-9a-f-]+\.json$",
            },
            "recorded_at": {"type": "string", "format": "date-time"},
            "supersedes": {"oneOf": [_uuid7(), {"type": "null"}]},
        },
    }
    return {"oneOf": [user_statement, source_record]}


def _proposal_schema() -> JsonObject:
    object_value: JsonObject = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value_type", "value"],
        "properties": {
            "value_type": {"type": "string", "minLength": 1},
            "value": {},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "proposal_type",
            "producer",
            "proposed_assertion",
            "evidence_refs",
            "reason_ref",
            "detection",
            "status",
            "created_at",
            "decision",
        ],
        "properties": {
            "id": _uuid7(),
            "proposal_type": {"const": "assertion"},
            "producer": {
                "type": "object",
                "additionalProperties": False,
                "required": ["producer_type", "producer_id", "producer_version"],
                "properties": {
                    "producer_type": {
                        "enum": ["agent", "rule_module", "source_adapter"]
                    },
                    "producer_id": {"type": "string", "minLength": 1},
                    "producer_version": {"type": "string", "minLength": 1},
                },
            },
            "proposed_assertion": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "subject_ref",
                    "predicate",
                    "valid_time",
                    "knowledge_type",
                    "module_data",
                ],
                "properties": {
                    "subject_ref": _ref(),
                    "predicate": {"type": "string", "minLength": 1},
                    "object_ref": _ref(),
                    "object_value": object_value,
                    "valid_time": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["start", "end_exclusive"],
                        "properties": {
                            "start": {"type": "string", "format": "date"},
                            "end_exclusive": {
                                "type": ["string", "null"],
                                "format": "date",
                            },
                        },
                    },
                    "knowledge_type": {"const": "inferred"},
                    "module_data": {"type": "object"},
                },
                "oneOf": [
                    {
                        "required": ["object_ref"],
                        "not": {"required": ["object_value"]},
                    },
                    {
                        "required": ["object_value"],
                        "not": {"required": ["object_ref"]},
                    },
                ],
            },
            "evidence_refs": {"type": "array", "minItems": 1, "items": _ref()},
            "reason_ref": {"type": "string", "minLength": 1},
            "detection": {
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["scheme", "score"],
                        "properties": {
                            "scheme": {"type": "string", "minLength": 1},
                            "score": {
                                "type": "string",
                                "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$",
                            },
                        },
                    },
                    {"type": "null"},
                ]
            },
            "status": {
                "enum": ["open", "confirmed", "corrected", "rejected", "superseded"]
            },
            "created_at": {"type": "string", "format": "date-time"},
            "decision": {
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "outcome",
                            "actor",
                            "decided_at",
                            "mutation_id",
                            "assertion_id",
                        ],
                        "properties": {
                            "outcome": {"enum": ["confirmed", "corrected", "rejected"]},
                            "actor": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["actor_type", "actor_id"],
                                "properties": {
                                    "actor_type": {
                                        "enum": [
                                            "human",
                                            "agent",
                                            "rule_module",
                                            "source_adapter",
                                            "system",
                                        ]
                                    },
                                    "actor_id": {"type": "string", "minLength": 1},
                                },
                            },
                            "decided_at": {"type": "string", "format": "date-time"},
                            "mutation_id": _uuid7(),
                            "assertion_id": {"oneOf": [_uuid7(), {"type": "null"}]},
                        },
                    },
                    {"type": "null"},
                ]
            },
        },
    }


COLLECTION_SCHEMAS = {
    "entities.json": _collection_schema(_entity_schema()),
    "assertions.json": _collection_schema(_assertion_schema()),
    "evidence.json": _collection_schema(_evidence_schema()),
    "proposals.json": _collection_schema(_proposal_schema()),
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
        "based_on": {"oneOf": [_uuid7(), {"type": "null"}]},
        "package_version": {"const": "0.1"},
        "context_schema_version": {"const": "topo.context/0.1"},
        "mutation_id": _uuid7(),
        "recorded_at": {"type": "string", "format": "date-time"},
        "modules": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["module_id", "module_version", "checksum"],
                "properties": {
                    "module_id": {"type": "string", "minLength": 1},
                    "module_version": {"type": "string", "minLength": 1},
                    "checksum": {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}$"},
                },
            },
        },
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


@dataclass(frozen=True)
class ValidatedPackage:
    manifest: Manifest
    entities: CanonicalCollection[EntityRecord]
    assertions: CanonicalCollection[AssertionRecord]
    evidence: CanonicalCollection[EvidenceRecord]
    proposals: CanonicalCollection[ProposalRecord]
    journal: Journal
    source_records: dict[str, bytes]
    initialization_result: ContextInitResult


def _validate_snapshot(
    snapshot: StoredPackageSnapshot, *, require_journal_tip: bool = True
) -> ValidatedPackage:
    generation_files = snapshot.generation_files
    expected_files = {*COLLECTION_SCHEMAS, "manifest.json"}
    if set(generation_files) != expected_files:
        raise PackageIntegrityError("generation has missing or unexpected files")

    parsed = {
        filename: json.loads(payload.decode("utf-8"))
        for filename, payload in generation_files.items()
    }
    checker = FormatChecker()
    manifest_value = parsed["manifest.json"]
    Draft202012Validator(MANIFEST_SCHEMA, format_checker=checker).validate(
        manifest_value
    )
    for filename, schema in COLLECTION_SCHEMAS.items():
        collection_value = parsed[filename]
        Draft202012Validator(schema, format_checker=checker).validate(collection_value)
        collection = cast(JsonObject, collection_value)
        records = cast(list[JsonObject], collection["records"])
        ids = [cast(str, record["id"]) for record in records]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{filename} records must have unique sorted ids")
        checksum = "sha256:" + hashlib.sha256(generation_files[filename]).hexdigest()
        manifest_mapping = cast(JsonObject, manifest_value)
        manifest_files = cast(dict[str, str], manifest_mapping["files"])
        if manifest_files[filename] != checksum:
            raise PackageIntegrityError(f"checksum mismatch for {filename}")

    manifest = Manifest.model_validate_json(
        generation_files["manifest.json"], strict=True
    )
    module_ids = [module.module_id for module in manifest.modules]
    if len(module_ids) != len(set(module_ids)):
        raise PackageIntegrityError("manifest module pins must be unique")
    entities = CanonicalCollection[EntityRecord].model_validate_json(
        generation_files["entities.json"], strict=True
    )
    assertions = CanonicalCollection[AssertionRecord].model_validate_json(
        generation_files["assertions.json"], strict=True
    )
    evidence = CanonicalCollection[EvidenceRecord].model_validate_json(
        generation_files["evidence.json"], strict=True
    )
    proposals = CanonicalCollection[ProposalRecord].model_validate_json(
        generation_files["proposals.json"], strict=True
    )
    journal = Journal.model_validate_json(snapshot.journal, strict=True)

    if manifest.generation_id != snapshot.current_generation:
        raise PackageIntegrityError("CURRENT does not match the manifest generation")

    entity_ids = {record.id for record in entities.records}
    entity_by_id = {record.id: record for record in entities.records}
    evidence_ids = {record.id for record in evidence.records}
    evidence_by_id = {record.id: record for record in evidence.records}
    proposal_ids = {record.id for record in proposals.records}
    for assertion in assertions.records:
        if assertion.subject_ref.ref_type != "entity":
            raise PackageIntegrityError("assertion subject has an invalid ref type")
        if assertion.subject_ref.id not in entity_ids:
            raise PackageIntegrityError("assertion subject does not resolve")
        if assertion.object_ref is not None:
            if assertion.object_ref.ref_type != "entity":
                raise PackageIntegrityError("assertion object has an invalid ref type")
            if assertion.object_ref.id not in entity_ids:
                raise PackageIntegrityError("assertion object does not resolve")
        if any(
            (ref.ref_type == "evidence" and ref.id not in evidence_ids)
            or (ref.ref_type == "proposal" and ref.id not in proposal_ids)
            or ref.ref_type not in {"evidence", "proposal"}
            for ref in assertion.provenance
        ):
            raise PackageIntegrityError("assertion provenance does not resolve")
        if assertion.supersedes is not None:
            predecessor = next(
                (
                    candidate
                    for candidate in assertions.records
                    if candidate.id == assertion.supersedes
                ),
                None,
            )
            if (
                predecessor is None
                or predecessor.id == assertion.id
                or predecessor.subject_ref != assertion.subject_ref
                or predecessor.predicate != assertion.predicate
            ):
                raise PackageIntegrityError("assertion successor lineage is invalid")

    assertion_successors = [
        assertion.supersedes
        for assertion in assertions.records
        if assertion.supersedes is not None
    ]
    if len(assertion_successors) != len(set(assertion_successors)):
        raise PackageIntegrityError("assertion has multiple direct successors")
    _validate_acyclic_lineage(
        {
            assertion.id: assertion.supersedes
            for assertion in assertions.records
            if assertion.supersedes is not None
        },
        description="assertion successor",
    )

    source_records: dict[str, bytes] = {}
    source_imports: dict[str, SourceImportRecord] = {}
    source_evidence_records: list[SourceRecordEvidenceRecord] = []
    for record in evidence.records:
        if not isinstance(record, SourceRecordEvidenceRecord):
            continue
        source_evidence_records.append(record)
        expected_path = f"evidence/records/{record.id}.json"
        if record.record_path != expected_path:
            raise PackageIntegrityError(
                "source evidence record_path does not match its id"
            )
        payload = snapshot.evidence_records.get(record.record_path)
        if payload is None:
            raise PackageIntegrityError("source evidence record does not resolve")
        checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
        if checksum != record.source.record_checksum:
            raise PackageIntegrityError("source evidence checksum does not match")
        source_record = SourceImportRecord.model_validate_json(payload, strict=True)
        if (
            source_record.source_id != record.source.source_id
            or source_record.record_id != record.source.record_id
        ):
            raise PackageIntegrityError("source evidence identity does not match")
        source_records[record.record_path] = payload
        source_imports[record.id] = source_record
        if record.supersedes is not None:
            evidence_predecessor = evidence_by_id.get(record.supersedes)
            if (
                not isinstance(evidence_predecessor, SourceRecordEvidenceRecord)
                or evidence_predecessor.id == record.id
                or evidence_predecessor.source.adapter_id != record.source.adapter_id
                or evidence_predecessor.source.source_id != record.source.source_id
                or evidence_predecessor.source.record_id != record.source.record_id
            ):
                raise PackageIntegrityError(
                    "source evidence successor lineage is invalid"
                )

    if require_journal_tip and set(snapshot.evidence_records) != set(source_records):
        raise PackageIntegrityError(
            "raw evidence records must exactly match canonical evidence"
        )

    evidence_successors = [
        record.supersedes
        for record in evidence.records
        if isinstance(record, SourceRecordEvidenceRecord)
        and record.supersedes is not None
    ]
    if len(evidence_successors) != len(set(evidence_successors)):
        raise PackageIntegrityError("source evidence has multiple direct successors")
    _validate_acyclic_lineage(
        {
            record.id: record.supersedes
            for record in evidence.records
            if isinstance(record, SourceRecordEvidenceRecord)
            and record.supersedes is not None
        },
        description="source evidence successor",
    )

    source_groups: dict[tuple[str, str, str], list[SourceRecordEvidenceRecord]] = {}
    for record in source_evidence_records:
        identity = (
            record.source.adapter_id,
            record.source.source_id,
            record.source.record_id,
        )
        source_groups.setdefault(identity, []).append(record)

    for source_lineage in source_groups.values():
        if sum(record.supersedes is None for record in source_lineage) != 1:
            raise PackageIntegrityError("source identity must have one lineage root")
        transaction_ids: set[str] = set()
        projections: dict[str, dict[str, AssertionRecord]] = {}
        for record in source_lineage:
            source_import = source_imports[record.id]
            source_observations = tuple(
                assertion
                for assertion in assertions.records
                if assertion.knowledge_type == "observed"
                and any(ref.id == record.id for ref in assertion.provenance)
            )
            if any(
                len(assertion.provenance) != 1
                or assertion.provenance[0].ref_type != "evidence"
                for assertion in source_observations
            ):
                raise PackageIntegrityError(
                    "source observations must have literal provenance"
                )
            projected = source_observations
            by_predicate = {assertion.predicate: assertion for assertion in projected}
            expected_values = {
                "domain.accounts/posting": ("source_account", source_import.source_id),
                "domain.cashflow/booking_date": (
                    "date",
                    source_import.booking_date.isoformat(),
                ),
                "domain.cashflow/money": (
                    "money",
                    source_import.money.model_dump(mode="json"),
                ),
                "domain.cashflow/description": ("text", source_import.description),
            }
            if len(projected) != 4 or set(by_predicate) != set(expected_values):
                raise PackageIntegrityError(
                    "source evidence must have four literal assertions"
                )
            transaction_id = projected[0].subject_ref.id
            if entity_by_id[transaction_id].entity_type != "transaction":
                raise PackageIntegrityError(
                    "source evidence subject must be a transaction"
                )
            transaction_ids.add(transaction_id)
            expected_end = source_import.booking_date + timedelta(days=1)
            for predicate, (value_type, value) in expected_values.items():
                assertion = by_predicate[predicate]
                if (
                    assertion.subject_ref.id != transaction_id
                    or assertion.object_value is None
                    or assertion.object_value.value_type != value_type
                    or assertion.object_value.value != value
                    or assertion.valid_time.start != source_import.booking_date
                    or assertion.valid_time.end_exclusive != expected_end
                    or assertion.recorded_at != record.recorded_at
                    or assertion.module_data
                ):
                    raise PackageIntegrityError(
                        "source assertion does not match its literal record"
                    )
            projections[record.id] = by_predicate

            classification_proposals = tuple(
                proposal
                for proposal in proposals.records
                if proposal.producer.producer_type == "source_adapter"
                and proposal.proposed_assertion.predicate
                == "domain.cashflow/source_classification"
                and any(ref.id == record.id for ref in proposal.evidence_refs)
            )
            classification = source_import.source_classification
            if classification is None:
                if classification_proposals:
                    raise PackageIntegrityError(
                        "source classification has no literal basis"
                    )
            elif len(classification_proposals) != 1:
                raise PackageIntegrityError(
                    "source classification must remain one proposal"
                )
            else:
                proposal = classification_proposals[0]
                proposed = proposal.proposed_assertion
                if (
                    proposal.producer.producer_id != record.source.adapter_id
                    or proposal.producer.producer_version
                    != record.source.adapter_version
                    or len(proposal.evidence_refs) != 1
                    or proposed.subject_ref.id != transaction_id
                    or proposed.object_value is None
                    or proposed.object_value.value_type != "source_classification"
                    or proposed.object_value.value
                    != classification.model_dump(mode="json")
                    or proposed.valid_time.start != source_import.booking_date
                    or proposed.valid_time.end_exclusive != expected_end
                    or proposed.module_data
                ):
                    raise PackageIntegrityError(
                        "source classification proposal does not match its record"
                    )

        if len(transaction_ids) != 1:
            raise PackageIntegrityError(
                "source identity must resolve to one transaction"
            )
        for record in source_lineage:
            if record.supersedes is None:
                continue
            predecessor_projection = projections[record.supersedes]
            if any(
                assertion.supersedes != predecessor_projection[predicate].id
                for predicate, assertion in projections[record.id].items()
            ):
                raise PackageIntegrityError(
                    "source assertion lineage does not match evidence lineage"
                )

    for proposal in proposals.records:
        if proposal.proposed_assertion.subject_ref.ref_type != "entity":
            raise PackageIntegrityError("proposal subject has an invalid ref type")
        if proposal.proposed_assertion.subject_ref.id not in entity_ids:
            raise PackageIntegrityError("proposal subject does not resolve")
        object_ref = proposal.proposed_assertion.object_ref
        if object_ref is not None and (
            object_ref.ref_type != "entity" or object_ref.id not in entity_ids
        ):
            raise PackageIntegrityError("proposal object does not resolve")
        if any(
            ref.ref_type != "evidence" or ref.id not in evidence_ids
            for ref in proposal.evidence_refs
        ):
            raise PackageIntegrityError("proposal evidence does not resolve")

    entities_by_type: dict[str, list[EntityRecord]] = {}
    for entity in entities.records:
        entities_by_type.setdefault(entity.entity_type, []).append(entity)
        expected_module = {
            "context": "topo.core",
            "person": "domain.parties",
            "household": "domain.parties",
            "account": "domain.accounts",
            "transaction": "domain.cashflow",
        }[entity.entity_type]
        if entity.module_id != expected_module:
            raise PackageIntegrityError("entity type has an invalid owning module")
    for entity_type in ("context", "person", "household"):
        if len(entities_by_type.get(entity_type, [])) != 1:
            raise PackageIntegrityError(
                f"initial generation must contain one {entity_type} entity"
            )

    context = entities_by_type["context"][0]
    person = entities_by_type["person"][0]
    household = entities_by_type["household"][0]
    memberships = [
        assertion
        for assertion in assertions.records
        if assertion.predicate == "domain.parties/household_membership"
    ]
    if len(memberships) != 1:
        raise PackageIntegrityError(
            "initial generation must contain one household membership"
        )
    membership = memberships[0]
    if (
        membership.subject_ref.id != person.id
        or membership.object_ref is None
        or membership.object_ref.id != household.id
    ):
        raise PackageIntegrityError(
            "household membership does not join the initial actors"
        )
    if context.id != manifest.context_id:
        raise PackageIntegrityError("context entity does not match the manifest")

    if not journal.entries or journal.entries[0].operation != "context.init":
        raise PackageIntegrityError("journal must start with context.init")
    matching_entries = tuple(
        entry
        for entry in journal.entries
        if entry.generation_after == manifest.generation_id
    )
    if len(matching_entries) != 1:
        raise PackageIntegrityError("generation must occur exactly once in the journal")
    entry = matching_entries[0]
    if require_journal_tip and entry != journal.entries[-1]:
        raise PackageIntegrityError("journal generation does not match the manifest")
    if entry.mutation_id != manifest.mutation_id:
        raise PackageIntegrityError("journal mutation does not match the manifest")
    if entry.generation_before != manifest.based_on:
        raise PackageIntegrityError("journal lineage does not match the manifest")

    result = ContextInitResult(
        context_id=context.id,
        generation_id=manifest.generation_id,
        mutation_id=manifest.mutation_id,
        person_id=person.id,
        household_id=household.id,
        membership_assertion_id=membership.id,
    )
    return ValidatedPackage(
        manifest=manifest,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
        proposals=proposals,
        journal=journal,
        source_records=source_records,
        initialization_result=result,
    )


def load_and_validate_generation(
    snapshot: StoredPackageSnapshot,
) -> ValidatedPackage:
    """Turn untrusted package bytes into a completely validated initial package."""
    try:
        current = _validate_snapshot(snapshot)
        retained = snapshot.retained_generation_files
        if retained is not None:
            expected_retained = {
                entry.generation_after
                for entry in current.journal.entries
                if entry.generation_after != snapshot.current_generation
            }
            if set(retained) != expected_retained:
                raise PackageIntegrityError(
                    "retained generations do not match the journal"
                )
            for generation_id, generation_files in retained.items():
                _validate_snapshot(
                    StoredPackageSnapshot(
                        current_generation=generation_id,
                        generation_files=generation_files,
                        journal=snapshot.journal,
                        evidence_records=snapshot.evidence_records,
                    ),
                    require_journal_tip=False,
                )
        return current
    except PackageIntegrityError:
        raise
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValidationError,
        PydanticValidationError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise PackageIntegrityError(str(error)) from error
