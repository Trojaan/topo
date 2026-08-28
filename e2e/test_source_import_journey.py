from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest


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


def rewrite_collection(generation: Path, filename: str, value: dict[str, Any]) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    (generation / filename).write_bytes(payload)
    manifest_path = generation / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][filename] = "sha256:" + hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def import_with_authorization(
    package: Path,
    request: dict[str, Any],
    *extra_arguments: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generation_before = current_generation(package)[0]
    preview_process = run_topo(
        "source",
        "import",
        "--package",
        str(package),
        *extra_arguments,
        "--json",
        request={**request, "authorization": None},
    )
    assert preview_process.returncode == 0, preview_process.stderr
    preview = parse_json(preview_process)
    assert preview["outcome"] == "requires_authorization"
    assert preview["generation_before"] == generation_before
    assert preview["generation_after"] == generation_before
    assert current_generation(package)[0] == generation_before
    authorized_request = {
        **request,
        "authorization": {
            "preview_ref": preview["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
            "authorized_at": "2026-08-28T12:00:00+02:00",
        },
    }
    imported_process = run_topo(
        "source",
        "import",
        "--package",
        str(package),
        *extra_arguments,
        "--json",
        request=authorized_request,
    )
    assert imported_process.returncode == 0, imported_process.stderr
    return parse_json(imported_process), authorized_request


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

    imported, authorized_request = import_with_authorization(package, request)
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
    assert source_evidence["record_path"] == f"evidence/records/{evidence_id}.json"
    source_record = json.loads(
        (package / source_evidence["record_path"]).read_text(encoding="utf-8")
    )
    assert source_evidence["source"]["record_checksum"] == (
        "sha256:"
        + hashlib.sha256(
            (package / source_evidence["record_path"]).read_bytes()
        ).hexdigest()
    )
    assert source_record == {
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
        "source",
        "import",
        "--package",
        str(package),
        "--json",
        request=authorized_request,
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
    first, _ = import_with_authorization(package, request)
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
    duplicate_request = {
        **request,
        "operation_id": "0198f1a0-0000-7000-8000-000000000113",
        "expected_generation": first["generation_after"],
        "reason": "Import an unchanged statement under a new operation",
    }
    duplicate, duplicate_authorized = import_with_authorization(
        package, duplicate_request
    )
    assert duplicate["outcome"] == "succeeded"
    assert duplicate["result"] == {
        "imported": 0,
        "evidence_refs": [old_evidence_ref],
        "transaction_refs": [transaction_ref],
    }

    correction_request = {
        **request,
        "operation_id": "0198f1a0-0000-7000-8000-000000000112",
        "expected_generation": duplicate["generation_after"],
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
    corrected, _ = import_with_authorization(package, correction_request)
    assert corrected["outcome"] == "succeeded"
    assert corrected["result"]["transaction_refs"] == [transaction_ref]
    new_evidence_id = corrected["result"]["evidence_refs"][0]["id"]

    _, generation = current_generation(package)
    evidence = json.loads((generation / "evidence.json").read_text())["records"]
    assert old_evidence in evidence
    successor = next(item for item in evidence if item["id"] == new_evidence_id)
    assert successor["supersedes"] == old_evidence_ref["id"]
    successor_record = json.loads(
        (package / successor["record_path"]).read_text(encoding="utf-8")
    )
    assert successor_record["money"]["amount"] == "3250.00"
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

    corrected_generation = corrected["generation_after"]
    duplicate_replay = parse_json(
        run_topo(
            "source",
            "import",
            "--package",
            str(package),
            "--json",
            request=duplicate_authorized,
        )
    )
    assert duplicate_replay["outcome"] == "no_change"
    assert duplicate_replay["result"] == duplicate["result"]
    assert duplicate_replay["generation_after"] == corrected_generation
    assert current_generation(package)[0] == corrected_generation


def test_source_adapter_imports_normalized_csv_transactions(tmp_path: Path) -> None:
    package = tmp_path / "csv-transactions.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    csv_path = tmp_path / "transactions.csv"
    csv_path.write_text(
        "source_id,record_id,booking_date,amount,currency,description,category,rule_version,explanation\n"
        "main-account,line-1,2026-07-25,3200.00,EUR,SALARY ACME,Income,rules-1,Employer match\n",
        encoding="utf-8",
    )
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "0198f1a0-0000-7000-8000-000000000121",
        "context_id": initialized["context_id"],
        "expected_generation": initialized["generation_after"],
        "actor": {"actor_type": "source_adapter", "actor_id": "adapter.csv"},
        "reason": "Import normalized CSV",
        "adapter": {"adapter_id": "adapter.csv", "adapter_version": "1.0.0"},
    }

    imported, authorized_request = import_with_authorization(
        package, request, "--records-csv", str(csv_path)
    )

    assert imported["outcome"] == "succeeded"
    assert imported["result"]["imported"] == 1
    normalized = imported["trace"]["normalized_request"]
    assert normalized["records"] == [
        {
            "source_id": "main-account",
            "record_id": "line-1",
            "booking_date": "2026-07-25",
            "money": {"amount": "3200.00", "currency": "EUR"},
            "description": "SALARY ACME",
            "source_classification": {
                "category": "Income",
                "rule_version": "rules-1",
                "explanation": "Employer match",
            },
        }
    ]
    assert "records" not in authorized_request


@pytest.mark.parametrize("invalid_lineage", ["assertion_self", "evidence_type"])
def test_invalid_source_successor_lineage_blocks_package_reads(
    tmp_path: Path, invalid_lineage: str
) -> None:
    package = tmp_path / f"invalid-{invalid_lineage}.topo"
    initialized = parse_json(
        run_topo("context", "init", "--package", str(package), "--json")
    )
    request = {
        "contract_version": "topo.cli/0.1",
        "operation_id": "0198f1a0-0000-7000-8000-000000000131",
        "context_id": initialized["context_id"],
        "expected_generation": initialized["generation_after"],
        "actor": {"actor_type": "source_adapter", "actor_id": "adapter.test"},
        "reason": "Import one source record",
        "adapter": {"adapter_id": "adapter.test", "adapter_version": "1.0.0"},
        "records": [
            {
                "source_id": "account",
                "record_id": "line-1",
                "booking_date": "2026-07-25",
                "money": {"amount": "10.00", "currency": "EUR"},
                "description": "TEST",
            }
        ],
    }
    _, authorized_request = import_with_authorization(package, request)
    _, generation = current_generation(package)
    if invalid_lineage == "assertion_self":
        assertions = json.loads(
            (generation / "assertions.json").read_text(encoding="utf-8")
        )
        transaction_assertion = next(
            item
            for item in assertions["records"]
            if item["predicate"] == "domain.cashflow/booking_date"
        )
        transaction_assertion["supersedes"] = transaction_assertion["id"]
        rewrite_collection(generation, "assertions.json", assertions)
    else:
        evidence = json.loads(
            (generation / "evidence.json").read_text(encoding="utf-8")
        )
        user_evidence = next(
            item
            for item in evidence["records"]
            if item["evidence_type"] == "user_statement"
        )
        source_evidence = next(
            item
            for item in evidence["records"]
            if item["evidence_type"] == "source_record"
        )
        source_evidence["supersedes"] = user_evidence["id"]
        rewrite_collection(generation, "evidence.json", evidence)

    rejected = run_topo(
        "source",
        "import",
        "--package",
        str(package),
        "--json",
        request=authorized_request,
    )

    assert rejected.returncode == 2
    body = parse_json(rejected)
    assert body["diagnostics"][0]["code"] == "PACKAGE_INTEGRITY_FAILED"
    assert body["generation_after"] is None
