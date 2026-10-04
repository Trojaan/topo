from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

HELPER = Path(__file__).resolve().parents[1] / "scripts" / "topo_helpers.py"
UUID7 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def invoke(*args: str, helper: bool = False) -> subprocess.CompletedProcess[str]:
    command = (
        [sys.executable, str(HELPER)] if helper else [sys.executable, "-m", "topo"]
    )
    return subprocess.run(
        [*command, *args], capture_output=True, text=True, check=False
    )


def body(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert process.returncode == 0, process.stderr
    return cast(dict[str, Any], json.loads(process.stdout))


def test_prepared_wave_refreshes_only_pending_requests(tmp_path: Path) -> None:
    package = tmp_path / "synthetic.topo"
    initialized = body(invoke("context", "init", "--package", str(package), "--json"))
    initial_generation = initialized["generation_after"]

    requests: list[Path] = []
    for number in (1, 2):
        payload = tmp_path / f"payload-{number}.json"
        payload.write_text(
            json.dumps(
                {
                    "adapter": {"adapter_id": "synthetic", "adapter_version": "0.1"},
                    "records": [
                        {
                            "source_id": "synthetic-account",
                            "record_id": f"synthetic-{number}",
                            "booking_date": "2026-09-01",
                            "money": {"amount": "-1.00", "currency": "EUR"},
                            "description": f"Synthetic {number}",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        request_path = tmp_path / f"request-{number}.json"
        built = invoke(
            "build",
            "--package",
            str(package),
            "--command",
            "source.import",
            "--payload",
            str(payload),
            "--output",
            str(request_path),
            "--actor-type",
            "source_adapter",
            "--actor-id",
            "synthetic",
            "--reason",
            f"Import synthetic wave {number}",
            helper=True,
        )
        assert built.returncode == 0, built.stderr
        request = json.loads(request_path.read_text(encoding="utf-8"))
        assert UUID7.fullmatch(request["operation_id"])
        assert request["context_id"] == initialized["context_id"]
        assert request["expected_generation"] == initial_generation
        assert request["authorization"] is None
        requests.append(request_path)

    proposal_payload = tmp_path / "proposal-payload.json"
    proposal_payload.write_text(
        json.dumps(
            {
                "proposal": {
                    "proposal_type": "assertion",
                    "producer": {
                        "producer_type": "agent",
                        "producer_id": "synthetic",
                        "producer_version": "0.1",
                    },
                    "proposed_assertion": {
                        "subject_ref": {
                            "ref_type": "entity",
                            "id": initialized["result"]["person_id"],
                        },
                        "predicate": "synthetic/test",
                        "object_value": {"value_type": "string", "value": "test"},
                        "valid_time": {"start": "2026-09-01", "end_exclusive": None},
                        "knowledge_type": "inferred",
                        "module_data": {},
                    },
                    "evidence_refs": [
                        {
                            "ref_type": "evidence",
                            "id": initialized["result"]["person_id"],
                        }
                    ],
                    "reason_ref": "synthetic shape check",
                }
            }
        ),
        encoding="utf-8",
    )
    proposal_request = tmp_path / "proposal.json"
    built = invoke(
        "build",
        "--package",
        str(package),
        "--command",
        "proposal.submit",
        "--payload",
        str(proposal_payload),
        "--output",
        str(proposal_request),
        "--actor-id",
        "synthetic",
        "--reason",
        "Shape check",
        helper=True,
    )
    assert built.returncode == 0, built.stderr
    current_before = (package / "CURRENT").read_bytes()
    validated = invoke(
        "validate",
        "--command",
        "proposal.submit",
        "--request",
        str(proposal_request),
        helper=True,
    )
    assert validated.returncode == 0, validated.stderr
    assert (package / "CURRENT").read_bytes() == current_before

    for index, path in enumerate(requests):
        if index:
            pending = json.loads(path.read_text(encoding="utf-8"))
            operation_id = pending["operation_id"]
            refreshed = invoke(
                "refresh",
                "--package",
                str(package),
                "--command",
                "source.import",
                "--request",
                str(path),
                helper=True,
            )
            assert refreshed.returncode == 0, refreshed.stderr
            updated = json.loads(path.read_text(encoding="utf-8"))
            assert updated["operation_id"] == operation_id
            assert updated["expected_generation"] == current_before.decode().strip()
        preview = body(
            invoke(
                "source",
                "import",
                "--package",
                str(package),
                "--request",
                str(path),
                "--json",
            )
        )
        assert preview["outcome"] == "requires_authorization"
        assert (package / "CURRENT").read_bytes() == current_before
        request = json.loads(path.read_text(encoding="utf-8"))
        request["authorization"] = {
            "preview_ref": preview["result"]["preview_ref"],
            "authorized_by": {"actor_type": "human", "actor_id": "synthetic-person"},
            "authorized_at": "2026-09-01T12:00:00+02:00",
        }
        authorized = tmp_path / f"authorized-{index}.json"
        authorized.write_text(json.dumps(request), encoding="utf-8")
        rejected_refresh = invoke(
            "refresh",
            "--package",
            str(package),
            "--command",
            "source.import",
            "--request",
            str(authorized),
            helper=True,
        )
        assert rejected_refresh.returncode == 1
        committed = body(
            invoke(
                "source",
                "import",
                "--package",
                str(package),
                "--request",
                str(authorized),
                "--json",
            )
        )
        assert committed["outcome"] == "succeeded"
        assert committed["generation_before"] == preview["generation_before"]
        current_before = (package / "CURRENT").read_bytes()
        assert current_before.decode().strip() == committed["generation_after"]
        replay_refresh = invoke(
            "refresh",
            "--package",
            str(package),
            "--command",
            "source.import",
            "--request",
            str(path),
            helper=True,
        )
        assert replay_refresh.returncode == 1
        assert "already executed" in replay_refresh.stderr


def test_helper_rejects_payload_shell_overrides(tmp_path: Path) -> None:
    package = tmp_path / "synthetic.topo"
    body(invoke("context", "init", "--package", str(package), "--json"))
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"operation_id": "wrong"}), encoding="utf-8")
    request = tmp_path / "request.json"
    rejected = invoke(
        "build",
        "--package",
        str(package),
        "--command",
        "proposal.submit",
        "--payload",
        str(payload),
        "--output",
        str(request),
        "--actor-id",
        "synthetic",
        "--reason",
        "Invalid",
        helper=True,
    )
    assert rejected.returncode == 1
    assert "operation_id" in rejected.stderr
    assert not request.exists()

    payload.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "source": {"category": "Synthetic"},
                        "target_classification": "groceries_household",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    built = invoke(
        "build",
        "--package",
        str(package),
        "--command",
        "source.classify-batch",
        "--payload",
        str(payload),
        "--output",
        str(request),
        "--actor-id",
        "synthetic",
        "--reason",
        "Classify synthetic records",
        helper=True,
    )
    assert built.returncode == 0, built.stderr
    batch = json.loads(request.read_text(encoding="utf-8"))
    assert UUID7.fullmatch(batch["batch_id"])
    assert batch["authorization"] is None
