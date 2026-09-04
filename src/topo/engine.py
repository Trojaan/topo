from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, JsonValue

from topo.builtin_modules import default_module_catalog
from topo.canonical_validation import ValidatedPackage, load_and_validate_generation
from topo.context_inventory import inventory_context, next_workflow_action
from topo.errors import (
    ContextAlreadyExistsError,
    ExplanationReferenceError,
    PackageIntegrityError,
    ProposalDecisionError,
)
from topo.explanations import (
    decode_explanation,
    explain_decision,
    explain_proposal,
    index_analysis,
    index_rule_preview,
)
from topo.identifiers import source_account_id, uuid7
from topo.models import (
    Actor,
    AnalyzeRunRequest,
    AssertionRecord,
    Authorization,
    CanonicalCollection,
    ContextInitRequest,
    ContextMigrateRequest,
    ContextPrivacyScrubRequest,
    ContextRestoreRequest,
    ContextRetentionRequest,
    ContextStatusResult,
    ContextVerifyResult,
    DiscoveryOutcome,
    DiscoveryRequest,
    EntityRecord,
    EvidenceRecord,
    InitializationOutcome,
    Journal,
    JournalEntry,
    JsonObject,
    Manifest,
    ModulePin,
    MutationOutcome,
    MutationRequest,
    ObjectValue,
    Producer,
    ProposalBatchConfirmRequest,
    ProposalBatchRejectRequest,
    ProposalConfirmRequest,
    ProposalCorrectRequest,
    ProposalDecision,
    ProposalRecord,
    ProposalRejectRequest,
    ProposalSubmitRequest,
    ProposedAssertion,
    ProposedEntity,
    Ref,
    RuleActivateRequest,
    RulePackagePin,
    RulePackageRequest,
    ScenarioAnalyzeRunRequest,
    SourceImportRecord,
    SourceImportRequest,
    SourceRecordEvidenceRecord,
    SourceReference,
    UserStatementEvidenceRecord,
    ValidTime,
    WorkflowContextItem,
    WorkflowNextRequest,
    WorkflowProposalResponse,
    WorkflowRespondRequest,
    model_to_json_object,
)
from topo.modules import ModuleCatalog
from topo.net_worth import analyze_net_worth
from topo.normalized_cashflow import analyze_normalized_monthly_cashflow
from topo.realized_cashflow import analyze_realized_monthly_cashflow
from topo.recognition import TransactionObservation, recognize_recurring_cashflows
from topo.rules import (
    DeclarativeRulePackage,
    RulePackageError,
    canonical_rule_package_bytes,
    default_rule_registry,
    package_checksum,
    parse_rule_package,
    preview_ref,
    preview_traces,
    validate_rule_package,
)
from topo.scenario import analyze_scenario_comparison
from topo.storage import (
    CurrentStorage,
    ExplanationStorage,
    PackageCommit,
    PrivacyStorage,
    RetentionStorage,
    StorageAdapter,
    StoredPackageSnapshot,
)

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


def _json_bytes(value: BaseModel) -> bytes:
    payload: object = value.model_dump(mode="json")

    def omit_absent_assertion_object(item: object) -> object:
        if isinstance(item, dict):
            return {
                key: omit_absent_assertion_object(child)
                for key, child in item.items()
                if not (key in {"object_ref", "object_value"} and child is None)
            }
        if isinstance(item, list):
            return [omit_absent_assertion_object(child) for child in item]
        return item

    payload = omit_absent_assertion_object(payload)
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _evidence_inventory_bytes(paths: tuple[str, ...]) -> bytes:
    return (
        json.dumps(
            {"paths": sorted(paths)}, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
    ).encode("utf-8")


class EngineCore:
    """Own generation, validation, history, and replay semantics."""

    def __init__(
        self,
        storage: StorageAdapter,
        *,
        clock: Clock | None = None,
        id_factory: IdFactory = uuid7,
        module_catalog: ModuleCatalog | None = None,
    ) -> None:
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory
        self._module_catalog = module_catalog or default_module_catalog()

    def initialize(self, request: ContextInitRequest) -> InitializationOutcome:
        try:
            snapshot = self._storage.load()
        except OSError as error:
            raise PackageIntegrityError(str(error)) from error

        if snapshot is not None:
            validated = load_and_validate_generation(snapshot)
            entry = validated.journal.entries[0]
            if entry.operation_id != request.operation_id:
                raise ContextAlreadyExistsError(request.package)
            return InitializationOutcome(
                result=validated.initialization_result,
                replayed=True,
            )

        publication = self._build_initial_publication(request)
        validated = load_and_validate_generation(
            StoredPackageSnapshot(
                current_generation=publication.generation_id,
                generation_files=publication.generation_files,
                journal=publication.journal,
            )
        )
        self._storage.commit(publication, expected_generation=None)
        return InitializationOutcome(
            result=validated.initialization_result,
            replayed=False,
        )

    def analyze(self, request: AnalyzeRunRequest) -> JsonObject:
        validated = self._load_existing()
        if request.analysis_id == "analysis.context_inventory":
            result = inventory_context(validated, request)
        elif request.analysis_id == "analysis.realized_monthly_cashflow":
            result = analyze_realized_monthly_cashflow(validated, request)
        elif request.analysis_id == "analysis.normalized_monthly_cashflow":
            result = analyze_normalized_monthly_cashflow(validated, request)
        elif isinstance(request, ScenarioAnalyzeRunRequest):
            result = analyze_scenario_comparison(validated, request)
        else:
            result = analyze_net_worth(validated, request)
        indexed, explanations = index_analysis(validated, result)
        if isinstance(self._storage, ExplanationStorage):
            self._storage.store_explanations(explanations)
        return indexed

    def workflow_next(self, request: WorkflowNextRequest) -> tuple[JsonObject, str]:
        validated = self._load_existing()
        return (
            next_workflow_action(validated, request),
            validated.manifest.generation_id,
        )

    def explain(self, ref: str) -> JsonObject:
        validated = self._load_existing()
        ref_type, separator, ref_id = ref.partition(":")
        if not separator or not ref_id:
            raise ExplanationReferenceError(
                "EXPLAIN_REFERENCE_UNKNOWN", ref, "reference has no supported type"
            )
        if ref_type == "proposal":
            proposal = next(
                (item for item in validated.proposals.records if item.id == ref_id),
                None,
            )
            if proposal is not None:
                return explain_proposal(validated, proposal)
        if ref_type == "decision":
            proposal = next(
                (
                    item
                    for item in validated.proposals.records
                    if item.decision is not None and item.decision.mutation_id == ref_id
                ),
                None,
            )
            if proposal is not None:
                return explain_decision(validated, proposal)
        try:
            payload = (
                self._storage.load_explanation(ref)
                if isinstance(self._storage, ExplanationStorage)
                else None
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ExplanationReferenceError(
                "EXPLAIN_REFERENCE_UNVERIFIABLE", ref, str(error)
            ) from error
        if payload is not None:
            try:
                value = decode_explanation(payload, ref)
                generation = value.get("generation_id")
                available_generations = {
                    validated.manifest.generation_id,
                    *(entry.generation_after for entry in validated.journal.entries),
                }
                if generation not in available_generations:
                    raise ValueError("used generation is no longer verifiable")
                return value
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                raise ExplanationReferenceError(
                    "EXPLAIN_REFERENCE_UNVERIFIABLE", ref, str(error)
                ) from error
        raise ExplanationReferenceError(
            "EXPLAIN_REFERENCE_UNKNOWN", ref, "reference does not resolve"
        )

    def current_identity(self) -> tuple[str, str]:
        validated = self._load_existing()
        return validated.manifest.generation_id, validated.manifest.context_id

    def context_status(self) -> ContextStatusResult:
        validated = self._load_existing()
        initialized = validated.initialization_result
        return ContextStatusResult(
            context_id=validated.manifest.context_id,
            generation_id=validated.manifest.generation_id,
            person_id=initialized.person_id,
            household_id=initialized.household_id,
            package_version=validated.manifest.package_version,
            context_schema_version=validated.manifest.context_schema_version,
            modules=validated.manifest.modules,
        )

    def verify_context(self) -> ContextVerifyResult:
        snapshot = self._load_snapshot()
        validated = load_and_validate_generation(snapshot)
        return ContextVerifyResult(
            context_id=validated.manifest.context_id,
            generation_id=validated.manifest.generation_id,
            generations_verified=1 + len(snapshot.retained_generation_files or {}),
            evidence_records_verified=len(snapshot.evidence_records),
        )

    def migrate_context(self, request: ContextMigrateRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        if (
            request.target_package_version != "0.2"
            or request.target_context_schema_version != "topo.context/0.2"
            or request.target_module_versions
            != {pin.module_id: pin.module_version for pin in self._module_catalog.pins}
        ):
            return MutationOutcome(
                context_id=request.context_id,
                generation_before=validated.manifest.generation_id,
                generation_after=validated.manifest.generation_id,
                outcome="rejected",
                result={
                    "reason": "incompatible_target_version",
                    "supported_package_versions": ["0.2"],
                    "supported_context_schema_versions": ["topo.context/0.2"],
                    "supported_module_versions": {
                        pin.module_id: pin.module_version
                        for pin in self._module_catalog.pins
                    },
                },
            )
        migration_basis = {
            "command": "context.migrate",
            "context_id": request.context_id,
            "expected_generation": request.expected_generation,
            "target_package_version": request.target_package_version,
            "target_context_schema_version": request.target_context_schema_version,
            "target_module_versions": request.target_module_versions,
        }
        migration_digest = hashlib.sha256(
            json.dumps(migration_basis, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        preview: JsonObject = {
            "preview_ref": f"preview:sha256:{migration_digest}",
            "effects": [
                {
                    "action": "publish_migrated_generation",
                    "from_context_schema": validated.manifest.context_schema_version,
                    "to_context_schema": request.target_context_schema_version,
                }
            ],
        }
        if request.authorization is None:
            return self._authorization_required(request, preview)
        self._validate_authorization(request.authorization, preview)
        now = self._now()
        generation_id = self._id_factory()
        result: JsonObject = {
            "package_version": request.target_package_version,
            "context_schema_version": request.target_context_schema_version,
            "module_versions": {
                pin.module_id: pin.module_version for pin in self._module_catalog.pins
            },
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="context.migrate",
            mutation_id=self._id_factory(),
            generation_id=generation_id,
            result=result,
            now=now,
            modules=self._module_catalog.pins,
            package_version="0.2",
            context_schema_version="topo.context/0.2",
        )
        self._commit_update(publication, validated.manifest.generation_id)
        return self._success(request, generation_id, result)

    def restore_context(self, request: ContextRestoreRequest) -> MutationOutcome:
        snapshot = self._load_snapshot()
        validated = load_and_validate_generation(snapshot)
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        target_files: dict[str, bytes] | None
        if request.restore_generation == snapshot.current_generation:
            target_files = snapshot.generation_files
        else:
            retained = snapshot.retained_generation_files or {}
            target_files = retained.get(request.restore_generation)
        if target_files is None:
            raise ValueError("restore_generation is not retained")
        target_index = next(
            (
                index
                for index, entry in enumerate(validated.journal.entries)
                if entry.generation_after == request.restore_generation
            ),
            None,
        )
        if target_index is None:
            raise PackageIntegrityError("restore generation has no mutation history")
        target_journal = validated.journal.model_copy(
            update={"entries": validated.journal.entries[: target_index + 1]}
        )
        target = load_and_validate_generation(
            StoredPackageSnapshot(
                current_generation=request.restore_generation,
                generation_files=target_files,
                journal=_json_bytes(target_journal),
                evidence_records=self._generation_evidence_records(
                    target_files, snapshot.evidence_records
                ),
            )
        )
        now = self._now()
        generation_id = self._id_factory()
        result: JsonObject = {"restored_from_generation": request.restore_generation}
        publication = self._build_update_publication(
            target,
            request=request,
            operation="context.restore",
            mutation_id=self._id_factory(),
            generation_id=generation_id,
            result=result,
            now=now,
            based_on=validated.manifest.generation_id,
            journal_entries=validated.journal.entries,
        )
        self._commit_update(publication, validated.manifest.generation_id)
        return self._success(request, generation_id, result)

    def apply_retention(self, request: ContextRetentionRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        if not isinstance(self._storage, RetentionStorage):
            raise TypeError("storage adapter does not support retention")
        known_generations = tuple(
            entry.generation_after for entry in validated.journal.entries
        )
        unknown = set(request.restore_generations) - set(known_generations)
        if unknown:
            raise ValueError("restore_generations contains an unknown generation")
        generation_id = self._id_factory()
        ordered_with_new = (*known_generations, generation_id)
        keep = {
            *ordered_with_new[-request.retain_latest :],
            *request.restore_generations,
        }
        removed = tuple(
            generation for generation in known_generations if generation not in keep
        )
        result: JsonObject = {
            "retain_latest": request.retain_latest,
            "restore_generations": list(request.restore_generations),
            "removed_generations": list(removed),
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="context.compact",
            mutation_id=self._id_factory(),
            generation_id=generation_id,
            result=result,
            now=self._now(),
        )
        self._commit_update(publication, validated.manifest.generation_id)
        self._storage.apply_retention(expected_generation=generation_id)
        return self._success(request, generation_id, result)

    def scrub_privacy(self, request: ContextPrivacyScrubRequest) -> MutationOutcome:
        snapshot = self._load_snapshot()
        validated = load_and_validate_generation(snapshot)
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        if not isinstance(self._storage, PrivacyStorage):
            raise TypeError("storage adapter does not support privacy scrub")
        requested_ids = set(request.evidence_ids)
        all_generation_files = {
            snapshot.current_generation: snapshot.generation_files,
            **(snapshot.retained_generation_files or {}),
        }
        present_ids = {
            str(record["id"])
            for files in all_generation_files.values()
            for record in cast(
                list[JsonObject],
                cast(
                    JsonObject,
                    json.loads(files["evidence.json"].decode("utf-8")),
                )["records"],
            )
        }
        if not requested_ids & present_ids:
            return MutationOutcome(
                context_id=request.context_id,
                generation_before=validated.manifest.generation_id,
                generation_after=validated.manifest.generation_id,
                outcome="no_change",
                result={"scrubbed_evidence_count": 0},
            )

        scrubbed_current = self._privacy_scrubbed_package(validated, requested_ids)
        generation_id = self._id_factory()
        result: JsonObject = {
            "scrubbed_evidence_count": len(requested_ids & present_ids),
            "remaining_assertions_marked_unverifiable": sum(
                assertion.verification_status == "unverifiable"
                for assertion in scrubbed_current.assertions.records
            ),
        }
        publication = self._build_update_publication(
            scrubbed_current,
            request=request,
            operation="context.privacy_scrub",
            mutation_id=self._id_factory(),
            generation_id=generation_id,
            result=result,
            now=self._now(),
            based_on=validated.manifest.generation_id,
            journal_entries=validated.journal.entries,
        )
        self._commit_update(publication, validated.manifest.generation_id)

        scrub_snapshot = self._load_snapshot()
        scrub_current = load_and_validate_generation(scrub_snapshot)
        rewritten_generations: dict[str, dict[str, bytes]] = {}
        inventories: dict[str, bytes] = {}
        all_files_after = {
            scrub_snapshot.current_generation: scrub_snapshot.generation_files,
            **(scrub_snapshot.retained_generation_files or {}),
        }
        for retained_id, files in all_files_after.items():
            entry_index = next(
                index
                for index, entry in enumerate(scrub_current.journal.entries)
                if entry.generation_after == retained_id
            )
            retained_journal = scrub_current.journal.model_copy(
                update={"entries": scrub_current.journal.entries[: entry_index + 1]}
            )
            retained = load_and_validate_generation(
                StoredPackageSnapshot(
                    current_generation=retained_id,
                    generation_files=files,
                    journal=_json_bytes(retained_journal),
                    evidence_records=self._generation_evidence_records(
                        files, scrub_snapshot.evidence_records
                    ),
                )
            )
            scrubbed = self._privacy_scrubbed_package(retained, requested_ids)
            rewritten_generations[retained_id] = self._generation_files(scrubbed)
            inventories[retained_id] = _evidence_inventory_bytes(
                tuple(scrubbed.source_records)
            )

        journal_value = self._scrub_json(
            model_to_json_object(scrub_current.journal), requested_ids
        )
        scrubbed_journal = Journal.model_validate_json(
            json.dumps(journal_value), strict=True
        )
        remaining_records = {
            path: payload
            for path, payload in scrub_snapshot.evidence_records.items()
            if Path(path).stem not in requested_ids
        }
        self._storage.apply_privacy_scrub(
            expected_generation=generation_id,
            generation_files=rewritten_generations,
            journal=_json_bytes(scrubbed_journal),
            evidence_records=remaining_records,
            evidence_inventories=inventories,
        )
        self._load_full_existing()
        return self._success(request, generation_id, result)

    @staticmethod
    def _scrub_json(value: JsonValue, targets: set[str]) -> JsonValue:
        if isinstance(value, str):
            result = value
            for target in targets:
                result = result.replace(target, "[privacy-scrubbed]")
            return result
        if isinstance(value, list):
            return [EngineCore._scrub_json(item, targets) for item in value]
        if isinstance(value, dict):
            return {
                key: EngineCore._scrub_json(item, targets)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _privacy_scrubbed_package(
        validated: ValidatedPackage, requested_ids: set[str]
    ) -> ValidatedPackage:
        removed_evidence = set(requested_ids)
        changed = True
        while changed:
            changed = False
            for record in validated.evidence.records:
                if (
                    isinstance(record, SourceRecordEvidenceRecord)
                    and record.supersedes in removed_evidence
                    and record.id not in removed_evidence
                ):
                    removed_evidence.add(record.id)
                    changed = True
        proposals = tuple(
            proposal
            for proposal in validated.proposals.records
            if not any(ref.id in removed_evidence for ref in proposal.evidence_refs)
        )
        removed_proposals = {
            proposal.id
            for proposal in validated.proposals.records
            if proposal not in proposals
        }
        assertions: list[AssertionRecord] = []
        for assertion in validated.assertions.records:
            provenance = tuple(
                ref
                for ref in assertion.provenance
                if not (
                    (ref.ref_type == "evidence" and ref.id in removed_evidence)
                    or (ref.ref_type == "proposal" and ref.id in removed_proposals)
                )
            )
            assertions.append(
                assertion
                if provenance == assertion.provenance
                else assertion.model_copy(
                    update={
                        "provenance": provenance,
                        "verification_status": "unverifiable",
                    }
                )
            )
        evidence = tuple(
            record
            for record in validated.evidence.records
            if record.id not in removed_evidence
        )
        source_records = {
            path: payload
            for path, payload in validated.source_records.items()
            if Path(path).stem not in removed_evidence
        }
        return replace(
            validated,
            assertions=CanonicalCollection[AssertionRecord](
                schema_version=validated.assertions.schema_version,
                records=tuple(assertions),
            ),
            evidence=CanonicalCollection[EvidenceRecord](
                schema_version=validated.evidence.schema_version,
                records=evidence,
            ),
            proposals=CanonicalCollection[ProposalRecord](
                schema_version=validated.proposals.schema_version,
                records=proposals,
            ),
            source_records=source_records,
        )

    @staticmethod
    def _generation_files(validated: ValidatedPackage) -> dict[str, bytes]:
        collections = {
            "entities.json": _json_bytes(validated.entities),
            "assertions.json": _json_bytes(validated.assertions),
            "evidence.json": _json_bytes(validated.evidence),
            "proposals.json": _json_bytes(validated.proposals),
        }
        payloads = {**collections, **validated.rule_package_files}
        checksums = {
            filename: "sha256:" + hashlib.sha256(payload).hexdigest()
            for filename, payload in payloads.items()
        }
        manifest = validated.manifest.model_copy(update={"files": checksums})
        return {**payloads, "manifest.json": _json_bytes(manifest)}

    @staticmethod
    def _generation_evidence_records(
        generation_files: dict[str, bytes], available: dict[str, bytes]
    ) -> dict[str, bytes]:
        evidence = cast(
            JsonObject,
            json.loads(generation_files["evidence.json"].decode("utf-8")),
        )
        paths = {
            str(record["record_path"])
            for record in cast(list[JsonObject], evidence["records"])
            if record.get("evidence_type") == "source_record"
        }
        return {path: available[path] for path in paths if path in available}

    def validate_rules(self, request: RulePackageRequest) -> JsonObject:
        validated = self._load_existing()
        self._guard_rule_read(validated.manifest, request)
        package = self._validated_rule_package(validated, request.rule_package_yaml)
        return self._rule_validation_result(validated, package)

    @staticmethod
    def _rule_validation_result(
        validated: ValidatedPackage, package: DeclarativeRulePackage
    ) -> JsonObject:
        return {
            "valid": True,
            "validated_generation": validated.manifest.generation_id,
            "package_id": package.package_id,
            "package_version": package.package_version,
            "module_id": package.module_id,
            "checksum": package_checksum(package),
            "rule_count": len(package.rules),
            "rule_types": cast(
                list[JsonValue], sorted({rule.rule_type for rule in package.rules})
            ),
        }

    def preview_rules(self, request: RulePackageRequest) -> JsonObject:
        validated = self._load_existing()
        self._guard_rule_read(validated.manifest, request)
        package = self._validated_rule_package(validated, request.rule_package_yaml)
        result: JsonObject = {
            **self._rule_validation_result(validated, package),
            "preview_ref": preview_ref(package, validated.manifest.generation_id),
            "effects": [
                {
                    "action": "replace_rule_package",
                    "module_id": package.module_id,
                    "package_id": package.package_id,
                    "package_version": package.package_version,
                }
            ],
            "evaluations": preview_traces(package),
        }
        indexed, explanations = index_rule_preview(validated, result)
        if isinstance(self._storage, ExplanationStorage):
            self._storage.store_explanations(explanations)
        return indexed

    def activate_rules(self, request: RuleActivateRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        package = self._validated_rule_package(validated, request.rule_package_yaml)
        preview: JsonObject = {
            "preview_ref": preview_ref(package, validated.manifest.generation_id),
            "effects": [
                {
                    "action": "replace_rule_package",
                    "module_id": package.module_id,
                    "package_id": package.package_id,
                    "package_version": package.package_version,
                }
            ],
        }
        if request.authorization is None:
            return self._authorization_required(request, preview)
        if request.authorization.preview_ref != preview["preview_ref"]:
            raise RulePackageError(
                "INVALID_AUTHORIZATION",
                "/authorization/preview_ref",
                "authorization does not match this rule package preview",
            )
        if request.authorization.authorized_by.actor_type != "human":
            raise RulePackageError(
                "INVALID_AUTHORIZATION",
                "/authorization/authorized_by/actor_type",
                "rule package activation must be authorized by a human",
            )
        now = self._now()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        artifact = f"rule-package.{package.module_id}.json"
        package_bytes = canonical_rule_package_bytes(package)
        checksum = package_checksum(package)
        pin = RulePackagePin(
            package_id=package.package_id,
            package_version=package.package_version,
            module_id=package.module_id,
            module_version=package.module_version,
            checksum=checksum,
            artifact=artifact,
        )
        active_pins = tuple(
            sorted(
                (
                    *(
                        candidate
                        for candidate in validated.manifest.active_rule_packages
                        if candidate.module_id != package.module_id
                    ),
                    pin,
                ),
                key=lambda candidate: candidate.module_id,
            )
        )
        active_files = {
            name: payload
            for name, payload in validated.rule_package_files.items()
            if name != artifact
        }
        active_files[artifact] = package_bytes
        result: JsonObject = {
            "package_id": package.package_id,
            "package_version": package.package_version,
            "module_id": package.module_id,
            "checksum": checksum,
            "rule_count": len(package.rules),
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="rule.activate",
            mutation_id=mutation_id,
            generation_id=generation_id,
            result=result,
            now=now,
            active_rule_packages=active_pins,
            rule_package_files=active_files,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def submit_proposal(self, request: ProposalSubmitRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        if request.workflow_response is not None:
            return self._submit_workflow_response(
                validated, request, request.workflow_response
            )
        assert request.proposal is not None
        self._module_catalog.validate_proposed_assertion(
            request.proposal.proposed_assertion,
            validated.manifest.modules,
            validated.assertions.records,
            validated.entities.records,
        )
        now = self._now()
        proposal_id = self._id_factory()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        proposal = ProposalRecord(
            id=proposal_id,
            **request.proposal.model_dump(),
            status="open",
            created_at=now,
            decision=None,
        )
        result: JsonObject = {"proposal_id": proposal_id}
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="proposal.submit",
            mutation_id=mutation_id,
            generation_id=generation_id,
            proposals=(*validated.proposals.records, proposal),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def respond_to_workflow(self, request: WorkflowRespondRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        if validated.manifest.context_schema_version != "topo.context/0.2":
            raise ProposalDecisionError(
                "CONTEXT_MIGRATION_REQUIRED",
                "/expected_generation",
                "workflow responses require topo.context/0.2",
            )
        response = request.workflow_response
        workflow_request = WorkflowNextRequest(
            contract_version=request.contract_version,
            context_id=request.context_id,
            analysis_scope=response.analysis_scope,
            as_of_date=response.as_of_date,
            include_basis_context=True,
        )
        current = next_workflow_action(validated, workflow_request)
        action = cast(JsonObject | None, current.get("next_action"))
        if action is None or action.get("action_id") != response.action_id:
            raise ProposalDecisionError(
                "WORKFLOW_ACTION_NOT_CURRENT",
                "/workflow_response/action_id",
                "action_id does not identify the current workflow action",
            )
        if action.get("command") != "workflow.respond":
            raise ProposalDecisionError(
                "WORKFLOW_RESPONSE_UNSUPPORTED",
                "/workflow_response/response_type",
                "the current workflow action does not accept a context inventory",
            )

        section_modules = {
            "household": "domain.parties",
            "accounts": "domain.accounts",
            "cashflow": "domain.cashflow",
            "assets": "domain.assets",
            "debts": "domain.debts",
            "pensions": "domain.pensions",
            "contracts_insurance": "domain.contracts",
            "goals": "domain.goals",
        }
        entity_modules: dict[
            str,
            Literal[
                "domain.parties",
                "domain.accounts",
                "domain.assets",
                "domain.debts",
                "domain.contracts",
                "domain.pensions",
                "domain.goals",
            ],
        ] = {
            "person": "domain.parties",
            "account": "domain.accounts",
            "asset": "domain.assets",
            "debt": "domain.debts",
            "contract": "domain.contracts",
            "pension_entitlement": "domain.pensions",
            "goal": "domain.goals",
        }
        expected_module = section_modules[response.section_id]
        now = self._now()
        batch_id = self._id_factory()
        evidence_id = self._id_factory()
        existing_entities = {entity.id: entity for entity in validated.entities.records}
        proposed_entities: list[ProposedEntity] = []
        assertions: list[ProposedAssertion] = []

        def add_assertion(
            subject_id: str,
            predicate: str,
            *,
            object_ref: Ref | None = None,
            object_value: ObjectValue | None = None,
            end_exclusive: date | None = None,
            module_data: JsonObject | None = None,
        ) -> None:
            assertions.append(
                ProposedAssertion(
                    subject_ref=Ref(ref_type="entity", id=subject_id),
                    predicate=predicate,
                    object_ref=object_ref,
                    object_value=object_value,
                    valid_time=ValidTime(
                        start=response.as_of_date, end_exclusive=end_exclusive
                    ),
                    knowledge_type="user_provided",
                    module_data=module_data or {},
                )
            )

        item_entity_ids: list[str] = []
        for item in response.items:
            if item.entity_type == "recurring_cashflow":
                self._append_recurring_workflow_assertion(
                    assertions,
                    item,
                    response.analysis_scope.entity_id,
                    response.as_of_date,
                )
                continue
            module_id = entity_modules[item.entity_type]
            if module_id != expected_module:
                raise ProposalDecisionError(
                    "WORKFLOW_ITEM_WRONG_SECTION",
                    "/workflow_response/items",
                    "item entity type does not belong to the selected section",
                )
            entity_id = (
                item.entity_ref.id if item.entity_ref is not None else item.item_id
            )
            if item.entity_ref is not None:
                entity = existing_entities.get(entity_id)
                if (
                    item.entity_ref.ref_type != "entity"
                    or entity is None
                    or entity.entity_type != item.entity_type
                ):
                    raise ProposalDecisionError(
                        "WORKFLOW_ENTITY_NOT_FOUND",
                        "/workflow_response/items",
                        "entity_ref does not resolve to the declared item type",
                    )
            else:
                if entity_id in existing_entities or any(
                    entity.id == entity_id for entity in proposed_entities
                ):
                    raise ProposalDecisionError(
                        "WORKFLOW_ENTITY_ID_CONFLICT",
                        "/workflow_response/items",
                        "new workflow item id is not unique",
                    )
                proposed_entities.append(
                    ProposedEntity(
                        id=entity_id,
                        entity_type=item.entity_type,
                        module_id=module_id,
                    )
                )
            item_entity_ids.append(entity_id)
            add_assertion(
                entity_id,
                "topo.core/label",
                object_value=ObjectValue(value_type="text", value=item.label),
            )
            if item.classification is not None:
                classification = item.classification
                if "/" not in classification:
                    classification = f"{module_id}/classification/{classification}"
                add_assertion(
                    entity_id,
                    classification,
                    object_value=ObjectValue(value_type="boolean", value=True),
                )
            value_contract = {
                "account": ("domain.accounts/balance", "account_balance"),
                "asset": ("domain.assets/value", "asset_value"),
                "debt": ("domain.debts/balance", "debt_balance"),
                "pension_entitlement": ("domain.pensions/value", "pension_value"),
            }.get(item.entity_type)
            if item.money is not None and value_contract is not None:
                predicate, basis = value_contract
                add_assertion(
                    entity_id,
                    predicate,
                    object_value=ObjectValue(
                        value_type="money", value=item.money.model_dump(mode="json")
                    ),
                    end_exclusive=response.as_of_date + timedelta(days=1),
                    module_data={
                        "economic_interest_ref": f"{item.entity_type}:{entity_id}",
                        "valuation_basis": basis,
                    },
                )
            if item.entity_type == "goal":
                add_assertion(
                    entity_id,
                    "domain.goals/definition",
                    object_value=ObjectValue(
                        value_type="goal_definition",
                        value={
                            "target_date": (
                                item.target_date.isoformat()
                                if item.target_date is not None
                                else None
                            ),
                            "target_money": (
                                item.target_money.model_dump(mode="json")
                                if item.target_money is not None
                                else None
                            ),
                        },
                    ),
                )
            if item.source is not None and item.entity_type == "account":
                add_assertion(
                    entity_id,
                    "domain.accounts/external_identity",
                    object_value=ObjectValue(
                        value_type="external_identity",
                        value=item.source.model_dump(mode="json"),
                    ),
                )
            if item.household_share is not None:
                relation = (
                    "domain.parties/household_allocation"
                    if response.analysis_scope.scope_type == "household"
                    else {
                        "account": "domain.parties/account_holder",
                        "debt": "domain.parties/debtor",
                        "pension_entitlement": "domain.parties/beneficiary",
                    }.get(item.entity_type, "domain.parties/ownership")
                )
                add_assertion(
                    entity_id,
                    relation,
                    object_ref=Ref(
                        ref_type="entity", id=response.analysis_scope.entity_id
                    ),
                    module_data={
                        "distribution": {
                            "complete": item.household_share == "1",
                            "shares": [item.household_share],
                        }
                    },
                )

        coverage_predicate = {
            "household": "domain.parties/inventory_coverage",
            "accounts": "domain.accounts/inventory_coverage",
            "cashflow": "domain.cashflow/inventory_coverage",
            "assets": "domain.assets/inventory_coverage",
            "debts": "domain.debts/inventory_coverage",
            "pensions": "domain.pensions/inventory_coverage",
            "contracts_insurance": "domain.contracts/inventory_coverage",
            "goals": "domain.goals/inventory_coverage",
        }[response.section_id]
        add_assertion(
            response.analysis_scope.entity_id,
            coverage_predicate,
            object_value=ObjectValue(
                value_type="inventory_coverage",
                value={
                    "coverage": response.coverage,
                    "as_of_date": response.as_of_date.isoformat(),
                    "item_refs": [
                        {"ref_type": "entity", "id": entity_id}
                        for entity_id in item_entity_ids
                    ],
                },
            ),
            end_exclusive=response.as_of_date + timedelta(days=1),
        )

        final_entities = (
            *validated.entities.records,
            *(
                EntityRecord(
                    id=entity.id,
                    entity_type=entity.entity_type,
                    module_id=entity.module_id,
                    created_at=now,
                )
                for entity in proposed_entities
            ),
        )
        for assertion in assertions:
            self._module_catalog.validate_proposed_assertion(
                assertion,
                validated.manifest.modules,
                validated.assertions.records,
                final_entities,
            )
        evidence = UserStatementEvidenceRecord(
            id=evidence_id,
            evidence_type="user_statement",
            recorded_at=now,
            statement_type="workflow_answer",
            statement=response.model_dump(mode="json"),
        )
        records: list[ProposalRecord] = []
        proposal_ids: list[str] = []
        for proposed_entity in proposed_entities:
            proposal_id = self._id_factory()
            proposal_ids.append(proposal_id)
            records.append(
                ProposalRecord(
                    id=proposal_id,
                    proposal_type="entity",
                    producer=response.producer,
                    proposed_entity=proposed_entity,
                    batch_id=batch_id,
                    evidence_refs=(Ref(ref_type="evidence", id=evidence_id),),
                    reason_ref=f"workflow-action:{response.action_id}",
                    detection=None,
                    status="open",
                    created_at=now,
                    decision=None,
                )
            )
        for assertion in assertions:
            proposal_id = self._id_factory()
            proposal_ids.append(proposal_id)
            records.append(
                ProposalRecord(
                    id=proposal_id,
                    proposal_type="assertion",
                    producer=response.producer,
                    proposed_assertion=assertion,
                    batch_id=batch_id,
                    evidence_refs=(Ref(ref_type="evidence", id=evidence_id),),
                    reason_ref=f"workflow-action:{response.action_id}",
                    detection=None,
                    status="open",
                    created_at=now,
                    decision=None,
                )
            )
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        result: JsonObject = {
            "batch_id": batch_id,
            "proposal_ids": cast(JsonValue, proposal_ids),
            "evidence_id": evidence_id,
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="workflow.respond",
            mutation_id=mutation_id,
            generation_id=generation_id,
            evidence=(*validated.evidence.records, evidence),
            proposals=(*validated.proposals.records, *records),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    @staticmethod
    def _append_recurring_workflow_assertion(
        assertions: list[ProposedAssertion],
        item: WorkflowContextItem,
        scope_id: str,
        as_of_date: date,
    ) -> None:
        if (
            (item.money is None and item.amount_range is None)
            or item.direction is None
            or item.frequency is None
            or item.expected_period is None
        ):
            raise ProposalDecisionError(
                "WORKFLOW_CASHFLOW_INCOMPLETE",
                "/workflow_response/items",
                "recurring cashflow requires amount, direction, frequency and expected period",
            )
        assertions.append(
            ProposedAssertion(
                subject_ref=Ref(ref_type="entity", id=scope_id),
                predicate="domain.cashflow/recurring_cashflow",
                object_value=ObjectValue(
                    value_type="recurring_cashflow",
                    value={
                        "frequency": item.frequency,
                        "direction": item.direction,
                        "expected_period": item.expected_period.model_dump(mode="json"),
                        "money": (
                            item.money.model_dump(mode="json")
                            if item.money is not None
                            else None
                        ),
                        "amount_range": (
                            item.amount_range.model_dump(mode="json")
                            if item.amount_range is not None
                            else None
                        ),
                        "typical_money": (
                            item.typical_money.model_dump(mode="json")
                            if item.typical_money is not None
                            else None
                        ),
                    },
                ),
                valid_time=ValidTime(
                    start=item.valid_from or as_of_date, end_exclusive=None
                ),
                knowledge_type="user_provided",
                module_data={
                    "label": item.label,
                    "classification": item.classification,
                },
            )
        )

    def _submit_workflow_response(
        self,
        validated: ValidatedPackage,
        request: ProposalSubmitRequest,
        response: WorkflowProposalResponse,
    ) -> MutationOutcome:
        workflow_request = WorkflowNextRequest(
            contract_version=request.contract_version,
            context_id=request.context_id,
            analysis_id=response.analysis_id,
            analysis_scope=response.analysis_scope,
            as_of_date=response.as_of_date,
        )
        action_result = next_workflow_action(validated, workflow_request)
        actions = cast(list[JsonObject], action_result["actions"])
        action = next(
            (
                candidate
                for candidate in actions
                if candidate.get("action_id") == response.action_id
            ),
            None,
        )
        if action is None:
            raise ProposalDecisionError(
                "WORKFLOW_ACTION_NOT_CURRENT",
                "/workflow_response/action_id",
                "action_id does not identify the current workflow action",
            )
        if (
            action.get("action_contract_version") != "topo.workflow-action/0.2"
            or action.get("reason_code") != "NET_WORTH_NEEDS_ACCOUNT_BALANCE"
        ):
            raise ProposalDecisionError(
                "WORKFLOW_RESPONSE_UNSUPPORTED",
                "/workflow_response/response_type",
                "the current workflow action does not accept account balances",
            )

        available_context = cast(JsonObject, action["available_context"])
        account_contexts = cast(list[JsonObject], available_context["accounts"])
        expected_accounts = {
            str(cast(JsonObject, item["account_ref"])["id"]): item
            for item in account_contexts
        }
        submitted_accounts = {
            balance.account_ref.id: balance for balance in response.balances
        }
        if submitted_accounts.keys() != expected_accounts.keys():
            raise ProposalDecisionError(
                "WORKFLOW_ACCOUNT_BALANCES_INCOMPLETE",
                "/workflow_response/balances",
                "submit exactly one balance for every account in available_context",
            )
        entity_types = {
            entity.id: entity.entity_type for entity in validated.entities.records
        }
        for account_id, balance in submitted_accounts.items():
            expected_source = cast(JsonObject, expected_accounts[account_id]["source"])
            if balance.source.model_dump(mode="json") != expected_source:
                raise ProposalDecisionError(
                    "WORKFLOW_ACCOUNT_SOURCE_MISMATCH",
                    "/workflow_response/balances",
                    "account source identity does not match its account_ref",
                )
            if entity_types.get(account_id) != "account":
                raise ProposalDecisionError(
                    "WORKFLOW_ACCOUNT_NOT_FOUND",
                    "/workflow_response/balances",
                    "account_ref does not resolve to an account entity",
                )

        proposed_assertions = {
            account_id: ProposedAssertion(
                subject_ref=balance.account_ref,
                predicate="domain.accounts/balance",
                object_value=ObjectValue(
                    value_type="money",
                    value=balance.money.model_dump(mode="json"),
                ),
                valid_time=ValidTime(
                    start=response.as_of_date,
                    end_exclusive=response.as_of_date + timedelta(days=1),
                ),
                knowledge_type="user_provided",
                module_data={
                    "economic_interest_ref": f"account:{account_id}",
                    "valuation_basis": "account_balance",
                },
            )
            for account_id, balance in submitted_accounts.items()
        }
        for proposed in proposed_assertions.values():
            self._module_catalog.validate_proposed_assertion(
                proposed,
                validated.manifest.modules,
                validated.assertions.records,
                validated.entities.records,
            )

        now = self._now()
        evidence_id = self._id_factory()
        normalized_balances = [
            submitted_accounts[account_id].model_dump(mode="json")
            for account_id in sorted(submitted_accounts)
        ]
        answer_evidence = UserStatementEvidenceRecord(
            id=evidence_id,
            evidence_type="user_statement",
            recorded_at=now,
            statement_type="workflow_answer",
            statement=cast(
                JsonObject,
                {
                    "action_id": response.action_id,
                    "response_type": response.response_type,
                    "analysis_id": response.analysis_id,
                    "analysis_scope": response.analysis_scope.model_dump(mode="json"),
                    "as_of_date": response.as_of_date.isoformat(),
                    "balances": normalized_balances,
                },
            ),
        )
        proposals: list[ProposalRecord] = []
        proposal_ids: list[str] = []
        for account_id in sorted(submitted_accounts):
            proposal_id = self._id_factory()
            proposal_ids.append(proposal_id)
            proposals.append(
                ProposalRecord(
                    id=proposal_id,
                    proposal_type="assertion",
                    producer=response.producer,
                    proposed_assertion=proposed_assertions[account_id],
                    batch_id=response.action_id,
                    evidence_refs=(Ref(ref_type="evidence", id=evidence_id),),
                    reason_ref=f"workflow-action:{response.action_id}",
                    detection=None,
                    status="open",
                    created_at=now,
                    decision=None,
                )
            )

        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        result: JsonObject = {
            "proposal_ids": cast(JsonValue, proposal_ids),
            "evidence_id": evidence_id,
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="proposal.submit",
            mutation_id=mutation_id,
            generation_id=generation_id,
            evidence=(*validated.evidence.records, answer_evidence),
            proposals=(*validated.proposals.records, *proposals),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def discover_recurring_cashflows(
        self, request: DiscoveryRequest
    ) -> DiscoveryOutcome:
        validated = self._load_existing()
        if request.context_id != validated.manifest.context_id:
            raise ValueError("request context does not match the package")
        scope_entities = tuple(
            entity
            for entity in validated.entities.records
            if entity.id == request.analysis_scope.entity_id
        )
        if (
            len(scope_entities) != 1
            or scope_entities[0].entity_type != request.analysis_scope.scope_type
        ):
            raise ValueError(
                "analysis scope does not resolve to the requested entity type"
            )
        self._module_catalog.require_pinned_identifiers(
            ("domain.cashflow/recurring_cashflow",), validated.manifest.modules
        )

        superseded_evidence = {
            record.supersedes
            for record in validated.evidence.records
            if isinstance(record, SourceRecordEvidenceRecord)
            and record.supersedes is not None
        }
        observations: list[TransactionObservation] = []
        for evidence in validated.evidence.records:
            if (
                not isinstance(evidence, SourceRecordEvidenceRecord)
                or evidence.id in superseded_evidence
            ):
                continue
            source_record = SourceImportRecord.model_validate_json(
                validated.source_records[evidence.record_path], strict=True
            )
            if source_record.booking_date > request.as_of_date:
                continue
            observations.append(
                TransactionObservation(
                    transaction_id=self._transaction_for_evidence(
                        validated.assertions.records, evidence.id
                    ),
                    evidence_id=evidence.id,
                    booking_date=source_record.booking_date,
                    amount=source_record.money.amount,
                    currency=source_record.money.currency,
                    description=source_record.description,
                )
            )
        result = recognize_recurring_cashflows(
            tuple(observations), subject_id=request.analysis_scope.entity_id
        )
        return DiscoveryOutcome(
            context_id=validated.manifest.context_id,
            generation_id=validated.manifest.generation_id,
            result=model_to_json_object(result),
        )

    def import_source(self, request: SourceImportRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        self._module_catalog.require_pinned_identifiers(
            (
                "domain.accounts/posting",
                "domain.cashflow/booking_date",
                "domain.cashflow/money",
                "domain.cashflow/description",
                "domain.cashflow/source_classification",
            ),
            validated.manifest.modules,
        )
        preview = self._source_import_preview(validated, request)
        if request.authorization is None:
            return self._authorization_required(request, preview)
        self._validate_authorization(request.authorization, preview)

        now = self._now()
        entities = list(validated.entities.records)
        assertions = list(validated.assertions.records)
        evidence = list(validated.evidence.records)
        proposals = list(validated.proposals.records)
        evidence_refs: list[Ref] = []
        account_refs: dict[str, Ref] = {}
        transaction_refs: list[Ref] = []
        source_records: dict[str, bytes] = {}
        imported = 0
        external_accounts: dict[tuple[str, str], str] = {}
        for assertion in validated.assertions.records:
            if (
                assertion.predicate != "domain.accounts/external_identity"
                or assertion.verification_status != "confirmed"
                or assertion.object_value is None
                or assertion.object_value.value_type != "external_identity"
                or not isinstance(assertion.object_value.value, dict)
            ):
                continue
            identity = assertion.object_value.value
            adapter_id = identity.get("adapter_id")
            source_id = identity.get("source_id")
            if isinstance(adapter_id, str) and isinstance(source_id, str):
                key = (adapter_id, source_id)
                if (
                    key in external_accounts
                    and external_accounts[key] != assertion.subject_ref.id
                ):
                    raise PackageIntegrityError(
                        "external account identity resolves to multiple accounts"
                    )
                external_accounts[key] = assertion.subject_ref.id

        identity_merges = self._identity_merge_candidates(
            validated, request, external_accounts
        )
        if identity_merges:
            identity_evidence_id = self._id_factory()
            evidence.append(
                UserStatementEvidenceRecord(
                    id=identity_evidence_id,
                    evidence_type="user_statement",
                    recorded_at=now,
                    statement_type="workflow_answer",
                    statement={
                        "response_type": "account_identity_merge",
                        "adapter_id": request.adapter.adapter_id,
                        "links": [
                            {"source_id": source_id, "account_id": account_id}
                            for source_id, account_id in sorted(identity_merges.items())
                        ],
                        "authorization": request.authorization.model_dump(mode="json"),
                    },
                )
            )
            for source_id, account_id in sorted(identity_merges.items()):
                proposed_identity = ProposedAssertion(
                    subject_ref=Ref(ref_type="entity", id=account_id),
                    predicate="domain.accounts/external_identity",
                    object_value=ObjectValue(
                        value_type="external_identity",
                        value={
                            "adapter_id": request.adapter.adapter_id,
                            "source_id": source_id,
                        },
                    ),
                    valid_time=ValidTime(
                        start=min(
                            record.booking_date
                            for record in request.records
                            if record.source_id == source_id
                        ),
                        end_exclusive=None,
                    ),
                    knowledge_type="user_provided",
                    module_data={},
                )
                self._module_catalog.validate_proposed_assertion(
                    proposed_identity,
                    validated.manifest.modules,
                    tuple(assertions),
                    tuple(entities),
                )
                assertions.append(
                    AssertionRecord(
                        id=self._id_factory(),
                        subject_ref=proposed_identity.subject_ref,
                        predicate=proposed_identity.predicate,
                        object_value=proposed_identity.object_value,
                        valid_time=proposed_identity.valid_time,
                        recorded_at=now,
                        knowledge_type=proposed_identity.knowledge_type,
                        verification_status="confirmed",
                        provenance=(Ref(ref_type="evidence", id=identity_evidence_id),),
                        supersedes=None,
                        module_data={},
                    )
                )
                external_accounts[(request.adapter.adapter_id, source_id)] = account_id

        for record in request.records:
            account_id = external_accounts.get(
                (request.adapter.adapter_id, record.source_id),
                source_account_id(request.adapter.adapter_id, record.source_id),
            )
            if not any(entity.id == account_id for entity in entities):
                entities.append(
                    EntityRecord(
                        id=account_id,
                        entity_type="account",
                        module_id="domain.accounts",
                        created_at=now,
                    )
                )
            account_refs[account_id] = Ref(ref_type="entity", id=account_id)
            prior = self._latest_source_evidence(
                tuple(evidence), request.adapter.adapter_id, record
            )
            record_payload = self._source_record_bytes(record)
            checksum = "sha256:" + hashlib.sha256(record_payload).hexdigest()
            if prior is not None and prior.source.record_checksum == checksum:
                transaction_id = self._transaction_for_evidence(
                    tuple(assertions), prior.id
                )
                evidence_refs.append(Ref(ref_type="evidence", id=prior.id))
                transaction_refs.append(Ref(ref_type="entity", id=transaction_id))
                continue

            transaction_id = (
                self._transaction_for_evidence(tuple(assertions), prior.id)
                if prior is not None
                else self._id_factory()
            )
            if prior is None:
                entities.append(
                    EntityRecord(
                        id=transaction_id,
                        entity_type="transaction",
                        module_id="domain.cashflow",
                        created_at=now,
                    )
                )
            evidence_id = self._id_factory()
            record_path = f"evidence/records/{evidence_id}.json"
            source_evidence = SourceRecordEvidenceRecord(
                id=evidence_id,
                evidence_type="source_record",
                source=SourceReference(
                    adapter_id=request.adapter.adapter_id,
                    adapter_version=request.adapter.adapter_version,
                    source_id=record.source_id,
                    record_id=record.record_id,
                    record_checksum=checksum,
                ),
                record_path=record_path,
                recorded_at=now,
                supersedes=prior.id if prior is not None else None,
            )
            evidence.append(source_evidence)
            source_records[record_path] = record_payload
            if prior is not None:
                proposals = [
                    proposal.model_copy(update={"status": "superseded"})
                    if proposal.status == "open"
                    and proposal.producer.producer_type == "source_adapter"
                    and proposal.producer.producer_id == request.adapter.adapter_id
                    and any(ref.id == prior.id for ref in proposal.evidence_refs)
                    else proposal
                    for proposal in proposals
                ]
            prior_assertions = self._source_assertions(
                tuple(assertions),
                transaction_id,
                prior.id if prior is not None else None,
            )
            observed = self._transaction_assertions(
                record,
                transaction_id=transaction_id,
                evidence_id=evidence_id,
                recorded_at=now,
                superseded=prior_assertions,
            )
            assertions.extend(observed)
            if record.source_classification is not None:
                proposal_id = self._id_factory()
                proposals.append(
                    ProposalRecord(
                        id=proposal_id,
                        proposal_type="assertion",
                        producer=Producer(
                            producer_type="source_adapter",
                            producer_id=request.adapter.adapter_id,
                            producer_version=request.adapter.adapter_version,
                        ),
                        proposed_assertion=ProposedAssertion(
                            subject_ref=Ref(ref_type="entity", id=transaction_id),
                            predicate="domain.cashflow/source_classification",
                            object_value=ObjectValue(
                                value_type="source_classification",
                                value=record.source_classification.model_dump(
                                    mode="json"
                                ),
                            ),
                            valid_time=ValidTime(
                                start=record.booking_date,
                                end_exclusive=record.booking_date + timedelta(days=1),
                            ),
                            knowledge_type="inferred",
                            module_data={},
                        ),
                        evidence_refs=(Ref(ref_type="evidence", id=evidence_id),),
                        reason_ref=(
                            "source-classification:"
                            f"{request.adapter.adapter_id}/"
                            f"{record.source_classification.rule_version}"
                        ),
                        detection=None,
                        status="open",
                        created_at=now,
                        decision=None,
                    )
                )
            imported += 1
            evidence_refs.append(Ref(ref_type="evidence", id=evidence_id))
            transaction_refs.append(Ref(ref_type="entity", id=transaction_id))

        result: JsonObject = {
            "imported": imported,
            "evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs],
            "account_refs": [
                ref.model_dump(mode="json")
                for ref in sorted(account_refs.values(), key=lambda item: item.id)
            ],
            "transaction_refs": [
                ref.model_dump(mode="json") for ref in transaction_refs
            ],
        }
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="source.import",
            mutation_id=mutation_id,
            generation_id=generation_id,
            entities=tuple(entities),
            assertions=tuple(assertions),
            evidence=tuple(evidence),
            proposals=tuple(proposals),
            source_records=source_records,
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def confirm_proposal(self, request: ProposalConfirmRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        proposal = self._open_proposal(
            validated.proposals.records, request.proposal_ref
        )
        proposed = proposal.proposed_assertion
        if proposed is None:
            raise ProposalDecisionError(
                "PROPOSAL_REQUIRES_BATCH",
                "/proposal_ref",
                "entity proposals must be decided through their batch",
            )
        preview = self._preview_result("proposal.confirm", request, proposal.id)
        if request.authorization is None:
            return self._authorization_required(request, preview)
        self._validate_authorization(request.authorization, preview)
        self._module_catalog.validate_proposed_assertion(
            proposed,
            validated.manifest.modules,
            validated.assertions.records,
            validated.entities.records,
        )
        now = self._now()
        evidence_id = self._id_factory()
        assertion_id = self._id_factory()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        confirmation_evidence = UserStatementEvidenceRecord(
            id=evidence_id,
            evidence_type="user_statement",
            recorded_at=now,
            statement_type="proposal_confirmation",
            statement={
                "proposal_id": proposal.id,
                "reason": request.reason,
                "authorization": request.authorization.model_dump(mode="json"),
            },
        )
        assertion = AssertionRecord(
            id=assertion_id,
            subject_ref=proposed.subject_ref,
            predicate=proposed.predicate,
            object_ref=proposed.object_ref,
            object_value=proposed.object_value,
            valid_time=proposed.valid_time,
            recorded_at=now,
            knowledge_type=proposed.knowledge_type,
            verification_status="confirmed",
            provenance=(
                *proposal.evidence_refs,
                Ref(ref_type="proposal", id=proposal.id),
                Ref(ref_type="evidence", id=evidence_id),
            ),
            supersedes=None,
            module_data=proposed.module_data,
        )
        decided = proposal.model_copy(
            update={
                "status": "confirmed",
                "decision": ProposalDecision(
                    outcome="confirmed",
                    actor=request.authorization.authorized_by,
                    decided_at=request.authorization.authorized_at,
                    mutation_id=mutation_id,
                    assertion_id=assertion_id,
                ),
            }
        )
        result: JsonObject = {
            "proposal_id": proposal.id,
            "assertion_id": assertion_id,
            "evidence_id": evidence_id,
            "decision_ref": f"decision:{mutation_id}",
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="proposal.confirm",
            mutation_id=mutation_id,
            generation_id=generation_id,
            assertions=(*validated.assertions.records, assertion),
            evidence=(*validated.evidence.records, confirmation_evidence),
            proposals=self._replace_proposal(validated.proposals.records, decided),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def confirm_proposal_batch(
        self, request: ProposalBatchConfirmRequest
    ) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        batch = tuple(
            proposal
            for proposal in validated.proposals.records
            if proposal.batch_id == request.batch_id
        )
        if not batch:
            raise ProposalDecisionError(
                "PROPOSAL_BATCH_NOT_FOUND", "/batch_id", "batch_id does not resolve"
            )
        if any(proposal.status != "open" for proposal in batch):
            raise ProposalDecisionError(
                "PROPOSAL_BATCH_NOT_OPEN",
                "/batch_id",
                "proposal batch is no longer wholly open",
            )
        preview = self._batch_preview_result(request, batch)
        if request.authorization is None:
            return self._authorization_required(request, preview)
        self._validate_authorization(request.authorization, preview)

        now = self._now()
        proposed_entities = tuple(
            proposal.proposed_entity
            for proposal in batch
            if proposal.proposed_entity is not None
        )
        new_entities = tuple(
            EntityRecord(
                id=entity.id,
                entity_type=entity.entity_type,
                module_id=entity.module_id,
                created_at=now,
            )
            for entity in proposed_entities
        )
        if {entity.id for entity in new_entities} & {
            entity.id for entity in validated.entities.records
        }:
            raise ProposalDecisionError(
                "PROPOSAL_ENTITY_CONFLICT",
                "/batch_id",
                "a proposed entity already exists",
            )
        final_entities = (*validated.entities.records, *new_entities)
        proposed_assertions = tuple(
            proposal.proposed_assertion
            for proposal in batch
            if proposal.proposed_assertion is not None
        )
        final_entity_ids = {entity.id for entity in final_entities}
        for proposed in proposed_assertions:
            if proposed.subject_ref.id not in final_entity_ids or (
                proposed.object_ref is not None
                and proposed.object_ref.id not in final_entity_ids
            ):
                raise ProposalDecisionError(
                    "PROPOSAL_BATCH_REFERENCE_UNRESOLVED",
                    "/batch_id",
                    "a batch assertion refers outside canonical or batch-local entities",
                )
            if (
                proposed.predicate.endswith("/inventory_coverage")
                and proposed.object_value is not None
                and isinstance(proposed.object_value.value, dict)
            ):
                refs = proposed.object_value.value.get("item_refs", [])
                if not isinstance(refs, list) or any(
                    not isinstance(ref, dict) or ref.get("id") not in final_entity_ids
                    for ref in refs
                ):
                    raise ProposalDecisionError(
                        "PROPOSAL_BATCH_COVERAGE_UNRESOLVED",
                        "/batch_id",
                        "inventory coverage contains an unresolved entity",
                    )
            self._module_catalog.validate_proposed_assertion(
                proposed,
                validated.manifest.modules,
                (*validated.assertions.records,),
                final_entities,
            )

        evidence_id = self._id_factory()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        confirmation_evidence = UserStatementEvidenceRecord(
            id=evidence_id,
            evidence_type="user_statement",
            recorded_at=now,
            statement_type="proposal_confirmation",
            statement={
                "batch_id": request.batch_id,
                "proposal_ids": [proposal.id for proposal in batch],
                "reason": request.reason,
                "authorization": request.authorization.model_dump(mode="json"),
            },
        )
        assertions: list[AssertionRecord] = []
        assertion_ids: dict[str, str] = {}
        for proposal in batch:
            proposed_assertion = proposal.proposed_assertion
            if proposed_assertion is None:
                continue
            assertion_id = self._id_factory()
            assertion_ids[proposal.id] = assertion_id
            assertions.append(
                AssertionRecord(
                    id=assertion_id,
                    subject_ref=proposed_assertion.subject_ref,
                    predicate=proposed_assertion.predicate,
                    object_ref=proposed_assertion.object_ref,
                    object_value=proposed_assertion.object_value,
                    valid_time=proposed_assertion.valid_time,
                    recorded_at=now,
                    knowledge_type=proposed_assertion.knowledge_type,
                    verification_status="confirmed",
                    provenance=(
                        *proposal.evidence_refs,
                        Ref(ref_type="proposal", id=proposal.id),
                        Ref(ref_type="evidence", id=evidence_id),
                    ),
                    supersedes=None,
                    module_data=proposed_assertion.module_data,
                )
            )
        decided_by_id = {
            proposal.id: proposal.model_copy(
                update={
                    "status": "confirmed",
                    "decision": ProposalDecision(
                        outcome="confirmed",
                        actor=request.authorization.authorized_by,
                        decided_at=request.authorization.authorized_at,
                        mutation_id=mutation_id,
                        assertion_id=assertion_ids.get(proposal.id),
                    ),
                }
            )
            for proposal in batch
        }
        result: JsonObject = {
            "batch_id": request.batch_id,
            "proposal_ids": [proposal.id for proposal in batch],
            "entity_ids": [entity.id for entity in new_entities],
            "assertion_ids": list(assertion_ids.values()),
            "evidence_id": evidence_id,
            "decision_ref": f"decision:{mutation_id}",
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="proposal.confirm-batch",
            mutation_id=mutation_id,
            generation_id=generation_id,
            entities=final_entities,
            assertions=(*validated.assertions.records, *assertions),
            evidence=(*validated.evidence.records, confirmation_evidence),
            proposals=tuple(
                decided_by_id.get(proposal.id, proposal)
                for proposal in validated.proposals.records
            ),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def reject_proposal_batch(
        self, request: ProposalBatchRejectRequest
    ) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        batch = tuple(
            proposal
            for proposal in validated.proposals.records
            if proposal.batch_id == request.batch_id
        )
        if not batch or any(proposal.status != "open" for proposal in batch):
            raise ProposalDecisionError(
                "PROPOSAL_BATCH_NOT_OPEN",
                "/batch_id",
                "proposal batch is not wholly open",
            )
        now = self._now()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        decided = {
            proposal.id: proposal.model_copy(
                update={
                    "status": "rejected",
                    "decision": ProposalDecision(
                        outcome="rejected",
                        actor=request.actor,
                        decided_at=now,
                        mutation_id=mutation_id,
                        assertion_id=None,
                    ),
                }
            )
            for proposal in batch
        }
        result: JsonObject = {
            "batch_id": request.batch_id,
            "proposal_ids": [proposal.id for proposal in batch],
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="proposal.reject-batch",
            mutation_id=mutation_id,
            generation_id=generation_id,
            proposals=tuple(
                decided.get(proposal.id, proposal)
                for proposal in validated.proposals.records
            ),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def correct_proposal(self, request: ProposalCorrectRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        proposal = self._open_proposal(
            validated.proposals.records, request.proposal_ref
        )
        proposed = proposal.proposed_assertion
        if proposed is None:
            raise ProposalDecisionError(
                "PROPOSAL_REQUIRES_BATCH",
                "/proposal_ref",
                "entity proposals must be decided through their batch",
            )
        corrected = proposed.model_copy(
            update={
                "object_ref": request.correction.object_ref,
                "object_value": request.correction.object_value,
            }
        )
        self._module_catalog.validate_proposed_assertion(
            corrected,
            validated.manifest.modules,
            validated.assertions.records,
            validated.entities.records,
        )
        preview = self._preview_result(
            "proposal.correct",
            request,
            proposal.id,
            correction=request.correction.model_dump(mode="json"),
        )
        if request.authorization is None:
            return self._authorization_required(request, preview)
        self._validate_authorization(request.authorization, preview)
        now = self._now()
        evidence_id = self._id_factory()
        assertion_id = self._id_factory()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        correction_evidence = UserStatementEvidenceRecord(
            id=evidence_id,
            evidence_type="user_statement",
            recorded_at=now,
            statement_type="proposal_correction",
            statement={
                "proposal_id": proposal.id,
                "reason": request.correction.reason,
                "correction": request.correction.model_dump(mode="json"),
                "authorization": request.authorization.model_dump(mode="json"),
            },
        )
        assertion = AssertionRecord(
            id=assertion_id,
            subject_ref=proposed.subject_ref,
            predicate=proposed.predicate,
            object_ref=corrected.object_ref,
            object_value=corrected.object_value,
            valid_time=proposed.valid_time,
            recorded_at=now,
            knowledge_type="user_provided",
            verification_status="confirmed",
            provenance=(
                *proposal.evidence_refs,
                Ref(ref_type="proposal", id=proposal.id),
                Ref(ref_type="evidence", id=evidence_id),
            ),
            supersedes=None,
            module_data=proposed.module_data,
        )
        decided = proposal.model_copy(
            update={
                "status": "corrected",
                "decision": ProposalDecision(
                    outcome="corrected",
                    actor=request.authorization.authorized_by,
                    decided_at=request.authorization.authorized_at,
                    mutation_id=mutation_id,
                    assertion_id=assertion_id,
                ),
            }
        )
        result: JsonObject = {
            "proposal_id": proposal.id,
            "assertion_id": assertion_id,
            "evidence_id": evidence_id,
            "decision_ref": f"decision:{mutation_id}",
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="proposal.correct",
            mutation_id=mutation_id,
            generation_id=generation_id,
            assertions=(*validated.assertions.records, assertion),
            evidence=(*validated.evidence.records, correction_evidence),
            proposals=self._replace_proposal(validated.proposals.records, decided),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def reject_proposal(self, request: ProposalRejectRequest) -> MutationOutcome:
        validated = self._load_full_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        proposal = self._open_proposal(
            validated.proposals.records, request.proposal_ref
        )
        now = self._now()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        decided = proposal.model_copy(
            update={
                "status": "rejected",
                "decision": ProposalDecision(
                    outcome="rejected",
                    actor=request.actor,
                    decided_at=now,
                    mutation_id=mutation_id,
                    assertion_id=None,
                ),
            }
        )
        result: JsonObject = {
            "proposal_id": proposal.id,
            "decision_ref": f"decision:{mutation_id}",
        }
        publication = self._build_update_publication(
            validated,
            request=request,
            operation="proposal.reject",
            mutation_id=mutation_id,
            generation_id=generation_id,
            proposals=self._replace_proposal(validated.proposals.records, decided),
            result=result,
            now=now,
        )
        self._commit_update(publication, request.expected_generation)
        return self._success(request, generation_id, result)

    def _load_existing(self) -> ValidatedPackage:
        return load_and_validate_generation(self._load_current_snapshot())

    def _load_full_existing(self) -> ValidatedPackage:
        return load_and_validate_generation(self._load_snapshot())

    def _load_current_snapshot(self) -> StoredPackageSnapshot:
        try:
            snapshot = (
                self._storage.load_current()
                if isinstance(self._storage, CurrentStorage)
                else self._storage.load()
            )
        except OSError as error:
            raise PackageIntegrityError(str(error)) from error
        if snapshot is None:
            raise PackageIntegrityError("context package does not exist")
        return snapshot

    def _load_snapshot(self) -> StoredPackageSnapshot:
        try:
            snapshot = self._storage.load()
        except OSError as error:
            raise PackageIntegrityError(str(error)) from error
        if snapshot is None:
            raise PackageIntegrityError("context package does not exist")
        return snapshot

    @staticmethod
    def _replay(journal: Journal, operation_id: str) -> JournalEntry | None:
        return next(
            (entry for entry in journal.entries if entry.operation_id == operation_id),
            None,
        )

    @staticmethod
    def _replayed_outcome(manifest: Manifest, entry: JournalEntry) -> MutationOutcome:
        return MutationOutcome(
            context_id=manifest.context_id,
            generation_before=manifest.generation_id,
            generation_after=manifest.generation_id,
            outcome="no_change",
            result=entry.result,
            replayed=True,
        )

    @staticmethod
    def _guard_request(
        manifest: Manifest, request: MutationRequest
    ) -> MutationOutcome | None:
        if request.context_id != manifest.context_id:
            raise ValueError("context_id does not match the package")
        if request.expected_generation == manifest.generation_id:
            return None
        return MutationOutcome(
            context_id=manifest.context_id,
            generation_before=manifest.generation_id,
            generation_after=manifest.generation_id,
            outcome="conflict",
            result={
                "expected_generation": request.expected_generation,
                "actual_generation": manifest.generation_id,
            },
        )

    @staticmethod
    def _open_proposal(
        proposals: tuple[ProposalRecord, ...], proposal_id: str
    ) -> ProposalRecord:
        proposal = next(
            (candidate for candidate in proposals if candidate.id == proposal_id),
            None,
        )
        if proposal is None:
            raise ProposalDecisionError(
                "PROPOSAL_NOT_FOUND", "/proposal_ref", "proposal_ref does not resolve"
            )
        if proposal.status != "open":
            raise ProposalDecisionError(
                "PROPOSAL_NOT_OPEN", "/proposal_ref", "proposal is no longer open"
            )
        return proposal

    @staticmethod
    def _preview_result(
        command: str,
        request: MutationRequest,
        proposal_id: str,
        *,
        correction: JsonObject | None = None,
    ) -> JsonObject:
        basis = {
            "command": command,
            "context_id": request.context_id,
            "expected_generation": request.expected_generation,
            "proposal_id": proposal_id,
            "correction": correction,
        }
        digest = hashlib.sha256(
            json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        action = (
            "create_corrected_assertion"
            if command == "proposal.correct"
            else "create_confirmed_assertion"
        )
        return {
            "preview_ref": f"preview:sha256:{digest}",
            "effects": [{"action": action, "proposal_ref": proposal_id}],
        }

    @staticmethod
    def _batch_preview_result(
        request: ProposalBatchConfirmRequest,
        proposals: tuple[ProposalRecord, ...],
    ) -> JsonObject:
        normalized = [
            proposal.model_dump(mode="json")
            for proposal in sorted(proposals, key=lambda item: item.id)
        ]
        basis = {
            "command": "proposal.confirm-batch",
            "context_id": request.context_id,
            "expected_generation": request.expected_generation,
            "batch_id": request.batch_id,
            "proposals": normalized,
        }
        digest = hashlib.sha256(
            json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "preview_ref": f"preview:sha256:{digest}",
            "batch_id": request.batch_id,
            "effects": [
                {
                    "action": (
                        "create_entity"
                        if proposal.proposal_type == "entity"
                        else "create_confirmed_assertion"
                    ),
                    "proposal_ref": proposal.id,
                }
                for proposal in sorted(proposals, key=lambda item: item.id)
            ],
        }

    @staticmethod
    def _validate_authorization(
        authorization: Authorization, preview: JsonObject
    ) -> None:
        if authorization.preview_ref != preview["preview_ref"]:
            raise ProposalDecisionError(
                "INVALID_AUTHORIZATION",
                "/authorization/preview_ref",
                "authorization does not match this preview",
            )
        if authorization.authorized_by.actor_type != "human":
            raise ProposalDecisionError(
                "INVALID_AUTHORIZATION",
                "/authorization/authorized_by/actor_type",
                "proposal authorization must be provided by a human",
            )

    @staticmethod
    def _authorization_required(
        request: MutationRequest, preview: JsonObject
    ) -> MutationOutcome:
        return MutationOutcome(
            context_id=request.context_id,
            generation_before=request.expected_generation,
            generation_after=request.expected_generation,
            outcome="requires_authorization",
            result=preview,
        )

    @staticmethod
    def _replace_proposal(
        proposals: tuple[ProposalRecord, ...], replacement: ProposalRecord
    ) -> tuple[ProposalRecord, ...]:
        return tuple(
            replacement if proposal.id == replacement.id else proposal
            for proposal in proposals
        )

    @staticmethod
    def _latest_source_evidence(
        evidence: tuple[EvidenceRecord, ...],
        adapter_id: str,
        record: SourceImportRecord,
    ) -> SourceRecordEvidenceRecord | None:
        matching = tuple(
            item
            for item in evidence
            if isinstance(item, SourceRecordEvidenceRecord)
            and item.source.adapter_id == adapter_id
            and item.source.source_id == record.source_id
            and item.source.record_id == record.record_id
        )
        superseded_ids = {
            item.supersedes for item in matching if item.supersedes is not None
        }
        return next((item for item in matching if item.id not in superseded_ids), None)

    @staticmethod
    def _source_record_bytes(record: SourceImportRecord) -> bytes:
        return _json_bytes(record)

    def _source_import_preview(
        self, validated: ValidatedPackage, request: SourceImportRequest
    ) -> JsonObject:
        effects: list[JsonValue] = []
        external_accounts = self._confirmed_external_accounts(validated)
        for source_id, account_id in sorted(
            self._identity_merge_candidates(
                validated, request, external_accounts
            ).items()
        ):
            effects.append(
                {
                    "action": "merge_external_account_identity",
                    "adapter_id": request.adapter.adapter_id,
                    "source_id": source_id,
                    "account_ref": {"ref_type": "entity", "id": account_id},
                }
            )
        for record in request.records:
            prior = self._latest_source_evidence(
                validated.evidence.records, request.adapter.adapter_id, record
            )
            checksum = (
                "sha256:"
                + hashlib.sha256(self._source_record_bytes(record)).hexdigest()
            )
            if prior is None:
                action = "create_source_transaction"
            elif prior.source.record_checksum == checksum:
                action = "retain_source_transaction"
            else:
                action = "correct_source_transaction"
            effects.append(
                {
                    "action": action,
                    "source_id": record.source_id,
                    "record_id": record.record_id,
                }
            )
        basis = request.model_dump(mode="json", exclude={"authorization"})
        digest = hashlib.sha256(
            json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {"preview_ref": f"preview:sha256:{digest}", "effects": effects}

    @staticmethod
    def _confirmed_external_accounts(
        validated: ValidatedPackage,
    ) -> dict[tuple[str, str], str]:
        result: dict[tuple[str, str], str] = {}
        for assertion in validated.assertions.records:
            if (
                assertion.predicate != "domain.accounts/external_identity"
                or assertion.verification_status != "confirmed"
                or assertion.object_value is None
                or assertion.object_value.value_type != "external_identity"
                or not isinstance(assertion.object_value.value, dict)
            ):
                continue
            adapter_id = assertion.object_value.value.get("adapter_id")
            source_id = assertion.object_value.value.get("source_id")
            if isinstance(adapter_id, str) and isinstance(source_id, str):
                result[(adapter_id, source_id)] = assertion.subject_ref.id
        return result

    @staticmethod
    def _identity_merge_candidates(
        validated: ValidatedPackage,
        request: SourceImportRequest,
        external_accounts: dict[tuple[str, str], str],
    ) -> dict[str, str]:
        imported_account_ids = {
            source_account_id(item.source.adapter_id, item.source.source_id)
            for item in validated.evidence.records
            if isinstance(item, SourceRecordEvidenceRecord)
        }
        linked_account_ids = set(external_accounts.values())
        manual_accounts = [
            entity.id
            for entity in validated.entities.records
            if entity.entity_type == "account"
            and entity.id not in imported_account_ids
            and entity.id not in linked_account_ids
        ]
        new_source_ids = sorted(
            {
                record.source_id
                for record in request.records
                if (request.adapter.adapter_id, record.source_id)
                not in external_accounts
            }
        )
        if len(manual_accounts) == 1 and len(new_source_ids) == 1:
            return {new_source_ids[0]: manual_accounts[0]}
        return {}

    @staticmethod
    def _transaction_for_evidence(
        assertions: tuple[AssertionRecord, ...], evidence_id: str
    ) -> str:
        transaction_ids = {
            assertion.subject_ref.id
            for assertion in assertions
            if any(
                ref.ref_type == "evidence" and ref.id == evidence_id
                for ref in assertion.provenance
            )
            and assertion.predicate == "domain.cashflow/booking_date"
        }
        if len(transaction_ids) != 1:
            raise PackageIntegrityError(
                "source evidence does not resolve to exactly one transaction"
            )
        return next(iter(transaction_ids))

    @staticmethod
    def _source_assertions(
        assertions: tuple[AssertionRecord, ...],
        transaction_id: str,
        evidence_id: str | None,
    ) -> dict[str, AssertionRecord]:
        if evidence_id is None:
            return {}
        return {
            assertion.predicate: assertion
            for assertion in assertions
            if assertion.subject_ref.id == transaction_id
            and any(
                ref.ref_type == "evidence" and ref.id == evidence_id
                for ref in assertion.provenance
            )
        }

    def _transaction_assertions(
        self,
        record: SourceImportRecord,
        *,
        transaction_id: str,
        evidence_id: str,
        recorded_at: datetime,
        superseded: dict[str, AssertionRecord],
    ) -> tuple[AssertionRecord, ...]:
        values: tuple[tuple[str, str, JsonValue], ...] = (
            ("domain.accounts/posting", "source_account", record.source_id),
            ("domain.cashflow/booking_date", "date", record.booking_date.isoformat()),
            ("domain.cashflow/money", "money", record.money.model_dump(mode="json")),
            ("domain.cashflow/description", "text", record.description),
        )
        return tuple(
            AssertionRecord(
                id=self._id_factory(),
                subject_ref=Ref(ref_type="entity", id=transaction_id),
                predicate=predicate,
                object_value=ObjectValue(value_type=value_type, value=value),
                valid_time=ValidTime(
                    start=record.booking_date,
                    end_exclusive=record.booking_date + timedelta(days=1),
                ),
                recorded_at=recorded_at,
                knowledge_type="observed",
                verification_status="confirmed",
                provenance=(Ref(ref_type="evidence", id=evidence_id),),
                supersedes=(
                    superseded[predicate].id if predicate in superseded else None
                ),
                module_data={},
            )
            for predicate, value_type, value in values
        )

    def _build_update_publication(
        self,
        validated: ValidatedPackage,
        *,
        request: MutationRequest,
        operation: Literal[
            "source.import",
            "proposal.submit",
            "proposal.confirm",
            "proposal.correct",
            "proposal.reject",
            "workflow.respond",
            "proposal.confirm-batch",
            "proposal.reject-batch",
            "rule.activate",
            "context.migrate",
            "context.restore",
            "context.compact",
            "context.privacy_scrub",
        ],
        mutation_id: str,
        generation_id: str,
        result: JsonObject,
        now: datetime,
        entities: tuple[EntityRecord, ...] | None = None,
        assertions: tuple[AssertionRecord, ...] | None = None,
        evidence: tuple[EvidenceRecord, ...] | None = None,
        proposals: tuple[ProposalRecord, ...] | None = None,
        source_records: dict[str, bytes] | None = None,
        active_rule_packages: tuple[RulePackagePin, ...] | None = None,
        rule_package_files: dict[str, bytes] | None = None,
        modules: tuple[ModulePin, ...] | None = None,
        package_version: Literal["0.1", "0.2"] | None = None,
        context_schema_version: Literal["topo.context/0.1", "topo.context/0.2"]
        | None = None,
        based_on: str | None = None,
        journal_entries: tuple[JournalEntry, ...] | None = None,
    ) -> PackageCommit:
        inventory_payload = _evidence_inventory_bytes(
            tuple({*validated.source_records, *(source_records or {})})
        )
        target_context_schema = (
            validated.manifest.context_schema_version
            if context_schema_version is None
            else context_schema_version
        )
        collections = {
            "entities.json": _json_bytes(
                CanonicalCollection[EntityRecord](
                    schema_version=target_context_schema,
                    records=tuple(
                        sorted(
                            entities or validated.entities.records, key=lambda x: x.id
                        )
                    ),
                )
            ),
            "assertions.json": _json_bytes(
                CanonicalCollection[AssertionRecord](
                    schema_version=target_context_schema,
                    records=tuple(
                        sorted(
                            assertions or validated.assertions.records,
                            key=lambda x: x.id,
                        )
                    ),
                )
            ),
            "evidence.json": _json_bytes(
                CanonicalCollection[EvidenceRecord](
                    schema_version=target_context_schema,
                    records=tuple(
                        sorted(
                            evidence or validated.evidence.records, key=lambda x: x.id
                        )
                    ),
                )
            ),
            "proposals.json": _json_bytes(
                CanonicalCollection[ProposalRecord](
                    schema_version=target_context_schema,
                    records=tuple(
                        sorted(
                            proposals or validated.proposals.records, key=lambda x: x.id
                        )
                    ),
                )
            ),
        }
        active_artifacts = (
            validated.rule_package_files
            if rule_package_files is None
            else rule_package_files
        )
        generation_payloads = {**collections, **active_artifacts}
        checksums = {
            filename: "sha256:" + hashlib.sha256(payload).hexdigest()
            for filename, payload in generation_payloads.items()
        }
        manifest = validated.manifest.model_copy(
            update={
                "generation_id": generation_id,
                "based_on": validated.manifest.generation_id,
                "mutation_id": mutation_id,
                "recorded_at": now,
                "package_version": (
                    validated.manifest.package_version
                    if package_version is None
                    else package_version
                ),
                "context_schema_version": target_context_schema,
                "modules": (validated.manifest.modules if modules is None else modules),
                "active_rule_packages": (
                    validated.manifest.active_rule_packages
                    if active_rule_packages is None
                    else active_rule_packages
                ),
                "files": checksums,
            }
        )
        if based_on is not None:
            manifest = manifest.model_copy(update={"based_on": based_on})
        journal = Journal(
            schema_version="topo.journal/0.1",
            entries=(
                *(
                    validated.journal.entries
                    if journal_entries is None
                    else journal_entries
                ),
                JournalEntry(
                    operation_id=request.operation_id,
                    mutation_id=mutation_id,
                    operation=operation,
                    actor=request.actor,
                    reason=request.reason,
                    generation_before=(
                        validated.manifest.generation_id
                        if based_on is None
                        else based_on
                    ),
                    generation_after=generation_id,
                    recorded_at=now,
                    result=result,
                ),
            ),
        )
        publication = PackageCommit(
            generation_id=generation_id,
            generation_files={
                **generation_payloads,
                "manifest.json": _json_bytes(manifest),
            },
            journal=_json_bytes(journal),
            evidence_records=source_records or {},
            evidence_inventory=inventory_payload,
        )
        load_and_validate_generation(
            StoredPackageSnapshot(
                current_generation=generation_id,
                generation_files=publication.generation_files,
                journal=publication.journal,
                evidence_records={
                    **validated.source_records,
                    **publication.evidence_records,
                },
            )
        )
        return publication

    def _commit_update(self, publication: PackageCommit, expected: str) -> None:
        self._storage.commit(publication, expected_generation=expected)

    @staticmethod
    def _guard_rule_read(manifest: Manifest, request: RulePackageRequest) -> None:
        if request.context_id != manifest.context_id:
            raise ValueError("context_id does not match the package")
        if request.expected_generation != manifest.generation_id:
            raise ValueError("expected_generation is not the active manifest version")

    @staticmethod
    def _validated_rule_package(
        validated: ValidatedPackage, payload: str
    ) -> DeclarativeRulePackage:
        package = parse_rule_package(payload)
        validate_rule_package(
            package,
            default_rule_registry(),
            pinned_modules={
                pin.module_id: pin.module_version for pin in validated.manifest.modules
            },
        )
        return package

    @staticmethod
    def _success(
        request: MutationRequest, generation_id: str, result: JsonObject
    ) -> MutationOutcome:
        return MutationOutcome(
            context_id=request.context_id,
            generation_before=request.expected_generation,
            generation_after=generation_id,
            outcome="succeeded",
            result=result,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("EngineCore clock must return a timezone-aware datetime")
        return now.astimezone(UTC)

    def _build_initial_publication(self, request: ContextInitRequest) -> PackageCommit:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("EngineCore clock must return a timezone-aware datetime")
        now = now.astimezone(UTC)

        context_id = self._id_factory()
        household_id = self._id_factory()
        person_id = self._id_factory()
        evidence_id = self._id_factory()
        membership_id = self._id_factory()
        generation_id = self._id_factory()
        mutation_id = self._id_factory()

        entities = CanonicalCollection[EntityRecord](
            schema_version="topo.context/0.2",
            records=tuple(
                sorted(
                    (
                        EntityRecord(
                            id=context_id,
                            entity_type="context",
                            module_id="topo.core",
                            created_at=now,
                        ),
                        EntityRecord(
                            id=household_id,
                            entity_type="household",
                            module_id="domain.parties",
                            created_at=now,
                        ),
                        EntityRecord(
                            id=person_id,
                            entity_type="person",
                            module_id="domain.parties",
                            created_at=now,
                        ),
                    ),
                    key=lambda record: record.id,
                )
            ),
        )
        evidence = CanonicalCollection[EvidenceRecord](
            schema_version="topo.context/0.2",
            records=(
                UserStatementEvidenceRecord(
                    id=evidence_id,
                    evidence_type="user_statement",
                    recorded_at=now,
                    statement_type="context_initialization",
                ),
            ),
        )
        assertions = CanonicalCollection[AssertionRecord](
            schema_version="topo.context/0.2",
            records=(
                AssertionRecord(
                    id=membership_id,
                    subject_ref=Ref(ref_type="entity", id=person_id),
                    predicate="domain.parties/household_membership",
                    object_ref=Ref(ref_type="entity", id=household_id),
                    valid_time=ValidTime(start=now.date(), end_exclusive=None),
                    recorded_at=now,
                    knowledge_type="user_provided",
                    verification_status="confirmed",
                    provenance=(Ref(ref_type="evidence", id=evidence_id),),
                    supersedes=None,
                    module_data={},
                ),
            ),
        )
        proposals = CanonicalCollection[ProposalRecord](
            schema_version="topo.context/0.2",
            records=(),
        )
        inventory_payload = _evidence_inventory_bytes(())
        collections = {
            "entities.json": _json_bytes(entities),
            "assertions.json": _json_bytes(assertions),
            "evidence.json": _json_bytes(evidence),
            "proposals.json": _json_bytes(proposals),
        }
        checksums = {
            filename: "sha256:" + hashlib.sha256(payload).hexdigest()
            for filename, payload in collections.items()
        }
        manifest = Manifest(
            schema_version="topo.manifest/0.1",
            context_id=context_id,
            generation_id=generation_id,
            based_on=None,
            package_version="0.2",
            context_schema_version="topo.context/0.2",
            mutation_id=mutation_id,
            recorded_at=now,
            modules=self._module_catalog.pins,
            active_rule_packages=(),
            files=checksums,
        )
        journal = Journal(
            schema_version="topo.journal/0.1",
            entries=(
                JournalEntry(
                    operation_id=request.operation_id,
                    mutation_id=mutation_id,
                    operation="context.init",
                    actor=Actor.model_validate(request.actor),
                    reason=request.reason,
                    generation_before=None,
                    generation_after=generation_id,
                    recorded_at=now,
                    result={
                        "context_id": context_id,
                        "generation_id": generation_id,
                        "mutation_id": mutation_id,
                        "person_id": person_id,
                        "household_id": household_id,
                        "membership_assertion_id": membership_id,
                    },
                ),
            ),
        )
        return PackageCommit(
            generation_id=generation_id,
            generation_files={
                **collections,
                "manifest.json": _json_bytes(manifest),
            },
            journal=_json_bytes(journal),
            evidence_inventory=inventory_payload,
        )
