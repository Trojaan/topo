from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from typing import cast

from pydantic import JsonValue

from topo.canonical_validation import ValidatedPackage
from topo.models import JsonObject, ProposalRecord


def _stable_uuid7(*parts: str) -> str:
    digest = bytearray(hashlib.sha256("\x1f".join(parts).encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x70
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def explanation_bytes(result: JsonObject) -> bytes:
    sealed = deepcopy(result)
    canonical = json.dumps(
        sealed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    sealed["record_checksum"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return (
        json.dumps(sealed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def decode_explanation(payload: bytes, ref: str) -> JsonObject:
    value: JsonValue = json.loads(payload)
    if not isinstance(value, dict) or value.get("ref") != ref:
        raise ValueError("stored explanation does not match its ref")
    checksum = value.pop("record_checksum", None)
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(canonical).hexdigest()
    if checksum != expected:
        raise ValueError("stored explanation checksum does not match its payload")
    value["record_checksum"] = checksum
    return value


def _modules(package: ValidatedPackage) -> list[JsonObject]:
    return [
        {
            "module_id": item.module_id,
            "module_version": item.module_version,
        }
        for item in sorted(package.manifest.modules, key=lambda item: item.module_id)
    ]


def _base(
    package: ValidatedPackage,
    *,
    ref: str,
    ref_type: str,
    meaning: str,
) -> JsonObject:
    return {
        "ref": ref,
        "ref_type": ref_type,
        "meaning": meaning,
        "generation_id": package.manifest.generation_id,
        "contract_version": "topo.cli/0.1",
        "module_versions": cast(JsonValue, _modules(package)),
        "assertion_refs": [],
        "evidence_refs": [],
        "requirements": [],
        "assumptions": [],
        "calculation_steps": [],
        "intermediate_results": [],
        "rounding": None,
        "decision": None,
        "rule_trace": None,
    }


def index_analysis(
    package: ValidatedPackage, result: JsonObject
) -> tuple[JsonObject, dict[str, bytes]]:
    indexed = deepcopy(result)
    records: dict[str, bytes] = {}
    component_groups: list[tuple[str, list[JsonObject]]] = []
    components = indexed.get("components")
    if isinstance(components, list):
        component_groups.append(("components", cast(list[JsonObject], components)))
    for view_name in ("baseline", "scenario", "delta"):
        view = indexed.get(view_name)
        if isinstance(view, dict):
            component_groups.append(
                (view_name, cast(list[JsonObject], list(view.values())))
            )

    for group_name, group in component_groups:
        for component in group:
            ref_id = _stable_uuid7(
                cast(str, indexed["result_id"]),
                group_name,
                cast(str, component["component_id"]),
            )
            component["explain_ref"] = {
                "ref_type": "analysis_component",
                "id": ref_id,
            }
            ref = f"analysis_component:{ref_id}"
            steps = cast(list[JsonObject], component["calculation_steps"])
            explanation = _base(
                package,
                ref=ref,
                ref_type="analysis_component",
                meaning=cast(str, component["component_id"]),
            )
            explanation.update(
                {
                    "analysis_id": indexed["analysis_id"],
                    "analysis_contract_version": indexed["analysis_contract_version"],
                    "assertion_refs": deepcopy(component["used_assertion_refs"]),
                    "evidence_refs": deepcopy(component["used_evidence_refs"]),
                    "requirements": deepcopy(component["requirements"]),
                    "assumptions": deepcopy(component["assumptions"]),
                    "calculation_steps": cast(JsonValue, deepcopy(steps)),
                    "intermediate_results": [
                        deepcopy(step["unrounded_result"])
                        for step in steps
                        if "unrounded_result" in step
                    ],
                    "rounding": deepcopy(component["rounding"]),
                }
            )
            records[ref] = explanation_bytes(explanation)
            for collection_name in ("blockers", "warnings"):
                diagnostics = cast(list[JsonObject], component[collection_name])
                for index, diagnostic in enumerate(diagnostics):
                    diagnostic_id = _stable_uuid7(
                        package.manifest.generation_id,
                        ref,
                        collection_name,
                        str(index),
                        cast(str, diagnostic["code"]),
                        cast(str, diagnostic["path"]),
                    )
                    diagnostic_ref = f"diagnostic:{diagnostic_id}"
                    diagnostic["explain_ref"] = {
                        "ref_type": "diagnostic",
                        "id": diagnostic_id,
                    }
                    diagnostic_explanation = _base(
                        package,
                        ref=diagnostic_ref,
                        ref_type="diagnostic",
                        meaning=cast(str, diagnostic["message_key"]),
                    )
                    diagnostic_explanation.update(
                        {
                            "diagnostic": deepcopy(diagnostic),
                            "requirements": deepcopy(component["requirements"]),
                            "assertion_refs": deepcopy(
                                component["used_assertion_refs"]
                            ),
                            "evidence_refs": deepcopy(component["used_evidence_refs"]),
                        }
                    )
                    records[diagnostic_ref] = explanation_bytes(diagnostic_explanation)
    return indexed, records


def index_rule_preview(
    package: ValidatedPackage, result: JsonObject
) -> tuple[JsonObject, dict[str, bytes]]:
    indexed = deepcopy(result)
    records: dict[str, bytes] = {}
    evaluations = cast(list[JsonObject], indexed["evaluations"])
    preview_ref = cast(str, indexed["preview_ref"])
    for evaluation in evaluations:
        ref_id = _stable_uuid7(preview_ref, cast(str, evaluation["rule_id"]))
        ref = f"rule_outcome:{ref_id}"
        evaluation["explain_ref"] = {"ref_type": "rule_outcome", "id": ref_id}
        explanation = _base(
            package,
            ref=ref,
            ref_type="rule_outcome",
            meaning=cast(str, evaluation["outcome"]),
        )
        explanation["rule_trace"] = deepcopy(evaluation)
        records[ref] = explanation_bytes(explanation)
    return indexed, records


def explain_proposal(package: ValidatedPackage, proposal: ProposalRecord) -> JsonObject:
    ref = f"proposal:{proposal.id}"
    explanation = _base(
        package,
        ref=ref,
        ref_type="proposal",
        meaning=proposal.reason_ref,
    )
    explanation["evidence_refs"] = [
        item.model_dump(mode="json") for item in proposal.evidence_refs
    ]
    explanation["proposal"] = proposal.model_dump(mode="json")
    return explanation


def explain_decision(package: ValidatedPackage, proposal: ProposalRecord) -> JsonObject:
    assert proposal.decision is not None
    ref = f"decision:{proposal.decision.mutation_id}"
    explanation = _base(
        package,
        ref=ref,
        ref_type="decision",
        meaning=proposal.decision.outcome,
    )
    evidence_refs = {
        item.id: item.model_dump(mode="json") for item in proposal.evidence_refs
    }
    explanation["decision"] = proposal.decision.model_dump(mode="json")
    if proposal.decision.assertion_id is not None:
        assertion = next(
            item
            for item in package.assertions.records
            if item.id == proposal.decision.assertion_id
        )
        for provenance_ref in assertion.provenance:
            if provenance_ref.ref_type == "evidence":
                evidence_refs[provenance_ref.id] = provenance_ref.model_dump(
                    mode="json"
                )
        explanation["assertion_refs"] = [
            {"ref_type": "assertion", "id": proposal.decision.assertion_id}
        ]
    explanation["evidence_refs"] = [
        evidence_refs[item] for item in sorted(evidence_refs)
    ]
    return explanation
