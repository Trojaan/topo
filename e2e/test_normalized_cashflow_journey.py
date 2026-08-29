from __future__ import annotations

from pathlib import Path
from typing import Any

from test_realized_cashflow_journey import (
    confirm_assertion,
    import_transactions,
    parse_json,
    run_topo,
)


def recurring_value(
    frequency: str,
    amount: str,
    *,
    direction: str = "inflow",
) -> dict[str, Any]:
    return {
        "value_type": "recurring_cashflow",
        "value": {
            "frequency": frequency,
            "direction": direction,
            "expected_period": {
                "start_date": "2026-08-01",
                "end_exclusive": "2026-09-01",
            },
            "money": {"amount": amount, "currency": "EUR"},
            "amount_range": None,
        },
    }


def recurring_range_value(
    frequency: str,
    minimum: str,
    maximum: str,
    *,
    direction: str,
    typical: str | None,
) -> dict[str, Any]:
    currency = "EUR"
    return {
        "value_type": "recurring_cashflow",
        "value": {
            "frequency": frequency,
            "direction": direction,
            "expected_period": {
                "start_date": "2026-08-01",
                "end_exclusive": "2026-09-01",
            },
            "money": None,
            "amount_range": {
                "minimum": {"amount": minimum, "currency": currency},
                "maximum": {"amount": maximum, "currency": currency},
            },
            "typical_money": (
                None if typical is None else {"amount": typical, "currency": currency}
            ),
        },
    }


def analyze_request(initialized: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": "topo.cli/0.1",
        "analysis_id": "analysis.normalized_monthly_cashflow",
        "analysis_contract_version": "0.1",
        "context_id": initialized["context_id"],
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": initialized["result"]["household_id"],
        },
        "as_of_date": "2026-08-29",
        "period": None,
        "reporting_currency": {
            "currency": "EUR",
            "allowed_rate_assertion_refs": [],
        },
        "scenario": None,
    }


def submit_open_recurring(
    package: Path,
    initialized: dict[str, Any],
    generation: str,
    evidence_id: str,
    value: dict[str, Any],
) -> str:
    submitted = run_topo(
        "proposal",
        "submit",
        "--package",
        str(package),
        "--json",
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000000908",
            "context_id": initialized["context_id"],
            "expected_generation": generation,
            "actor": {"actor_type": "agent", "actor_id": "local-agent"},
            "reason": "Keep an unconfirmed recurring candidate open",
            "proposal": {
                "proposal_type": "assertion",
                "producer": {
                    "producer_type": "agent",
                    "producer_id": "local-agent",
                    "producer_version": "0.1.0",
                },
                "proposed_assertion": {
                    "subject_ref": {
                        "ref_type": "entity",
                        "id": initialized["result"]["household_id"],
                    },
                    "predicate": "domain.cashflow/recurring_cashflow",
                    "object_value": value,
                    "valid_time": {
                        "start": "2026-01-01",
                        "end_exclusive": "2027-01-01",
                    },
                    "knowledge_type": "inferred",
                    "module_data": {},
                },
                "evidence_refs": [{"ref_type": "evidence", "id": evidence_id}],
                "reason_ref": "normalized-test:open-candidate",
                "detection": None,
            },
        },
    )
    assert submitted.returncode == 0, submitted.stderr
    return str(parse_json(submitted)["generation_after"])


def test_confirmed_current_fixed_cashflows_are_normalized_with_exact_factors(
    tmp_path: Path,
) -> None:
    package = tmp_path / "normalized-fixed.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    imported = import_transactions(
        package,
        initialized,
        [
            {
                "source_id": "main",
                "record_id": "proof",
                "booking_date": "2026-08-01",
                "money": {"amount": "1.00", "currency": "EUR"},
                "description": "Synthetic evidence",
            }
        ],
    )
    generation = imported["generation_after"]
    evidence_id = imported["result"]["evidence_refs"][0]["id"]
    household_id = initialized["result"]["household_id"]
    assertion_ids: list[str] = []

    for sequence, frequency in enumerate(
        ("weekly", "four_weekly", "monthly", "quarterly", "annual"),
        start=901,
    ):
        generation = confirm_assertion(
            package,
            initialized,
            generation,
            sequence=sequence,
            subject_id=household_id,
            predicate="domain.cashflow/recurring_cashflow",
            evidence_id=evidence_id,
            start="2026-01-01",
            end_exclusive="2027-01-01",
            object_value=recurring_value(frequency, "100.00"),
        )

    generation = confirm_assertion(
        package,
        initialized,
        generation,
        sequence=906,
        subject_id=household_id,
        predicate="domain.cashflow/recurring_cashflow",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2027-01-01",
        object_value=recurring_value("monthly", "-300.00", direction="outflow"),
    )
    generation = confirm_assertion(
        package,
        initialized,
        generation,
        sequence=907,
        subject_id=household_id,
        predicate="domain.cashflow/recurring_cashflow",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2026-08-01",
        object_value=recurring_value("monthly", "999.00"),
    )
    generation = submit_open_recurring(
        package,
        initialized,
        generation,
        evidence_id,
        recurring_value("monthly", "777.00"),
    )

    analyzed = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request=analyze_request(initialized),
    )

    assert analyzed.returncode == 0, analyzed.stderr
    response = parse_json(analyzed)
    assert response["generation_before"] == generation
    result = response["result"]
    assert result["period"] is None
    components = {item["component_id"]: item for item in result["components"]}
    assert components["normalized/income"]["value"] == {
        "amount": "683.33",
        "currency": "EUR",
    }
    assert components["normalized/fixed_expense"]["value"] == {
        "amount": "300.00",
        "currency": "EUR",
    }
    assert components["normalized/net"]["value"] == {
        "amount": "383.33",
        "currency": "EUR",
    }
    assert components["normalized/income"]["status"] == "complete"
    used = components["normalized/income"]["used_assertion_refs"]
    assert len(used) == 5
    assertion_ids.extend(ref["id"] for ref in used)
    assert len(set(assertion_ids)) == 5
    assert components["normalized/income"]["assumptions"] == []
    weekly_step = next(
        step
        for step in components["normalized/income"]["calculation_steps"]
        if step.get("factor") == {"multiply_by": "52", "divide_by": "12"}
    )
    assert weekly_step["unrounded_result"] == {
        "amount": "433.3333333333333333333333333",
        "currency": "EUR",
    }


def test_ranges_keep_bounds_and_need_every_explicit_typical_for_expected_total(
    tmp_path: Path,
) -> None:
    package = tmp_path / "normalized-ranges.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    imported = import_transactions(
        package,
        initialized,
        [
            {
                "source_id": "main",
                "record_id": "proof",
                "booking_date": "2026-08-01",
                "money": {"amount": "1.00", "currency": "EUR"},
                "description": "Synthetic evidence",
            }
        ],
    )
    generation = imported["generation_after"]
    evidence_id = imported["result"]["evidence_refs"][0]["id"]
    household_id = initialized["result"]["household_id"]
    for sequence, value in (
        (
            921,
            recurring_range_value(
                "monthly", "90.00", "110.00", direction="inflow", typical="100.00"
            ),
        ),
        (
            922,
            recurring_range_value(
                "quarterly", "270.00", "330.00", direction="inflow", typical=None
            ),
        ),
        (
            923,
            recurring_range_value(
                "monthly",
                "-220.00",
                "-180.00",
                direction="outflow",
                typical="-200.00",
            ),
        ),
    ):
        generation = confirm_assertion(
            package,
            initialized,
            generation,
            sequence=sequence,
            subject_id=household_id,
            predicate="domain.cashflow/recurring_cashflow",
            evidence_id=evidence_id,
            start="2026-01-01",
            end_exclusive="2027-01-01",
            object_value=value,
        )

    analyzed = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request=analyze_request(initialized),
    )

    assert analyzed.returncode == 0, analyzed.stderr
    components = {
        item["component_id"]: item
        for item in parse_json(analyzed)["result"]["components"]
    }
    variable_income = components["normalized/variable_income"]
    assert variable_income["minimum_value"]["amount"] == "180.00"
    assert variable_income["maximum_value"]["amount"] == "220.00"
    assert "expected_value" not in variable_income
    assert "value" not in variable_income
    variable_expense = components["normalized/variable_expense"]
    assert variable_expense["minimum_value"]["amount"] == "180.00"
    assert variable_expense["maximum_value"]["amount"] == "220.00"
    assert variable_expense["expected_value"]["amount"] == "200.00"
    net = components["normalized/net"]
    assert net["minimum_value"]["amount"] == "-40.00"
    assert net["maximum_value"]["amount"] == "40.00"
    assert "expected_value" not in net
    assert net["status"] == "complete"
    assert len(variable_income["used_assertion_refs"]) == 2
