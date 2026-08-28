from __future__ import annotations

import hashlib
import re
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from typing import Literal

from pydantic import field_serializer

from topo.models import (
    UUID7,
    Currency,
    DecimalString,
    Detection,
    JsonObject,
    Money,
    NonEmptyString,
    ObjectValue,
    Producer,
    ProposedAssertion,
    ProposedProposal,
    RecurringAmountRange,
    RecurringExpectedPeriod,
    Ref,
    TopoModel,
    ValidTime,
)

Frequency = Literal["weekly", "four_weekly", "monthly", "quarterly", "annual"]
Direction = Literal["inflow", "outflow"]

PRODUCER_ID = "domain.cashflow.recognition"
PRODUCER_VERSION = "0.1.0"
RULE_VERSION = "recurring-pattern/0.1.0"


class TransactionObservation(TopoModel):
    transaction_id: UUID7
    evidence_id: UUID7
    booking_date: date
    amount: DecimalString
    currency: Currency
    description: str


class PatternDeviation(TopoModel):
    transaction_ref: Ref
    kind: Literal["amount_variation"]
    observed_money: Money


class RecurringPatternCandidate(TopoModel):
    candidate_id: NonEmptyString
    proposal_type: Literal["recurring_cashflow"]
    frequency: Frequency
    direction: Direction
    expected_period: RecurringExpectedPeriod
    money: Money | None
    amount_range: RecurringAmountRange | None
    evidence_refs: tuple[Ref, ...]
    transaction_refs: tuple[Ref, ...]
    deviations: tuple[PatternDeviation, ...]
    producer: NonEmptyString
    rule_version: NonEmptyString
    detection: Detection
    proposal: ProposedProposal

    @field_serializer("proposal")
    def serialize_proposal(self, proposal: ProposedProposal) -> dict[str, object]:
        payload = proposal.model_dump(mode="json")
        assertion = payload["proposed_assertion"]
        assert isinstance(assertion, dict)
        for field in ("object_ref", "object_value"):
            if assertion.get(field) is None:
                assertion.pop(field, None)
        return payload


class PatternAttentionItem(TopoModel):
    code: Literal["INSUFFICIENT_PATTERN_HISTORY"]
    message_key: Literal["attention.insufficient_pattern_history"]
    frequency: Frequency
    required_observations: int
    actual_observations: int
    related_refs: tuple[Ref, ...]


class RecognitionResult(TopoModel):
    candidates: tuple[RecurringPatternCandidate, ...]
    attention_items: tuple[PatternAttentionItem, ...]


@dataclass(frozen=True)
class _FrequencyRule:
    frequency: Frequency
    months: int
    days: int
    tolerance_days: int
    minimum_observations: int


_RULES = (
    _FrequencyRule(
        "weekly", months=0, days=7, tolerance_days=2, minimum_observations=3
    ),
    _FrequencyRule(
        "four_weekly", months=0, days=28, tolerance_days=3, minimum_observations=3
    ),
    _FrequencyRule(
        "monthly", months=1, days=0, tolerance_days=5, minimum_observations=3
    ),
    _FrequencyRule(
        "quarterly", months=3, days=0, tolerance_days=10, minimum_observations=3
    ),
    _FrequencyRule(
        "annual", months=12, days=0, tolerance_days=30, minimum_observations=2
    ),
)


def _normalize_description(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _expected_after(value: date, rule: _FrequencyRule) -> date:
    if rule.months:
        return _add_months(value, rule.months)
    return value + timedelta(days=rule.days)


def _interval_errors(
    observations: tuple[TransactionObservation, ...], rule: _FrequencyRule
) -> tuple[int, ...]:
    return tuple(
        abs((later.booking_date - _expected_after(earlier.booking_date, rule)).days)
        for earlier, later in pairwise(observations)
    )


def _matching_rule(
    observations: tuple[TransactionObservation, ...],
) -> tuple[_FrequencyRule, tuple[int, ...]] | None:
    matches: list[tuple[int, _FrequencyRule, tuple[int, ...]]] = []
    for rule in _RULES:
        errors = _interval_errors(observations, rule)
        if errors and all(error <= rule.tolerance_days for error in errors):
            matches.append((sum(errors), rule, errors))
    if not matches:
        return None
    _, rule, errors = min(matches, key=lambda item: (item[0], item[1].tolerance_days))
    return rule, errors


def _score(
    observations: tuple[TransactionObservation, ...],
    rule: _FrequencyRule,
    interval_errors: tuple[int, ...],
) -> str:
    interval_penalty = sum(
        Decimal(error) / Decimal(rule.tolerance_days + 1) for error in interval_errors
    ) / Decimal(len(interval_errors))
    amounts = tuple(abs(Decimal(item.amount)) for item in observations)
    average = sum(amounts) / Decimal(len(amounts))
    amount_penalty = Decimal(0)
    if average:
        amount_penalty = min((max(amounts) - min(amounts)) / average, Decimal(1))
    score = max(
        Decimal(0),
        Decimal(1)
        - Decimal("0.7") * interval_penalty
        - Decimal("0.3") * amount_penalty,
    )
    return format(score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def _candidate_id(
    observations: tuple[TransactionObservation, ...], frequency: Frequency
) -> str:
    identity = "|".join(
        (frequency, *(item.evidence_id for item in observations))
    ).encode()
    return "candidate:" + hashlib.sha256(identity).hexdigest()


def _money_shape(
    observations: tuple[TransactionObservation, ...],
) -> tuple[Money | None, RecurringAmountRange | None, tuple[PatternDeviation, ...]]:
    amounts = tuple(Decimal(item.amount) for item in observations)
    if len(set(amounts)) == 1:
        return (
            Money(amount=observations[0].amount, currency=observations[0].currency),
            None,
            (),
        )
    minimum_index = amounts.index(min(amounts))
    maximum_index = amounts.index(max(amounts))
    amount_range = RecurringAmountRange(
        minimum=Money(
            amount=observations[minimum_index].amount,
            currency=observations[minimum_index].currency,
        ),
        maximum=Money(
            amount=observations[maximum_index].amount,
            currency=observations[maximum_index].currency,
        ),
    )
    deviations = tuple(
        PatternDeviation(
            transaction_ref=Ref(ref_type="entity", id=item.transaction_id),
            kind="amount_variation",
            observed_money=Money(amount=item.amount, currency=item.currency),
        )
        for item in observations
    )
    return None, amount_range, deviations


def _candidate(
    observations: tuple[TransactionObservation, ...],
    *,
    subject_id: str,
    rule: _FrequencyRule,
    interval_errors: tuple[int, ...],
) -> RecurringPatternCandidate:
    expected = _expected_after(observations[-1].booking_date, rule)
    expected_period = RecurringExpectedPeriod(
        start_date=expected - timedelta(days=rule.tolerance_days),
        end_exclusive=expected + timedelta(days=rule.tolerance_days + 1),
    )
    money, amount_range, deviations = _money_shape(observations)
    direction: Direction = (
        "inflow" if Decimal(observations[0].amount) > 0 else "outflow"
    )
    candidate_id = _candidate_id(observations, rule.frequency)
    evidence_refs = tuple(
        Ref(ref_type="evidence", id=item.evidence_id) for item in observations
    )
    transaction_refs = tuple(
        Ref(ref_type="entity", id=item.transaction_id) for item in observations
    )
    amount_value: JsonObject
    if money is not None:
        amount_value = {"money": money.model_dump(mode="json")}
    else:
        assert amount_range is not None
        amount_value = {"amount_range": amount_range.model_dump(mode="json")}
    recurring_value: JsonObject = {
        "frequency": rule.frequency,
        "direction": direction,
        **amount_value,
        "expected_period": expected_period.model_dump(mode="json"),
    }
    detection = Detection(
        scheme="recurring_pattern/0.1",
        score=_score(observations, rule, interval_errors),
    )
    proposal = ProposedProposal(
        proposal_type="assertion",
        producer=Producer(
            producer_type="rule_module",
            producer_id=PRODUCER_ID,
            producer_version=PRODUCER_VERSION,
        ),
        proposed_assertion=ProposedAssertion(
            subject_ref=Ref(ref_type="entity", id=subject_id),
            predicate="domain.cashflow/recurring_cashflow",
            object_value=ObjectValue(
                value_type="recurring_cashflow",
                value=recurring_value,
            ),
            valid_time=ValidTime(
                start=observations[0].booking_date, end_exclusive=None
            ),
            knowledge_type="inferred",
            module_data={
                "candidate_id": candidate_id,
                "rule_version": RULE_VERSION,
                "transaction_refs": [
                    item.model_dump(mode="json") for item in transaction_refs
                ],
                "deviations": [item.model_dump(mode="json") for item in deviations],
            },
        ),
        evidence_refs=evidence_refs,
        reason_ref=f"recognition:{RULE_VERSION}:{candidate_id}",
        detection=detection,
    )
    return RecurringPatternCandidate(
        candidate_id=candidate_id,
        proposal_type="recurring_cashflow",
        frequency=rule.frequency,
        direction=direction,
        expected_period=expected_period,
        money=money,
        amount_range=amount_range,
        evidence_refs=evidence_refs,
        transaction_refs=transaction_refs,
        deviations=deviations,
        producer=f"{PRODUCER_ID}/{PRODUCER_VERSION}",
        rule_version=RULE_VERSION,
        detection=detection,
        proposal=proposal,
    )


def recognize_recurring_cashflows(
    observations: tuple[TransactionObservation, ...], *, subject_id: str
) -> RecognitionResult:
    grouped: defaultdict[tuple[Direction, str, str], list[TransactionObservation]] = (
        defaultdict(list)
    )
    for item in observations:
        amount = Decimal(item.amount)
        if not amount:
            continue
        direction: Direction = "inflow" if amount > 0 else "outflow"
        grouped[
            (direction, item.currency, _normalize_description(item.description))
        ].append(item)

    candidates: list[RecurringPatternCandidate] = []
    attention_items: list[PatternAttentionItem] = []
    for grouped_observations in grouped.values():
        ordered = tuple(
            sorted(grouped_observations, key=lambda item: item.booking_date)
        )
        if len(ordered) < 2:
            continue
        match = _matching_rule(ordered)
        if match is None:
            continue
        rule, errors = match
        if len(ordered) < rule.minimum_observations:
            attention_items.append(
                PatternAttentionItem(
                    code="INSUFFICIENT_PATTERN_HISTORY",
                    message_key="attention.insufficient_pattern_history",
                    frequency=rule.frequency,
                    required_observations=rule.minimum_observations,
                    actual_observations=len(ordered),
                    related_refs=tuple(
                        Ref(ref_type="entity", id=item.transaction_id)
                        for item in ordered
                    ),
                )
            )
            continue
        candidates.append(
            _candidate(
                ordered,
                subject_id=subject_id,
                rule=rule,
                interval_errors=errors,
            )
        )

    return RecognitionResult(
        candidates=tuple(sorted(candidates, key=lambda item: item.candidate_id)),
        attention_items=tuple(
            sorted(
                attention_items,
                key=lambda item: tuple(ref.id for ref in item.related_refs),
            )
        ),
    )
