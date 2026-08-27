from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from topo.canonical_validation import ValidatedPackage, load_and_validate_generation
from topo.errors import (
    ContextAlreadyExistsError,
    PackageIntegrityError,
    ProposalDecisionError,
)
from topo.identifiers import uuid7
from topo.models import (
    Actor,
    AssertionRecord,
    Authorization,
    CanonicalCollection,
    ContextInitRequest,
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
    ProposalConfirmRequest,
    ProposalCorrectRequest,
    ProposalDecision,
    ProposalRecord,
    ProposalRejectRequest,
    ProposalSubmitRequest,
    Ref,
    ValidTime,
)
from topo.storage import (
    PackageCommit,
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


def _module_checksum(module_id: str, module_version: str) -> str:
    # Ticket 03 replaces this compatibility placeholder with an artifact digest.
    identity = f"{module_id}/{module_version}".encode()
    return "sha256:" + hashlib.sha256(identity).hexdigest()


class EngineCore:
    """Own generation, validation, history, and replay semantics."""

    def __init__(
        self,
        storage: StorageAdapter,
        *,
        clock: Clock | None = None,
        id_factory: IdFactory = uuid7,
    ) -> None:
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory

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

    def submit_proposal(self, request: ProposalSubmitRequest) -> MutationOutcome:
        validated = self._load_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
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

    def confirm_proposal(self, request: ProposalConfirmRequest) -> MutationOutcome:
        validated = self._load_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        proposal = self._open_proposal(
            validated.proposals.records, request.proposal_ref
        )
        preview = self._preview_result("proposal.confirm", request, proposal.id)
        if request.authorization is None:
            return self._authorization_required(request, preview)
        self._validate_authorization(request.authorization, preview)
        now = self._now()
        evidence_id = self._id_factory()
        assertion_id = self._id_factory()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        proposed = proposal.proposed_assertion
        confirmation_evidence = EvidenceRecord(
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

    def correct_proposal(self, request: ProposalCorrectRequest) -> MutationOutcome:
        validated = self._load_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
        proposal = self._open_proposal(
            validated.proposals.records, request.proposal_ref
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
        correction_evidence = EvidenceRecord(
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
        proposed = proposal.proposed_assertion
        assertion = AssertionRecord(
            id=assertion_id,
            subject_ref=proposed.subject_ref,
            predicate=proposed.predicate,
            object_ref=request.correction.object_ref,
            object_value=request.correction.object_value,
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
        validated = self._load_existing()
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
        result: JsonObject = {"proposal_id": proposal.id}
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
        try:
            snapshot = self._storage.load()
        except OSError as error:
            raise PackageIntegrityError(str(error)) from error
        if snapshot is None:
            raise PackageIntegrityError("context package does not exist")
        return load_and_validate_generation(snapshot)

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

    def _build_update_publication(
        self,
        validated: ValidatedPackage,
        *,
        request: MutationRequest,
        operation: Literal[
            "proposal.submit",
            "proposal.confirm",
            "proposal.correct",
            "proposal.reject",
        ],
        mutation_id: str,
        generation_id: str,
        result: JsonObject,
        now: datetime,
        assertions: tuple[AssertionRecord, ...] | None = None,
        evidence: tuple[EvidenceRecord, ...] | None = None,
        proposals: tuple[ProposalRecord, ...] | None = None,
    ) -> PackageCommit:
        collections = {
            "entities.json": _json_bytes(validated.entities),
            "assertions.json": _json_bytes(
                CanonicalCollection[AssertionRecord](
                    schema_version="topo.context/0.1",
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
                    schema_version="topo.context/0.1",
                    records=tuple(
                        sorted(
                            evidence or validated.evidence.records, key=lambda x: x.id
                        )
                    ),
                )
            ),
            "proposals.json": _json_bytes(
                CanonicalCollection[ProposalRecord](
                    schema_version="topo.context/0.1",
                    records=tuple(
                        sorted(
                            proposals or validated.proposals.records, key=lambda x: x.id
                        )
                    ),
                )
            ),
        }
        checksums = {
            filename: "sha256:" + hashlib.sha256(payload).hexdigest()
            for filename, payload in collections.items()
        }
        manifest = validated.manifest.model_copy(
            update={
                "generation_id": generation_id,
                "based_on": validated.manifest.generation_id,
                "mutation_id": mutation_id,
                "recorded_at": now,
                "files": checksums,
            }
        )
        journal = Journal(
            schema_version="topo.journal/0.1",
            entries=(
                *validated.journal.entries,
                JournalEntry(
                    operation_id=request.operation_id,
                    mutation_id=mutation_id,
                    operation=operation,
                    actor=request.actor,
                    reason=request.reason,
                    generation_before=validated.manifest.generation_id,
                    generation_after=generation_id,
                    recorded_at=now,
                    result=result,
                ),
            ),
        )
        publication = PackageCommit(
            generation_id=generation_id,
            generation_files={
                **collections,
                "manifest.json": _json_bytes(manifest),
            },
            journal=_json_bytes(journal),
        )
        load_and_validate_generation(
            StoredPackageSnapshot(
                current_generation=generation_id,
                generation_files=publication.generation_files,
                journal=publication.journal,
            )
        )
        return publication

    def _commit_update(self, publication: PackageCommit, expected: str) -> None:
        self._storage.commit(publication, expected_generation=expected)

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
            schema_version="topo.context/0.1",
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
            schema_version="topo.context/0.1",
            records=(
                EvidenceRecord(
                    id=evidence_id,
                    evidence_type="user_statement",
                    recorded_at=now,
                    statement_type="context_initialization",
                ),
            ),
        )
        assertions = CanonicalCollection[AssertionRecord](
            schema_version="topo.context/0.1",
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
            schema_version="topo.context/0.1",
            records=(),
        )
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
            package_version="0.1",
            context_schema_version="topo.context/0.1",
            mutation_id=mutation_id,
            recorded_at=now,
            modules=(
                ModulePin(
                    module_id="topo.core",
                    module_version="0.1.0",
                    checksum=_module_checksum("topo.core", "0.1.0"),
                ),
                ModulePin(
                    module_id="domain.parties",
                    module_version="0.1.0",
                    checksum=_module_checksum("domain.parties", "0.1.0"),
                ),
            ),
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
        )
