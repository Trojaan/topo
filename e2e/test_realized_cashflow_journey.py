from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def run_topo(
    *arguments: str, request: dict[str, Any] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "topo", *arguments],
        input=None if request is None else json.dumps(request),
        check=False,
        capture_output=True,
        text=True,
    )


def parse_json(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert process.stdout, process.stderr
    return cast(dict[str, Any], json.loads(process.stdout))


def import_transactions(
    package: Path, initialized: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "0198f1a0-0000-7000-8000-000000000801",
        "context_id": initialized["context_id"],
        "expected_generation": initialized["generation_after"],
        "actor": {"actor_type": "source_adapter", "actor_id": "adapter.bank"},
        "reason": "Import synthetic July statement",
        "adapter": {"adapter_id": "adapter.bank", "adapter_version": "0.1.0"},
        "records": records,
        "authorization": None,
    }
    preview = parse_json(
        run_topo(
            "source", "import", "--package", str(package), "--json", request=request
        )
    )
    request["authorization"] = {
        "preview_ref": preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
        "authorized_at": "2026-08-29T10:00:00+02:00",
    }
    imported = run_topo(
        "source", "import", "--package", str(package), "--json", request=request
    )
    assert imported.returncode == 0, imported.stderr
    return parse_json(imported)


def confirm_assertion(
    package: Path,
    initialized: dict[str, Any],
    generation: str,
    *,
    sequence: int,
    subject_id: str,
    predicate: str,
    evidence_id: str,
    start: str,
    end_exclusive: str,
    object_ref: str | None = None,
    object_value: dict[str, Any] | None = None,
    module_data: dict[str, Any] | None = None,
) -> str:
    proposed: dict[str, Any] = {
        "subject_ref": {"ref_type": "entity", "id": subject_id},
        "predicate": predicate,
        "valid_time": {"start": start, "end_exclusive": end_exclusive},
        "knowledge_type": "inferred",
        "module_data": (
            module_data
            if module_data is not None
            else {"distribution": {"complete": True, "shares": ["1"]}}
            if predicate == "domain.parties/household_allocation"
            else {}
        ),
    }
    if object_ref is not None:
        proposed["object_ref"] = {"ref_type": "entity", "id": object_ref}
    else:
        proposed["object_value"] = object_value
    metadata = {
        "contract_version": "topo.cli/0.1",
        "operation_id": f"0198f1a0-0000-7000-8000-{sequence:012d}",
        "context_id": initialized["context_id"],
        "expected_generation": generation,
        "actor": {"actor_type": "agent", "actor_id": "local-agent"},
        "reason": "Record explicit cashflow meaning",
    }
    submitted = parse_json(
        run_topo(
            "proposal",
            "submit",
            "--package",
            str(package),
            "--json",
            request={
                **metadata,
                "proposal": {
                    "proposal_type": "assertion",
                    "producer": {
                        "producer_type": "agent",
                        "producer_id": "local-agent",
                        "producer_version": "0.1.0",
                    },
                    "proposed_assertion": proposed,
                    "evidence_refs": [{"ref_type": "evidence", "id": evidence_id}],
                    "reason_ref": f"cashflow-test:{sequence}",
                    "detection": None,
                },
            },
        )
    )
    decision = {
        **metadata,
        "operation_id": f"0198f1a0-0000-7000-8001-{sequence:012d}",
        "expected_generation": submitted["generation_after"],
        "actor": {"actor_type": "human", "actor_id": "local-user"},
        "proposal_ref": submitted["result"]["proposal_id"],
        "authorization": None,
    }
    preview = parse_json(
        run_topo(
            "proposal", "confirm", "--package", str(package), "--json", request=decision
        )
    )
    decision["authorization"] = {
        "preview_ref": preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
        "authorized_at": "2026-08-29T10:05:00+02:00",
    }
    confirmed_process = run_topo(
        "proposal", "confirm", "--package", str(package), "--json", request=decision
    )
    assert confirmed_process.returncode == 0, confirmed_process.stderr
    return str(parse_json(confirmed_process)["generation_after"])


def test_empty_context_has_a_traceable_provisional_month_result(
    tmp_path: Path,
) -> None:
    package = tmp_path / "empty-cashflow.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    generation = initialized["generation_after"]

    process = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request={
            "contract_version": "topo.cli/0.1",
            "analysis_id": "analysis.realized_monthly_cashflow",
            "analysis_contract_version": "0.1",
            "context_id": initialized["context_id"],
            "analysis_scope": {
                "scope_type": "household",
                "entity_id": initialized["result"]["household_id"],
            },
            "as_of_date": "2026-08-01",
            "period": {
                "start_date": "2026-07-01",
                "end_date": "2026-08-01",
            },
            "reporting_currency": {
                "currency": "EUR",
                "allowed_rate_assertion_refs": [],
            },
            "scenario": None,
        },
    )

    assert process.returncode == 0, process.stderr
    response = parse_json(process)
    assert response["generation_before"] == generation
    assert response["generation_after"] == generation
    assert response["result"]["period"] == {
        "start_date": "2026-07-01",
        "end_date": "2026-08-01",
    }
    components = {
        item["component_id"]: item for item in response["result"]["components"]
    }
    assert components["realized/net_movement"]["value"] == {
        "amount": "0.00",
        "currency": "EUR",
    }
    assert components["realized/net_movement"]["status"] == "provisional"
    assert {
        item["code"] for item in components["realized/net_movement"]["warnings"]
    } == {"TRANSACTION_COVERAGE_NOT_DEMONSTRATED"}
    assert response["trace"]["refs"] == [{"ref_type": "generation", "id": generation}]


def test_realized_month_excludes_paired_transfers_and_keeps_unclassified_in_net(
    tmp_path: Path,
) -> None:
    package = tmp_path / "july-cashflow.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    imported = import_transactions(
        package,
        initialized,
        [
            {
                "source_id": "main",
                "record_id": "salary",
                "booking_date": "2026-07-25",
                "money": {"amount": "3200.00", "currency": "EUR"},
                "description": "SALARY",
            },
            {
                "source_id": "main",
                "record_id": "rent",
                "booking_date": "2026-07-01",
                "money": {"amount": "-1200.00", "currency": "EUR"},
                "description": "RENT",
            },
            {
                "source_id": "main",
                "record_id": "save-out",
                "booking_date": "2026-07-02",
                "money": {"amount": "-500.00", "currency": "EUR"},
                "description": "TO SAVINGS",
            },
            {
                "source_id": "savings",
                "record_id": "save-in",
                "booking_date": "2026-07-02",
                "money": {"amount": "500.00", "currency": "EUR"},
                "description": "FROM MAIN",
            },
            {
                "source_id": "main",
                "record_id": "unknown",
                "booking_date": "2026-07-10",
                "money": {"amount": "-100.00", "currency": "EUR"},
                "description": "UNKNOWN",
            },
        ],
    )
    generation = imported["generation_after"]
    accounts = [item["id"] for item in imported["result"]["account_refs"]]
    transactions = [item["id"] for item in imported["result"]["transaction_refs"]]
    evidence = [item["id"] for item in imported["result"]["evidence_refs"]]
    household = initialized["result"]["household_id"]

    sequence = 810
    for account_id in accounts:
        generation = confirm_assertion(
            package,
            initialized,
            generation,
            sequence=sequence,
            subject_id=account_id,
            predicate="domain.parties/household_allocation",
            evidence_id=evidence[0],
            start="2026-07-01",
            end_exclusive="2026-08-01",
            object_ref=household,
        )
        sequence += 1
        generation = confirm_assertion(
            package,
            initialized,
            generation,
            sequence=sequence,
            subject_id=account_id,
            predicate="domain.accounts/transaction_coverage",
            evidence_id=evidence[0],
            start="2026-07-01",
            end_exclusive="2026-08-01",
            object_value={
                "value_type": "transaction_coverage",
                "value": {"start_date": "2026-07-01", "end_exclusive": "2026-08-01"},
            },
        )
        sequence += 1

    for index, classification in (
        (0, "income"),
        (1, "expense"),
        (2, "internal_transfer"),
        (3, "internal_transfer"),
    ):
        generation = confirm_assertion(
            package,
            initialized,
            generation,
            sequence=sequence,
            subject_id=transactions[index],
            predicate=f"domain.cashflow/classification/{classification}",
            evidence_id=evidence[index],
            start="2026-07-01",
            end_exclusive="2026-08-01",
            object_value={"value_type": "classification", "value": classification},
        )
        sequence += 1
    for left, right, evidence_id in ((2, 3, evidence[2]), (3, 2, evidence[3])):
        generation = confirm_assertion(
            package,
            initialized,
            generation,
            sequence=sequence,
            subject_id=transactions[left],
            predicate="domain.cashflow/transfer_counterpart",
            evidence_id=evidence_id,
            start="2026-07-01",
            end_exclusive="2026-08-01",
            object_ref=transactions[right],
        )
        sequence += 1

    analyzed = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        "--json",
        request={
            "contract_version": "topo.cli/0.1",
            "analysis_id": "analysis.realized_monthly_cashflow",
            "analysis_contract_version": "0.1",
            "context_id": initialized["context_id"],
            "analysis_scope": {"scope_type": "household", "entity_id": household},
            "as_of_date": "2026-08-01",
            "period": {"start_date": "2026-07-01", "end_date": "2026-08-01"},
            "reporting_currency": {
                "currency": "EUR",
                "allowed_rate_assertion_refs": [],
            },
            "scenario": None,
        },
    )
    assert analyzed.returncode == 0, analyzed.stderr
    result = parse_json(analyzed)["result"]
    components = {item["component_id"]: item for item in result["components"]}
    assert components["realized/income"]["value"]["amount"] == "3200.00"
    assert components["realized/expense"]["value"]["amount"] == "1200.00"
    assert components["realized/net_movement"]["value"]["amount"] == "1900.00"
    assert components["realized/internal_transfers"]["value"]["amount"] == "500.00"
    assert components["realized/unclassified_movement"]["value"]["amount"] == "-100.00"
    assert components["realized/net_movement"]["status"] == "complete"
    assert components["realized/category_breakdown"]["status"] == "provisional"
    assert {
        warning["code"]
        for warning in components["realized/category_breakdown"]["warnings"]
    } == {"UNCLASSIFIED_TRANSACTION"}
    assert {
        ref["id"] for ref in components["realized/net_movement"]["used_evidence_refs"]
    } == set(evidence)
