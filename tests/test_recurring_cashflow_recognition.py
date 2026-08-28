from __future__ import annotations

from datetime import date

import pytest

from topo.recognition import TransactionObservation, recognize_recurring_cashflows

SUBJECT_ID = "0198f1a0-0000-7002-8000-000000000001"


def observation(index: int, booking_date: date, amount: str) -> TransactionObservation:
    suffix = f"{index:012d}"
    return TransactionObservation(
        transaction_id=f"0198f1a0-0000-7000-8000-{suffix}",
        evidence_id=f"0198f1a0-0000-7001-8000-{suffix}",
        booking_date=booking_date,
        amount=amount,
        currency="EUR",
        description="ACME recurring payment",
    )


@pytest.mark.parametrize(
    ("dates", "frequency"),
    [
        ((date(2026, 7, 1), date(2026, 7, 8), date(2026, 7, 15)), "weekly"),
        (
            (date(2026, 5, 1), date(2026, 5, 29), date(2026, 6, 26)),
            "four_weekly",
        ),
        ((date(2026, 5, 25), date(2026, 6, 25), date(2026, 7, 25)), "monthly"),
        ((date(2026, 1, 5), date(2026, 4, 5), date(2026, 7, 5)), "quarterly"),
        ((date(2025, 7, 5), date(2026, 7, 5)), "annual"),
    ],
)
def test_recognizes_supported_frequencies(
    dates: tuple[date, ...], frequency: str
) -> None:
    result = recognize_recurring_cashflows(
        tuple(
            observation(index, value, "3200.00") for index, value in enumerate(dates)
        ),
        subject_id=SUBJECT_ID,
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.frequency == frequency
    assert candidate.money is not None
    assert candidate.money.amount == "3200.00"
    assert candidate.amount_range is None
    assert len(candidate.evidence_refs) == len(dates)
    assert candidate.expected_period.start_date > dates[-1]
    assert candidate.detection.scheme == "recurring_pattern/0.1"


def test_variable_amounts_keep_a_range_and_explain_deviations() -> None:
    result = recognize_recurring_cashflows(
        (
            observation(1, date(2026, 5, 25), "1200.00"),
            observation(2, date(2026, 6, 25), "1210.00"),
            observation(3, date(2026, 7, 25), "1190.00"),
        ),
        subject_id=SUBJECT_ID,
    )

    candidate = result.candidates[0]
    assert candidate.money is None
    assert candidate.amount_range is not None
    assert candidate.amount_range.minimum.amount == "1190.00"
    assert candidate.amount_range.maximum.amount == "1210.00"
    assert {deviation.kind for deviation in candidate.deviations} == {
        "amount_variation"
    }
    assert candidate.proposal.proposed_assertion.object_value is not None
    assert candidate.proposal.proposed_assertion.object_value.value == {
        "frequency": "monthly",
        "direction": "inflow",
        "amount_range": {
            "minimum": {"amount": "1190.00", "currency": "EUR"},
            "maximum": {"amount": "1210.00", "currency": "EUR"},
        },
        "expected_period": {
            "start_date": "2026-08-20",
            "end_exclusive": "2026-08-31",
        },
    }


def test_insufficient_monthly_history_is_attention_not_candidate() -> None:
    result = recognize_recurring_cashflows(
        (
            observation(1, date(2026, 6, 25), "3200.00"),
            observation(2, date(2026, 7, 25), "3200.00"),
        ),
        subject_id=SUBJECT_ID,
    )

    assert result.candidates == ()
    assert len(result.attention_items) == 1
    attention = result.attention_items[0]
    assert attention.code == "INSUFFICIENT_PATTERN_HISTORY"
    assert attention.frequency == "monthly"
    assert len(attention.related_refs) == 2
