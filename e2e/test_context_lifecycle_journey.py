from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from topo.identifiers import uuid7


def run_topo(*args: str, request: dict[str, object]) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "topo", *args, "--json"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return cast(dict[str, object], json.loads(completed.stdout))


def mutation(context_id: str, generation: str, reason: str) -> dict[str, object]:
    return {
        "contract_version": "topo.cli/0.1",
        "operation_id": uuid7(),
        "context_id": context_id,
        "expected_generation": generation,
        "actor": {"actor_type": "human", "actor_id": "beheerder"},
        "reason": reason,
    }


def test_administrator_can_manage_the_complete_context_lifecycle(
    tmp_path: Path,
) -> None:
    package = tmp_path / "lifecycle.topo"
    initialized = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={"contract_version": "topo.cli/0.1"},
    )
    context_id = str(initialized["context_id"])
    first = str(initialized["generation_after"])
    evidence_id = json.loads(
        (package / "generations" / first / "evidence.json").read_text()
    )["records"][0]["id"]
    module_versions = {
        module["module_id"]: module["module_version"]
        for module in json.loads(
            (package / "generations" / first / "manifest.json").read_text()
        )["modules"]
    }

    migrated = run_topo(
        "context",
        "migrate",
        "--package",
        str(package),
        request={
            **mutation(context_id, first, "Migreer gecontroleerd"),
            "target_package_version": "0.1",
            "target_context_schema_version": "topo.context/0.1",
            "target_module_versions": module_versions,
        },
    )
    restored = run_topo(
        "context",
        "restore",
        "--package",
        str(package),
        request={
            **mutation(
                context_id,
                str(migrated["generation_after"]),
                "Herstel vertrouwde toestand",
            ),
            "restore_generation": first,
        },
    )
    compacted = run_topo(
        "context",
        "compact",
        "--package",
        str(package),
        request={
            **mutation(
                context_id,
                str(restored["generation_after"]),
                "Pas begrensde retentie toe",
            ),
            "retain_latest": 2,
            "restore_generations": [first],
        },
    )
    scrubbed = run_topo(
        "context",
        "privacy-scrub",
        "--package",
        str(package),
        request={
            **mutation(
                context_id,
                str(compacted["generation_after"]),
                "Verwijder geselecteerd bewijs",
            ),
            "evidence_ids": [evidence_id],
        },
    )

    assert scrubbed["outcome"] == "succeeded"
    assert (package / "CURRENT").read_text().strip() == scrubbed["generation_after"]
    assert evidence_id not in (package / "history" / "journal.json").read_text()
