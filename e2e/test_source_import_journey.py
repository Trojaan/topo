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


def current_generation(package: Path) -> tuple[str, Path]:
    generation_id = (package / "CURRENT").read_text(encoding="utf-8").strip()
    return generation_id, package / "generations" / generation_id


def test_source_adapter_imports_literal_transaction_and_replay_has_no_effect(
    tmp_path: Path,
) -> None:
    package = tmp_path / "transactions.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "0198f1a0-0000-7000-8000-000000000101",
        "context_id": initialized["context_id"],
        "expected_generation": initialized["generation_after"],
        "actor": {"actor_type": "source_adapter", "actor_id": "adapter.tally"},
        "reason": "Import July statement",
        "adapter": {"adapter_id": "adapter.tally", "adapter_version": "0.1.0"},
        "records": [
            {
                "source_id": "main-account",
                "record_id": "2026-07-25:salary",
                "booking_date": "2026-07-25",
                "money": {"amount": "3200.00", "currency": "EUR"},
                "description": "SALARY ACME",
                "source_classification": {
                    "category": "Inkomen",
                    "rule_version": "tally-rules-17",
                    "explanation": "Matched employer rule",
                },
            }
        ],
    }

    imported_process = run_topo(
        "source", "import", "--package", str(package), "--json", request=request
    )
    assert imported_process.returncode == 0, imported_process.stderr
    imported = parse_json(imported_process)
    assert imported["outcome"] == "succeeded"
    assert imported["result"]["imported"] == 1
    assert len(imported["result"]["transaction_refs"]) == 1
    assert len(imported["result"]["evidence_refs"]) == 1
    transaction_id = imported["result"]["transaction_refs"][0]["id"]
    evidence_id = imported["result"]["evidence_refs"][0]["id"]

    generation_id, generation = current_generation(package)
    entities = json.loads((generation / "entities.json").read_text())
    evidence = json.loads((generation / "evidence.json").read_text())
    assertions = json.loads((generation / "assertions.json").read_text())
    proposals = json.loads((generation / "proposals.json").read_text())

    assert {
        "id": transaction_id,
        "entity_type": "transaction",
        "module_id": "domain.cashflow",
    }.items() <= next(
        record.items()
        for record in entities["records"]
        if record["id"] == transaction_id
    )
    source_evidence = next(
        record for record in evidence["records"] if record["id"] == evidence_id
    )
    assert source_evidence["evidence_type"] == "source_record"
    assert source_evidence["source"] == {
        "adapter_id": "adapter.tally",
        "adapter_version": "0.1.0",
        "source_id": "main-account",
        "record_id": "2026-07-25:salary",
        "record_checksum": source_evidence["source"]["record_checksum"],
    }
    assert source_evidence["record"] == {
        "booking_date": "2026-07-25",
        "money": {"amount": "3200.00", "currency": "EUR"},
        "description": "SALARY ACME",
    }
    literal_values = {
        record["predicate"]: record["object_value"]
        for record in assertions["records"]
        if record["subject_ref"]["id"] == transaction_id
    }
    assert literal_values == {
        "domain.accounts/posting": {
            "value_type": "source_account",
            "value": "main-account",
        },
        "domain.cashflow/booking_date": {
            "value_type": "date",
            "value": "2026-07-25",
        },
        "domain.cashflow/money": {
            "value_type": "money",
            "value": {"amount": "3200.00", "currency": "EUR"},
        },
        "domain.cashflow/description": {
            "value_type": "text",
            "value": "SALARY ACME",
        },
    }
    assert all(
        record["knowledge_type"] == "observed"
        and record["provenance"] == [{"ref_type": "evidence", "id": evidence_id}]
        for record in assertions["records"]
        if record["subject_ref"]["id"] == transaction_id
    )
    classification = next(
        record
        for record in proposals["records"]
        if record["proposed_assertion"]["subject_ref"]["id"] == transaction_id
    )
    assert classification["status"] == "open"
    assert classification["producer"]["producer_type"] == "source_adapter"
    assert classification["proposed_assertion"]["object_value"]["value"] == {
        "category": "Inkomen",
        "rule_version": "tally-rules-17",
        "explanation": "Matched employer rule",
    }

    replay_process = run_topo(
        "source", "import", "--package", str(package), "--json", request=request
    )
    assert replay_process.returncode == 0, replay_process.stderr
    replay = parse_json(replay_process)
    assert replay["outcome"] == "no_change"
    assert replay["generation_before"] == generation_id
    assert replay["generation_after"] == generation_id
    assert replay["result"] == imported["result"]
    assert current_generation(package)[0] == generation_id


def test_source_correction_preserves_history_and_supersedes_prior_meaning(
    tmp_path: Path,
) -> None:
    package = tmp_path / "corrected-transactions.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "0198f1a0-0000-7000-8000-000000000111",
        "context_id": initialized["context_id"],
        "expected_generation": initialized["generation_after"],
        "actor": {"actor_type": "source_adapter", "actor_id": "adapter.bank"},
        "reason": "Import statement",
        "adapter": {"adapter_id": "adapter.bank", "adapter_version": "1.0.0"},
        "records": [
            {
                "source_id": "checking-account",
                "record_id": "line-104",
                "booking_date": "2026-07-25",
                "money": {"amount": "3200.00", "currency": "EUR"},
                "description": "SALARY ACM3",
                "source_classification": {
                    "category": "Unknown",
                    "rule_version": "bank-rules-1",
                    "explanation": "Initial bank label",
                },
            }
        ],
    }
    first = parse_json(
        run_topo(
            "source", "import", "--package", str(package), "--json", request=request
        )
    )
    transaction_ref = first["result"]["transaction_refs"][0]
    old_evidence_ref = first["result"]["evidence_refs"][0]
    _, first_generation = current_generation(package)
    old_evidence = next(
        item
        for item in json.loads((first_generation / "evidence.json").read_text())[
            "records"
        ]
        if item["id"] == old_evidence_ref["id"]
    )
    old_assertions = {
        item["predicate"]: item
        for item in json.loads((first_generation / "assertions.json").read_text())[
            "records"
        ]
        if item["subject_ref"]["id"] == transaction_ref["id"]
    }

    correction_request = {
        **request,
        "operation_id": "0198f1a0-0000-7000-8000-000000000112",
        "expected_generation": first["generation_after"],
        "reason": "Import corrected statement line",
        "records": [
            {
                **request["records"][0],
                "money": {"amount": "3250.00", "currency": "EUR"},
                "description": "SALARY ACME",
                "source_classification": {
                    "category": "Income",
                    "rule_version": "bank-rules-2",
                    "explanation": "Corrected employer match",
                },
            }
        ],
    }
    corrected_process = run_topo(
        "source",
        "import",
        "--package",
        str(package),
        "--json",
        request=correction_request,
    )
    assert corrected_process.returncode == 0, corrected_process.stderr
    corrected = parse_json(corrected_process)
    assert corrected["outcome"] == "succeeded"
    assert corrected["result"]["transaction_refs"] == [transaction_ref]
    new_evidence_id = corrected["result"]["evidence_refs"][0]["id"]

    _, generation = current_generation(package)
    evidence = json.loads((generation / "evidence.json").read_text())["records"]
    assert old_evidence in evidence
    successor = next(item for item in evidence if item["id"] == new_evidence_id)
    assert successor["supersedes"] == old_evidence_ref["id"]
    assert successor["record"]["money"]["amount"] == "3250.00"
    assertions = json.loads((generation / "assertions.json").read_text())["records"]
    for predicate, old_assertion in old_assertions.items():
        assert old_assertion in assertions
        successor_assertion = next(
            item
            for item in assertions
            if item["predicate"] == predicate
            and item["supersedes"] == old_assertion["id"]
        )
        assert successor_assertion["provenance"] == [
            {"ref_type": "evidence", "id": new_evidence_id}
        ]
    proposals = [
        item
        for item in json.loads((generation / "proposals.json").read_text())["records"]
        if item["proposed_assertion"]["subject_ref"]["id"] == transaction_ref["id"]
    ]
    assert [item["status"] for item in proposals] == ["superseded", "open"]
    assert (
        proposals[1]["proposed_assertion"]["object_value"]["value"]["category"]
        == "Income"
    )
