from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, cast

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from topo.identifiers import UUID7_PATTERN

JsonObject = dict[str, JsonValue]
Outcome = Literal[
    "succeeded",
    "no_change",
    "rejected",
    "conflict",
    "requires_authorization",
]
UUID7 = Annotated[str, StringConstraints(pattern=UUID7_PATTERN, strict=True)]
NonEmptyString = Annotated[str, StringConstraints(min_length=1, strict=True)]
Checksum = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$", strict=True),
]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$", strict=True)]
DecimalString = Annotated[
    str,
    StringConstraints(pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$", strict=True),
]


class TopoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Actor(TopoModel):
    actor_type: Literal["human", "agent", "rule_module", "source_adapter", "system"]
    actor_id: NonEmptyString


class Ref(TopoModel):
    ref_type: NonEmptyString
    id: UUID7


class Money(TopoModel):
    amount: DecimalString
    currency: Currency


class RecurringExpectedPeriod(TopoModel):
    start_date: date
    end_exclusive: date

    @model_validator(mode="after")
    def ordered_period(self) -> RecurringExpectedPeriod:
        if self.end_exclusive <= self.start_date:
            raise ValueError("expected period must be non-empty")
        return self


class RecurringAmountRange(TopoModel):
    minimum: Money
    maximum: Money

    @model_validator(mode="after")
    def ordered_range(self) -> RecurringAmountRange:
        if self.minimum.currency != self.maximum.currency:
            raise ValueError("amount range currencies must match")
        if Decimal(self.minimum.amount) > Decimal(self.maximum.amount):
            raise ValueError("amount range minimum must not exceed maximum")
        return self


class RecurringCashflowValue(TopoModel):
    frequency: Literal["weekly", "four_weekly", "monthly", "quarterly", "annual"]
    direction: Literal["inflow", "outflow"]
    expected_period: RecurringExpectedPeriod
    money: Money | None = None
    amount_range: RecurringAmountRange | None = None

    @model_validator(mode="after")
    def exactly_one_amount(self) -> RecurringCashflowValue:
        if (self.money is None) == (self.amount_range is None):
            raise ValueError("exactly one of money and amount_range is required")
        amounts: tuple[Decimal, ...]
        if self.money is not None:
            amounts = (Decimal(self.money.amount),)
        else:
            assert self.amount_range is not None
            amounts = (
                Decimal(self.amount_range.minimum.amount),
                Decimal(self.amount_range.maximum.amount),
            )
        if self.direction == "inflow" and any(amount <= 0 for amount in amounts):
            raise ValueError("inflow amounts must be positive")
        if self.direction == "outflow" and any(amount >= 0 for amount in amounts):
            raise ValueError("outflow amounts must be negative")
        return self


class ValidTime(TopoModel):
    start: date
    end_exclusive: date | None


class EntityRecord(TopoModel):
    id: UUID7
    entity_type: Literal["context", "person", "household", "transaction"]
    module_id: Literal["topo.core", "domain.parties", "domain.cashflow"]
    created_at: AwareDatetime


class AssertionRecord(TopoModel):
    id: UUID7
    subject_ref: Ref
    predicate: NonEmptyString
    object_ref: Ref | None = None
    object_value: ObjectValue | None = None
    valid_time: ValidTime
    recorded_at: AwareDatetime
    knowledge_type: Literal[
        "observed", "user_provided", "inferred", "calculated", "assumed", "projected"
    ]
    verification_status: Literal["confirmed"]
    provenance: tuple[Ref, ...] = Field(min_length=1)
    supersedes: UUID7 | None
    module_data: JsonObject

    @model_validator(mode="after")
    def exactly_one_object(self) -> AssertionRecord:
        if (self.object_ref is None) == (self.object_value is None):
            raise ValueError("exactly one of object_ref and object_value is required")
        return self


class UserStatementEvidenceRecord(TopoModel):
    id: UUID7
    evidence_type: Literal["user_statement"]
    recorded_at: AwareDatetime
    statement_type: Literal[
        "context_initialization", "proposal_confirmation", "proposal_correction"
    ]
    statement: JsonObject | None = None


class SourceReference(TopoModel):
    adapter_id: NonEmptyString
    adapter_version: NonEmptyString
    source_id: NonEmptyString
    record_id: NonEmptyString
    record_checksum: Checksum


class SourceRecordEvidenceRecord(TopoModel):
    id: UUID7
    evidence_type: Literal["source_record"]
    source: SourceReference
    record_path: NonEmptyString
    recorded_at: AwareDatetime
    supersedes: UUID7 | None


type EvidenceRecord = Annotated[
    UserStatementEvidenceRecord | SourceRecordEvidenceRecord,
    Field(discriminator="evidence_type"),
]


class ObjectValue(TopoModel):
    value_type: NonEmptyString
    value: JsonValue


class ProposedAssertion(TopoModel):
    subject_ref: Ref
    predicate: NonEmptyString
    object_ref: Ref | None = None
    object_value: ObjectValue | None = None
    valid_time: ValidTime
    knowledge_type: Literal["inferred"]
    module_data: JsonObject

    @model_validator(mode="after")
    def exactly_one_object(self) -> ProposedAssertion:
        if (self.object_ref is None) == (self.object_value is None):
            raise ValueError("exactly one of object_ref and object_value is required")
        return self


class Producer(TopoModel):
    producer_type: Literal["agent", "rule_module", "source_adapter"]
    producer_id: NonEmptyString
    producer_version: NonEmptyString


class Detection(TopoModel):
    scheme: NonEmptyString
    score: DecimalString


class ProposalDecision(TopoModel):
    outcome: Literal["confirmed", "corrected", "rejected"]
    actor: Actor
    decided_at: AwareDatetime
    mutation_id: UUID7
    assertion_id: UUID7 | None


class ProposalRecord(TopoModel):
    id: UUID7
    proposal_type: Literal["assertion"]
    producer: Producer
    proposed_assertion: ProposedAssertion
    evidence_refs: tuple[Ref, ...] = Field(min_length=1)
    reason_ref: NonEmptyString
    detection: Detection | None = None
    status: Literal["open", "confirmed", "corrected", "rejected", "superseded"]
    created_at: AwareDatetime
    decision: ProposalDecision | None


class CanonicalCollection[RecordT: TopoModel](TopoModel):
    schema_version: Literal["topo.context/0.1"]
    records: tuple[RecordT, ...]


class ModulePin(TopoModel):
    module_id: NonEmptyString
    module_version: NonEmptyString
    checksum: Checksum


class Manifest(TopoModel):
    schema_version: Literal["topo.manifest/0.1"]
    context_id: UUID7
    generation_id: UUID7
    based_on: UUID7 | None
    package_version: Literal["0.1"]
    context_schema_version: Literal["topo.context/0.1"]
    mutation_id: UUID7
    recorded_at: AwareDatetime
    modules: tuple[ModulePin, ...] = Field(min_length=1)
    active_rule_packages: tuple[()] = ()
    files: dict[str, Checksum]


class JournalEntry(TopoModel):
    operation_id: UUID7
    mutation_id: UUID7
    operation: Literal[
        "context.init",
        "source.import",
        "proposal.submit",
        "proposal.confirm",
        "proposal.correct",
        "proposal.reject",
    ]
    actor: Actor
    reason: NonEmptyString
    generation_before: UUID7 | None
    generation_after: UUID7
    recorded_at: AwareDatetime
    result: JsonObject


class Journal(TopoModel):
    schema_version: Literal["topo.journal/0.1"]
    entries: tuple[JournalEntry, ...] = Field(min_length=1)


class ContextInitRequest(TopoModel):
    contract_version: Literal["topo.cli/0.1"]
    package: NonEmptyString
    operation_id: UUID7
    expected_generation: None
    actor: Actor
    reason: NonEmptyString


class ContextInitResult(TopoModel):
    context_id: UUID7
    generation_id: UUID7
    mutation_id: UUID7
    person_id: UUID7
    household_id: UUID7
    membership_assertion_id: UUID7


class InitializationOutcome(TopoModel):
    result: ContextInitResult
    replayed: bool


class Authorization(TopoModel):
    preview_ref: NonEmptyString
    authorized_by: Actor
    authorized_at: AwareDatetime


class MutationRequest(TopoModel):
    contract_version: Literal["topo.cli/0.1"]
    operation_id: UUID7
    context_id: UUID7
    expected_generation: UUID7
    actor: Actor
    reason: NonEmptyString


class SourceAdapter(TopoModel):
    adapter_id: NonEmptyString
    adapter_version: NonEmptyString


class SourceClassification(TopoModel):
    category: str
    rule_version: str
    explanation: str


class SourceImportRecord(TopoModel):
    source_id: NonEmptyString
    record_id: NonEmptyString
    booking_date: date
    money: Money
    description: str
    source_classification: SourceClassification | None = None


class SourceImportRequest(MutationRequest):
    adapter: SourceAdapter
    records: tuple[SourceImportRecord, ...]
    authorization: Authorization | None

    @model_validator(mode="after")
    def authorized_unique_records(self) -> SourceImportRequest:
        if (
            self.actor.actor_type != "source_adapter"
            or self.actor.actor_id != self.adapter.adapter_id
        ):
            raise ValueError("source import must be performed by its source adapter")
        identities = tuple(
            (record.source_id, record.record_id) for record in self.records
        )
        if len(identities) != len(set(identities)):
            raise ValueError("source import records must have unique source identities")
        return self


class AnalysisScope(TopoModel):
    scope_type: Literal["person", "household"]
    entity_id: UUID7


class DiscoveryRequest(TopoModel):
    contract_version: Literal["topo.cli/0.1"]
    context_id: UUID7
    analysis_scope: AnalysisScope
    as_of_date: date


class DiscoveryOutcome(TopoModel):
    context_id: UUID7
    generation_id: UUID7
    result: JsonObject


class ProposalSubmitRequest(MutationRequest):
    proposal: ProposedProposal


class ProposedProposal(TopoModel):
    proposal_type: Literal["assertion"]
    producer: Producer
    proposed_assertion: ProposedAssertion
    evidence_refs: tuple[Ref, ...] = Field(min_length=1)
    reason_ref: NonEmptyString
    detection: Detection | None = None


class ProposalDecisionRequest(MutationRequest):
    proposal_ref: UUID7


class ProposalConfirmRequest(ProposalDecisionRequest):
    authorization: Authorization | None


class Correction(TopoModel):
    object_ref: Ref | None = None
    object_value: ObjectValue | None = None
    reason: NonEmptyString

    @model_validator(mode="after")
    def exactly_one_object(self) -> Correction:
        if (self.object_ref is None) == (self.object_value is None):
            raise ValueError("exactly one of object_ref and object_value is required")
        return self


class ProposalCorrectRequest(ProposalDecisionRequest):
    authorization: Authorization | None
    correction: Correction


class ProposalRejectRequest(ProposalDecisionRequest):
    pass


class MutationOutcome(TopoModel):
    context_id: UUID7
    generation_before: UUID7
    generation_after: UUID7
    outcome: Outcome
    result: JsonObject
    replayed: bool = False


class CommandDescriptor(TopoModel):
    command: NonEmptyString
    input_schema_ref: NonEmptyString
    output_schema_ref: NonEmptyString


class DescribeResult(TopoModel):
    supported_contract_versions: tuple[Literal["topo.cli/0.1"], ...]
    commands: tuple[CommandDescriptor, ...]


class SchemaResult(TopoModel):
    command: NonEmptyString
    input_schema_ref: NonEmptyString
    output_schema_ref: NonEmptyString
    input_schema: JsonObject
    output_schema: JsonObject


class Diagnostic(TopoModel):
    code: NonEmptyString
    message_key: NonEmptyString
    severity: Literal["info", "warning", "error"]
    path: str
    params: JsonObject
    retryable: bool
    effect: Literal["none"] = "none"
    related_refs: tuple[Ref, ...] = ()


class Trace(TopoModel):
    normalized_request: JsonObject
    refs: tuple[Ref, ...] = ()


class ResponseEnvelope(TopoModel):
    contract_version: Literal["topo.cli/0.1"]
    command: NonEmptyString
    operation_id: UUID7 | None
    context_id: UUID7 | None
    generation_before: UUID7 | None
    generation_after: UUID7 | None
    outcome: Outcome
    result: JsonObject
    diagnostics: tuple[Diagnostic, ...] = ()
    next_actions: tuple[JsonObject, ...] = ()
    trace: Trace


def model_to_json_object(model: BaseModel) -> JsonObject:
    return cast(JsonObject, model.model_dump(mode="json"))
