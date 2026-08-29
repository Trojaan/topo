from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from test_net_worth_journey import add_value, initialized_with_evidence
from test_normalized_cashflow_journey import recurring_value
from test_realized_cashflow_journey import confirm_assertion, parse_json, run_topo


def _component(view: dict[str, Any], name: str) -> dict[str, Any]:
    return cast(dict[str, Any], view[name])


def test_explicit_scenario_compares_cashflow_one_offs_and_net_worth_without_mutation(
    tmp_path: Path,
) -> None:
    package, initialized, generation, evidence_id, account_id = (
        initialized_with_evidence(tmp_path)
    )
    household_id = str(initialized["result"]["household_id"])
    generation = confirm_assertion(
        package,
        initialized,
        generation,
        sequence=1101,
        subject_id=account_id,
        predicate="domain.parties/household_allocation",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2028-01-01",
        object_ref=household_id,
    )
    for sequence, amount, direction in (
        (1102, "2000.00", "inflow"),
        (1103, "-1100.00", "outflow"),
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
            end_exclusive="2028-01-01",
            object_value=recurring_value("monthly", amount, direction=direction),
        )
    for sequence, subject, predicate, amount, interest, basis in (
        (
            1104,
            account_id,
            "domain.accounts/balance",
            "30000.00",
            "account:main",
            "account_balance",
        ),
        (
            1105,
            household_id,
            "jurisdiction.nl/valuation/woz",
            "350000.00",
            "asset:home",
            "asset_value",
        ),
        (
            1106,
            household_id,
            "domain.debts/balance",
            "240000.00",
            "debt:mortgage",
            "debt_balance",
        ),
    ):
        generation = add_value(
            package,
            initialized,
            generation,
            evidence_id,
            sequence=sequence,
            subject_id=subject,
            predicate=predicate,
            amount=amount,
            currency="EUR",
            interest=interest,
            basis=basis,
            start="2026-01-01",
            end_exclusive="2028-01-01",
        )

    scenario_id = "0198f1a0-0000-7000-8000-000000001100"
    assumptions = [
        {
            "assumption_type": "recurring_cashflow_change",
            "target_ref": {"ref_type": "entity", "id": household_id},
            "change": "add",
            "money": {"amount": "500.00", "currency": "EUR"},
            "effective_date": "2027-01-01",
            "reason": "Explicitly model lower monthly household spending",
        },
        {
            "assumption_type": "one_off_cashflow",
            "target_ref": {"ref_type": "entity", "id": account_id},
            "direction": "outflow",
            "money": {"amount": "1000.00", "currency": "EUR"},
            "effective_date": "2027-03-01",
            "reason": "Explicitly model a one-off household payment",
        },
        {
            "assumption_type": "value_override",
            "target_ref": {"ref_type": "entity", "id": account_id},
            "money": {"amount": "36000.00", "currency": "EUR"},
            "effective_date": "2027-12-31",
            "reason": "Explicit savings-account value at the scenario date",
        },
    ]
    request = {
        "contract_version": "topo.cli/0.1",
        "analysis_id": "analysis.scenario_comparison",
        "analysis_contract_version": "0.1",
        "context_id": initialized["context_id"],
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": household_id,
        },
        "as_of_date": "2027-12-31",
        "period": None,
        "reporting_currency": {
            "currency": "EUR",
            "allowed_rate_assertion_refs": [],
        },
        "scenario": {"scenario_id": scenario_id, "assumptions": assumptions},
    }

    cashflow_only_request = deepcopy(request)
    cashflow_only_request["scenario"]["assumptions"] = assumptions[:1]
    cashflow_only = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request=cashflow_only_request,
    )
    assert cashflow_only.returncode == 0, cashflow_only.stderr
    cashflow_only_result = parse_json(cashflow_only)["result"]
    assert _component(cashflow_only_result["scenario"], "net_worth")["value"] == {
        "amount": "140000.00",
        "currency": "EUR",
    }
    assert _component(cashflow_only_result["delta"], "net_worth")["value"] == {
        "amount": "0.00",
        "currency": "EUR",
    }
    assert {
        item["code"]
        for item in _component(cashflow_only_result["scenario"], "net_worth")[
            "warnings"
        ]
    } == {"CASHFLOW_DESTINATION_NOT_MODELED"}

    process = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request=request,
    )

    assert process.returncode == 0, process.stderr
    body = parse_json(process)
    result = body["result"]
    assert result["knowledge_type"] == "projected"
    assert result["scenario_id"] == scenario_id
    assert _component(result["baseline"], "normalized_monthly_cashflow")["value"] == {
        "amount": "900.00",
        "currency": "EUR",
    }
    assert _component(result["scenario"], "normalized_monthly_cashflow")["value"] == {
        "amount": "1400.00",
        "currency": "EUR",
    }
    assert _component(result["delta"], "normalized_monthly_cashflow")["value"] == {
        "amount": "500.00",
        "currency": "EUR",
    }
    assert _component(result["baseline"], "one_off_cashflow")["value"] == {
        "amount": "0.00",
        "currency": "EUR",
    }
    assert _component(result["scenario"], "one_off_cashflow")["value"] == {
        "amount": "-1000.00",
        "currency": "EUR",
    }
    assert _component(result["baseline"], "net_worth")["value"] == {
        "amount": "140000.00",
        "currency": "EUR",
    }
    assert _component(result["scenario"], "net_worth")["value"] == {
        "amount": "146000.00",
        "currency": "EUR",
    }
    assert _component(result["delta"], "net_worth")["value"] == {
        "amount": "6000.00",
        "currency": "EUR",
    }
    assert {
        item["code"] for item in _component(result["scenario"], "net_worth")["warnings"]
    } == {"CASHFLOW_DESTINATION_NOT_MODELED"}
    assert _component(result["scenario"], "net_worth")["assumptions"] == assumptions
    assert body["generation_before"] == generation == body["generation_after"]


def test_unbounded_scenario_assumption_is_rejected_without_effect(
    tmp_path: Path,
) -> None:
    package = tmp_path / "invalid-scenario.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    household_id = initialized["result"]["household_id"]
    process = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request={
            "contract_version": "topo.cli/0.1",
            "analysis_id": "analysis.scenario_comparison",
            "analysis_contract_version": "0.1",
            "context_id": initialized["context_id"],
            "analysis_scope": {
                "scope_type": "household",
                "entity_id": household_id,
            },
            "as_of_date": "2027-12-31",
            "period": None,
            "reporting_currency": {
                "currency": "EUR",
                "allowed_rate_assertion_refs": [],
            },
            "scenario": {
                "scenario_id": "0198f1a0-0000-7000-8000-000000001101",
                "assumptions": [
                    {
                        "assumption_type": "percentage_growth_formula",
                        "target_ref": {"ref_type": "entity", "id": household_id},
                        "percentage": "8.0",
                        "formula": "compound_annually",
                        "effective_date": "2027-01-01",
                        "reason": "Invent a return",
                    }
                ],
            },
        },
    )

    assert process.returncode == 2
    body = parse_json(process)
    assert body["outcome"] == "rejected"
    assert body["diagnostics"][0]["effect"] == "none"
