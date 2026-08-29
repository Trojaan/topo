from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from test_rule_package_journey import PROJECT_ROOT, RULE_PACKAGE, run_topo


def initialize(package: Path) -> dict[str, Any]:
    return run_topo(
        "context",
        "init",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000001301",
            "expected_generation": None,
            "actor": {"actor_type": "human", "actor_id": "local-user"},
            "reason": "Initialize explain journey",
        },
    )


def explain(package: Path, ref: dict[str, str]) -> dict[str, Any]:
    return run_topo(
        "explain",
        "--package",
        str(package),
        "--ref",
        f"{ref['ref_type']}:{ref['id']}",
        request={"contract_version": "topo.cli/0.1"},
    )


def test_analysis_components_and_diagnostics_remain_verifiably_explainable(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context"
    initialized = initialize(package)
    analyzed = run_topo(
        "analyze",
        "run",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "analysis_id": "analysis.net_worth",
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
        },
    )
    component = analyzed["result"]["components"][0]
    component_explanation = explain(package, component["explain_ref"])
    stable_ref = (
        f"{component['explain_ref']['ref_type']}:{component['explain_ref']['id']}"
    )
    english_json = run_topo(
        "explain",
        "--package",
        str(package),
        "--ref",
        stable_ref,
        "--locale",
        "en",
        request={"contract_version": "topo.cli/0.1"},
    )

    assert component_explanation["result"]["meaning"] == "net_worth/total"
    assert english_json["result"] == component_explanation["result"]
    assert (
        component_explanation["result"]["generation_id"]
        == initialized["generation_after"]
    )
    assert component_explanation["result"]["analysis_contract_version"] == "0.1"
    assert component_explanation["result"]["requirements"] == component["requirements"]
    assert component_explanation["result"]["rounding"] == component["rounding"]

    diagnostic = component["blockers"][0]
    diagnostic_explanation = explain(package, diagnostic["explain_ref"])
    assert diagnostic_explanation["result"]["diagnostic"]["code"] == (
        "MISSING_NET_WORTH_INPUT"
    )
    assert diagnostic_explanation["result"]["requirements"] == component["requirements"]

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    human = subprocess.run(
        [
            sys.executable,
            "-m",
            "topo",
            "explain",
            "--package",
            str(package),
            "--ref",
            stable_ref,
            "--locale",
            "nl-NL",
        ],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert human.returncode == 0, human.stderr
    assert f"Referentie: {stable_ref}" in human.stdout
    assert "Betekenis: net_worth/total" in human.stdout


def test_rule_outcomes_and_unknown_references_have_honest_explanations(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context"
    initialized = initialize(package)
    previewed = run_topo(
        "rule",
        "preview",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "context_id": initialized["context_id"],
            "expected_generation": initialized["generation_after"],
            "rule_package_yaml": RULE_PACKAGE,
        },
    )
    evaluation = previewed["result"]["evaluations"][0]
    explained = explain(package, evaluation["explain_ref"])

    assert explained["result"]["rule_trace"] == evaluation
    assert explained["result"]["meaning"] == "proposal"

    stable_ref = (
        f"{evaluation['explain_ref']['ref_type']}:{evaluation['explain_ref']['id']}"
    )
    record = (
        package
        / "derived"
        / "explanations"
        / f"{hashlib.sha256(stable_ref.encode()).hexdigest()}.json"
    )
    record.write_text("not-json", encoding="utf-8")
    unverifiable = run_topo(
        "explain",
        "--package",
        str(package),
        "--ref",
        stable_ref,
        request={"contract_version": "topo.cli/0.1"},
    )
    assert unverifiable["outcome"] == "rejected"
    assert unverifiable["result"] == {}
    assert unverifiable["diagnostics"][0]["code"] == ("EXPLAIN_REFERENCE_UNVERIFIABLE")

    unknown = run_topo(
        "explain",
        "--package",
        str(package),
        "--ref",
        "analysis_component:0198f1a0-0000-7000-8000-000000009999",
        request={"contract_version": "topo.cli/0.1"},
    )
    assert unknown["outcome"] == "rejected"
    assert unknown["result"] == {}
    assert unknown["diagnostics"][0]["code"] == "EXPLAIN_REFERENCE_UNKNOWN"


def test_proposals_and_human_decisions_are_explainable(tmp_path: Path) -> None:
    package = tmp_path / "context"
    initialized = initialize(package)
    generation = package / "generations" / initialized["generation_after"]
    assertions = json.loads((generation / "assertions.json").read_text())
    membership = assertions["records"][0]
    evidence_ref = next(
        ref for ref in membership["provenance"] if ref["ref_type"] == "evidence"
    )
    submitted = run_topo(
        "proposal",
        "submit",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000001302",
            "context_id": initialized["context_id"],
            "expected_generation": initialized["generation_after"],
            "actor": {"actor_type": "agent", "actor_id": "local-agent"},
            "reason": "Propose an explainable recurring cashflow",
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
                    "object_value": {
                        "value_type": "recurring_cashflow",
                        "value": {
                            "frequency": "monthly",
                            "direction": "outflow",
                            "expected_period": {
                                "start_date": "2026-08-01",
                                "end_exclusive": "2026-09-01",
                            },
                            "money": {"amount": "-1000", "currency": "EUR"},
                            "amount_range": None,
                        },
                    },
                    "valid_time": {"start": "2026-08-01", "end_exclusive": None},
                    "knowledge_type": "inferred",
                    "module_data": {},
                },
                "evidence_refs": [evidence_ref],
                "reason_ref": "agent:recognized-monthly-outflow",
                "detection": None,
            },
        },
    )
    assert submitted["outcome"] == "succeeded", submitted["diagnostics"]
    proposal_id = submitted["result"]["proposal_id"]
    proposal_explanation = run_topo(
        "explain",
        "--package",
        str(package),
        "--ref",
        f"proposal:{proposal_id}",
        request={"contract_version": "topo.cli/0.1"},
    )
    assert proposal_explanation["result"]["proposal"]["status"] == "open"
    assert proposal_explanation["result"]["evidence_refs"] == [evidence_ref]

    rejected = run_topo(
        "proposal",
        "reject",
        "--package",
        str(package),
        request={
            "contract_version": "topo.cli/0.1",
            "operation_id": "0198f1a0-0000-7000-8000-000000001303",
            "context_id": initialized["context_id"],
            "expected_generation": submitted["generation_after"],
            "actor": {"actor_type": "human", "actor_id": "local-user"},
            "reason": "Reject after review",
            "proposal_ref": proposal_id,
        },
    )
    decision_explanation = run_topo(
        "explain",
        "--package",
        str(package),
        "--ref",
        rejected["result"]["decision_ref"],
        request={"contract_version": "topo.cli/0.1"},
    )
    assert decision_explanation["result"]["meaning"] == "rejected"
    assert decision_explanation["result"]["decision"]["actor"] == {
        "actor_type": "human",
        "actor_id": "local-user",
    }
