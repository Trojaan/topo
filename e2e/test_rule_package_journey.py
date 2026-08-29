from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).parents[1]

RULE_PACKAGE = """
package_id: domain.cashflow.default-rules
package_version: 0.1.0
module_id: domain.cashflow
module_version: 0.1.0
rules:
  - rule_id: cashflow.salary-monthly
    rule_version: 0.1.0
    rule_type: recognition
    input_view: domain.cashflow.transactions-by-counterparty/0.1
    when:
      all:
        - predicate: transaction_count_at_least
          args: {count: 3}
        - predicate: interval_matches
          args: {frequency: monthly}
    then:
      outcome: proposal
      assertion_template: domain.cashflow/recurring_cashflow
"""


def run_topo(*args: str, request: dict[str, Any]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "topo", *args, "--json"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return cast(dict[str, Any], json.loads(completed.stdout))


def test_rule_package_validation_preview_and_authorized_activation_are_safe(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context"
    initialized = run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000001201",
            "expected_generation": None,
            "actor": {"actor_type": "human", "actor_id": "local-user"},
            "reason": "Initialize rule package journey",
        },
    )
    context_id = initialized["context_id"]
    original_generation = initialized["generation_after"]
    read_request = {
        "contract_version": "topo.cli/0.1",
        "context_id": context_id,
        "expected_generation": original_generation,
        "rule_package_yaml": RULE_PACKAGE,
    }

    validated = run_topo(
        "rule", "validate", "--package", str(package), request=read_request
    )
    previewed = run_topo(
        "rule", "preview", "--package", str(package), request=read_request
    )

    assert validated["result"]["valid"] is True
    assert previewed["result"]["evaluations"][0] == {
        "package_id": "domain.cashflow.default-rules",
        "package_version": "0.1.0",
        "rule_id": "cashflow.salary-monthly",
        "rule_version": "0.1.0",
        "rule_type": "recognition",
        "input_view": "domain.cashflow.transactions-by-counterparty/0.1",
        "conditions": [
            {
                "predicate": "transaction_count_at_least",
                "args": {"count": 3},
                "result": False,
                "reason": "preview_input_view_is_empty",
            },
            {
                "predicate": "interval_matches",
                "args": {"frequency": "monthly"},
                "result": False,
                "reason": "preview_input_view_is_empty",
            },
        ],
        "matched": False,
        "outcome": "proposal",
        "explain_ref": previewed["result"]["evaluations"][0]["explain_ref"],
    }
    assert (package / "CURRENT").read_text().strip() == original_generation

    activation = {
        **read_request,
        "operation_id": "0198f1a0-0000-7000-8000-000000001202",
        "actor": {"actor_type": "agent", "actor_id": "agent.topo"},
        "reason": "Propose activation of reviewed cashflow rules",
        "authorization": None,
    }
    unauthorized = run_topo(
        "rule", "activate", "--package", str(package), request=activation
    )
    assert unauthorized["outcome"] == "requires_authorization"
    assert (package / "CURRENT").read_text().strip() == original_generation

    activation["authorization"] = {
        "preview_ref": previewed["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "local-user"},
        "authorized_at": "2026-08-29T12:00:00+02:00",
    }
    activated = run_topo(
        "rule", "activate", "--package", str(package), request=activation
    )
    assert activated["outcome"] == "succeeded"
    active_generation = activated["generation_after"]
    generation_path = package / "generations" / active_generation
    manifest = json.loads((generation_path / "manifest.json").read_text())
    assert manifest["active_rule_packages"] == [
        {
            "package_id": "domain.cashflow.default-rules",
            "package_version": "0.1.0",
            "module_id": "domain.cashflow",
            "module_version": "0.1.0",
            "checksum": activated["result"]["checksum"],
            "artifact": "rule-package.domain.cashflow.json",
        }
    ]
    assert (generation_path / "rule-package.domain.cashflow.json").is_file()

    stale = {
        **activation,
        "operation_id": "0198f1a0-0000-7000-8000-000000001203",
    }
    conflicted = run_topo("rule", "activate", "--package", str(package), request=stale)
    assert conflicted["outcome"] == "conflict"
    assert (package / "CURRENT").read_text().strip() == active_generation
