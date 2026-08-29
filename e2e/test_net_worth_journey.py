from __future__ import annotations

from pathlib import Path
from typing import Any

from test_realized_cashflow_journey import (
    confirm_assertion,
    import_transactions,
    parse_json,
    run_topo,
)


def money(amount: str, currency: str) -> dict[str, Any]:
    return {
        "value_type": "money",
        "value": {"amount": amount, "currency": currency},
    }


def analyze_request(
    initialized: dict[str, Any], reporting_currency: str = "EUR"
) -> dict[str, Any]:
    return {
        "contract_version": "topo.cli/0.1",
        "analysis_id": "analysis.net_worth",
        "analysis_contract_version": "0.1",
        "context_id": initialized["context_id"],
        "analysis_scope": {
            "scope_type": "household",
            "entity_id": initialized["result"]["household_id"],
        },
        "as_of_date": "2026-08-25",
        "period": None,
        "reporting_currency": {
            "currency": reporting_currency,
            "allowed_rate_assertion_refs": [],
        },
        "scenario": None,
    }


def initialized_with_evidence(
    tmp_path: Path,
) -> tuple[Path, dict[str, Any], str, str, str]:
    package = tmp_path / "net-worth.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    imported = import_transactions(
        package,
        initialized,
        [
            {
                "source_id": "main",
                "record_id": "synthetic-proof",
                "booking_date": "2026-08-25",
                "money": {"amount": "1.00", "currency": "EUR"},
                "description": "Synthetic net-worth evidence",
            }
        ],
    )
    return (
        package,
        initialized,
        str(imported["generation_after"]),
        str(imported["result"]["evidence_refs"][0]["id"]),
        str(imported["result"]["account_refs"][0]["id"]),
    )


def add_value(
    package: Path,
    initialized: dict[str, Any],
    generation: str,
    evidence_id: str,
    *,
    sequence: int,
    subject_id: str,
    predicate: str,
    amount: str,
    currency: str,
    interest: str,
    basis: str,
    start: str = "2026-08-25",
    end_exclusive: str = "2027-01-01",
) -> str:
    return confirm_assertion(
        package,
        initialized,
        generation,
        sequence=sequence,
        subject_id=subject_id,
        predicate=predicate,
        evidence_id=evidence_id,
        start=start,
        end_exclusive=end_exclusive,
        object_value=money(amount, currency),
        module_data={
            "economic_interest_ref": interest,
            "valuation_basis": basis,
            **(
                {"valuation_date": "2026-01-01"}
                if predicate == "jurisdiction.nl/valuation/woz"
                else {}
            ),
        },
    )


def components(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["component_id"]: item for item in body["result"]["components"]}


def test_net_worth_sums_each_interest_once_and_keeps_restricted_pension_separate(
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
        sequence=1001,
        subject_id=account_id,
        predicate="domain.parties/household_allocation",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2027-01-01",
        object_ref=household_id,
    )
    values = (
        (
            1002,
            account_id,
            "domain.accounts/balance",
            "30000.00",
            "account:main",
            "account_balance",
        ),
        (
            1003,
            household_id,
            "jurisdiction.nl/valuation/woz",
            "350000.00",
            "asset:home",
            "asset_value",
        ),
        (
            1004,
            household_id,
            "domain.debts/balance",
            "120000.00",
            "debt:mortgage-a",
            "debt_balance",
        ),
        (
            1005,
            household_id,
            "domain.debts/balance",
            "120000.00",
            "debt:mortgage-b",
            "debt_balance",
        ),
        (
            1006,
            household_id,
            "domain.pensions/value",
            "50000.00",
            "pension:employer",
            "pension_value",
        ),
        (
            1007,
            account_id,
            "domain.accounts/balance",
            "30000.00",
            "account:main",
            "account_balance",
        ),
    )
    for sequence, subject, predicate, amount, interest, basis in values:
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
        )
    process = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request=analyze_request(initialized),
    )
    assert process.returncode == 0, process.stderr
    body = parse_json(process)
    result = components(body)
    assert result["net_worth/EUR"]["status"] == "complete"
    assert result["net_worth/EUR"]["value"] == {
        "amount": "140000.00",
        "currency": "EUR",
    }
    assert result["net_worth/restricted_pension/EUR"]["value"] == {
        "amount": "50000.00",
        "currency": "EUR",
    }
    assert body["generation_before"] == generation == body["generation_after"]


def test_original_currency_subtotals_survive_a_missing_exchange_rate(
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
        sequence=1010,
        subject_id=account_id,
        predicate="domain.parties/household_allocation",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2027-01-01",
        object_ref=household_id,
    )
    generation = add_value(
        package,
        initialized,
        generation,
        evidence_id,
        sequence=1011,
        subject_id=account_id,
        predicate="domain.accounts/balance",
        amount="30000.00",
        currency="EUR",
        interest="account:main",
        basis="account_balance",
    )
    generation = add_value(
        package,
        initialized,
        generation,
        evidence_id,
        sequence=1012,
        subject_id=household_id,
        predicate="domain.assets/value",
        amount="10000.00",
        currency="USD",
        interest="asset:brokerage",
        basis="asset_value",
    )
    body = parse_json(
        run_topo(
            "analyze",
            "run",
            "--package",
            str(package),
            "--json",
            request=analyze_request(initialized),
        )
    )
    result = components(body)
    assert result["net_worth/EUR"]["status"] == "complete"
    assert result["net_worth/USD"]["status"] == "complete"
    assert result["net_worth/total"]["status"] == "unavailable"
    assert result["net_worth/total"]["blockers"][0]["code"] == ("MISSING_EXCHANGE_RATE")
    assert "value" not in result["net_worth/total"]
    assert body["generation_before"] == generation == body["generation_after"]


def test_missing_optional_valuation_is_visible_without_becoming_zero(
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
        sequence=1020,
        subject_id=account_id,
        predicate="domain.parties/household_allocation",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2027-01-01",
        object_ref=household_id,
    )
    generation = add_value(
        package,
        initialized,
        generation,
        evidence_id,
        sequence=1021,
        subject_id=account_id,
        predicate="domain.accounts/balance",
        amount="1000.00",
        currency="EUR",
        interest="account:main",
        basis="account_balance",
    )
    generation = confirm_assertion(
        package,
        initialized,
        generation,
        sequence=1022,
        subject_id=household_id,
        predicate="domain.assets/classification/other_asset",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2027-01-01",
        object_value={"value_type": "classification", "value": "other_asset"},
        module_data={
            "economic_interest_ref": "asset:unvalued",
            "valuation_basis": "asset_value",
            "expected_currency": "EUR",
        },
    )
    body = parse_json(
        run_topo(
            "analyze",
            "run",
            "--package",
            str(package),
            "--json",
            request=analyze_request(initialized),
        )
    )
    result = components(body)
    assert result["net_worth/EUR"]["status"] == "provisional"
    assert result["net_worth/EUR"]["value"] == {
        "amount": "1000.00",
        "currency": "EUR",
    }
    assert result["net_worth/EUR"]["warnings"][0]["code"] == "MISSING_VALUATION"
    assert body["generation_before"] == generation == body["generation_after"]


def test_conflicting_valuation_only_blocks_its_currency_component(
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
        sequence=1030,
        subject_id=account_id,
        predicate="domain.parties/household_allocation",
        evidence_id=evidence_id,
        start="2026-01-01",
        end_exclusive="2027-01-01",
        object_ref=household_id,
    )
    for sequence, subject, amount, currency, interest, predicate, basis in (
        (
            1031,
            account_id,
            "1000.00",
            "EUR",
            "account:main",
            "domain.accounts/balance",
            "account_balance",
        ),
        (
            1032,
            household_id,
            "5000.00",
            "USD",
            "asset:conflict",
            "domain.assets/value",
            "asset_value",
        ),
        (
            1033,
            household_id,
            "6000.00",
            "USD",
            "asset:conflict",
            "domain.assets/value",
            "asset_value",
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
            currency=currency,
            interest=interest,
            basis=basis,
        )
    body = parse_json(
        run_topo(
            "analyze",
            "run",
            "--package",
            str(package),
            "--json",
            request=analyze_request(initialized),
        )
    )
    result = components(body)
    assert result["net_worth/EUR"]["status"] == "complete"
    assert result["net_worth/USD"]["status"] == "unavailable"
    assert result["net_worth/USD"]["blockers"][0]["code"] == ("CONFLICTING_VALUATION")
    assert "value" not in result["net_worth/USD"]
    assert result["net_worth/total"]["status"] == "unavailable"
    assert body["generation_before"] == generation == body["generation_after"]


def test_empty_context_returns_unavailable_instead_of_zero(tmp_path: Path) -> None:
    package = tmp_path / "empty-net-worth.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    body = parse_json(
        run_topo(
            "analyze",
            "run",
            "--package",
            str(package),
            "--json",
            request=analyze_request(initialized),
        )
    )
    total = components(body)["net_worth/total"]
    assert total["status"] == "unavailable"
    assert total["blockers"][0]["code"] == "MISSING_NET_WORTH_INPUT"
    assert "value" not in total
