from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, JsonValue

from topo.builtin_modules import default_module_catalog
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
    MutationOutcome,
    MutationRequest,
    ObjectValue,
    Producer,
    ProposalConfirmRequest,
    ProposalCorrectRequest,
    ProposalDecision,
    ProposalRecord,
    ProposalRejectRequest,
    ProposalSubmitRequest,
    ProposedAssertion,
    Ref,
    SourceImportRecord,
    SourceImportRequest,
    SourceRecordEvidenceRecord,
    SourceReference,
    UserStatementEvidenceRecord,
    ValidTime,
)
from topo.modules import ModuleCatalog
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

    def submit_proposal(self, request: ProposalSubmitRequest) -> MutationOutcome:
        validated = self._load_existing()
        replay = self._replay(validated.journal, request.operation_id)
        if replay is not None:
            return self._replayed_outcome(validated.manifest, replay)
        conflict = self._guard_request(validated.manifest, request)
        if conflict is not None:
            return conflict
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

    def import_source(self, request: SourceImportRequest) -> MutationOutcome:
        validated = self._load_existing()
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
        transaction_refs: list[Ref] = []
        source_records: dict[str, bytes] = {}
        imported = 0

        for record in request.records:
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
        self._module_catalog.validate_proposed_assertion(
            proposal.proposed_assertion,
            validated.manifest.modules,
            validated.assertions.records,
            validated.entities.records,
        )
        now = self._now()
        evidence_id = self._id_factory()
        assertion_id = self._id_factory()
        mutation_id = self._id_factory()
        generation_id = self._id_factory()
        proposed = proposal.proposed_assertion
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
        proposed = proposal.proposed_assertion
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
    ) -> PackageCommit:
        collections = {
            "entities.json": _json_bytes(
                CanonicalCollection[EntityRecord](
                    schema_version="topo.context/0.1",
                    records=tuple(
                        sorted(
                            entities or validated.entities.records, key=lambda x: x.id
                        )
                    ),
                )
            ),
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
            evidence_records=source_records or {},
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
                UserStatementEvidenceRecord(
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
        )
