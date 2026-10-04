from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from test_storage_migration_journey import _mutation, _run

from topo.contracts import input_schema, output_schema


def test_authorized_batch_is_one_generation_and_replays(tmp_path: Path) -> None:
    package = tmp_path / "batch.topo"
    initialized = _run(
        package, "context", "init", request={"contract_version": "topo.cli/0.1"}
    )
    first = initialized["generation_after"]
    files = package / "generations" / first
    evidence_id = json.loads((files / "evidence.json").read_text())["records"][0]["id"]
    proposal: dict[str, Any] = {
        "proposal_type": "assertion",
        "producer": {
            "producer_type": "agent",
            "producer_id": "agent.synthetic",
            "producer_version": "0.1",
        },
        "proposed_assertion": {
            "subject_ref": {
                "ref_type": "entity",
                "id": initialized["result"]["person_id"],
            },
            "predicate": "domain.cashflow/monthly_salary",
            "object_value": {
                "value_type": "money",
                "value": {"amount": "1000.00", "currency": "EUR"},
            },
            "valid_time": {"start": "2026-01-01", "end_exclusive": None},
            "knowledge_type": "inferred",
            "module_data": {},
        },
        "evidence_refs": [{"ref_type": "evidence", "id": evidence_id}],
        "reason_ref": "synthetic:batch",
    }
    request = {
        **_mutation(initialized["context_id"], first),
        "proposals": [proposal, proposal],
        "authorization": None,
    }
    Draft202012Validator(input_schema("proposal.submit-batch")).validate(request)
    preview = _run(package, "proposal", "submit-batch", request=request)
    assert preview["outcome"] == "requires_authorization"
    assert (package / "CURRENT").read_text().strip() == first
    Draft202012Validator(output_schema("proposal.submit-batch")).validate(preview)
    request["authorization"] = {
        "preview_ref": preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "test-user"},
        "authorized_at": "2026-10-04T12:00:00Z",
    }
    altered = json.loads(json.dumps(request))
    altered["proposals"][1]["reason_ref"] = "synthetic:changed-after-preview"
    rejected = subprocess.run(
        [
            sys.executable,
            "-m",
            "topo",
            "proposal",
            "submit-batch",
            "--package",
            str(package),
            "--json",
        ],
        input=json.dumps(altered),
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 0
    assert json.loads(rejected.stdout)["outcome"] == "rejected"
    rejected_result = json.loads(rejected.stdout)
    assert rejected_result["diagnostics"][0]["code"] == "INVALID_AUTHORIZATION"
    assert (package / "CURRENT").read_text().strip() == first
    assert len(list((package / "generations").iterdir())) == 1
    result = _run(package, "proposal", "submit-batch", request=request)
    Draft202012Validator(output_schema("proposal.submit-batch")).validate(result)
    assert result["outcome"] == "succeeded"
    assert [item["item_index"] for item in result["result"]["items"]] == [0, 1]
    assert len({item["proposal_id"] for item in result["result"]["items"]}) == 2
    assert len(list((package / "generations").iterdir())) == 2
    second = package / "generations" / result["generation_after"]
    assert (second / "assertions.json").read_bytes() == (
        files / "assertions.json"
    ).read_bytes()
    assert all(
        item["status"] == "open"
        for item in json.loads((second / "proposals.json").read_text())["records"]
    )
    journal = json.loads((package / "history" / "journal.json").read_text())
    assert journal["entries"][-1]["operation"] == "proposal.submit-batch"
    replay = _run(package, "proposal", "submit-batch", request=request)
    assert replay["outcome"] == "no_change"
    assert replay["result"] == result["result"]
    assert len(list((package / "generations").iterdir())) == 2
    verified = _run(
        package, "context", "verify", request={"contract_version": "topo.cli/0.1"}
    )
    assert verified["result"]["generations_verified"] == 2
