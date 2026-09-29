"""Small, validated projection of the current context for CLI readers."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import cast

from topo.canonical_validation import ValidatedPackage
from topo.explanations import index_analysis
from topo.models import AnalysisScope, JsonObject, NetWorthAnalyzeRunRequest
from topo.net_worth import analyze_net_worth


def summarize_context(
    package: ValidatedPackage, as_of_date: date
) -> tuple[JsonObject, dict[str, bytes]]:
    entities = package.entities.records
    assertions = package.assertions.records
    superseded = {item.supersedes for item in assertions if item.supersedes is not None}
    current = tuple(
        item
        for item in assertions
        if item.id not in superseded
        and item.verification_status == "confirmed"
        and item.valid_time.start <= as_of_date
        and (
            item.valid_time.end_exclusive is None
            or as_of_date < item.valid_time.end_exclusive
        )
    )
    account_balances: list[JsonObject] = []
    for account in sorted(
        (item for item in entities if item.entity_type == "account"),
        key=lambda item: item.id,
    ):
        candidates = [
            item
            for item in current
            if item.subject_ref.id == account.id
            and item.predicate == "domain.accounts/balance"
            and item.object_value is not None
            and item.object_value.value_type == "money"
        ]
        if not candidates:
            account_balances.append({"account_id": account.id, "status": "missing"})
            continue
        latest_date = max(item.valid_time.start for item in candidates)
        latest = [item for item in candidates if item.valid_time.start == latest_date]
        values = {
            str(item.object_value.value)
            for item in latest
            if item.object_value is not None
        }
        if len(values) != 1:
            account_balances.append(
                {
                    "account_id": account.id,
                    "status": "conflicting",
                    "as_of_date": latest_date.isoformat(),
                }
            )
            continue
        value = latest[0].object_value
        assert value is not None
        account_balances.append(
            {
                "account_id": account.id,
                "status": "confirmed",
                "as_of_date": latest_date.isoformat(),
                "money": cast(JsonObject, value.value),
            }
        )

    diagnostics: list[JsonObject] = []
    explanations: dict[str, bytes] = {}
    for household in sorted(
        (item for item in entities if item.entity_type == "household"),
        key=lambda item: item.id,
    ):
        request = NetWorthAnalyzeRunRequest(
            contract_version="topo.cli/0.1",
            analysis_id="analysis.net_worth",
            analysis_contract_version="0.1",
            context_id=package.manifest.context_id,
            analysis_scope=AnalysisScope(
                scope_type="household", entity_id=household.id
            ),
            as_of_date=as_of_date,
            period=None,
            reporting_currency=None,
            scenario=None,
        )
        indexed, records = index_analysis(package, analyze_net_worth(package, request))
        explanations.update(records)
        for component in cast(list[JsonObject], indexed["components"]):
            for kind in ("blockers", "warnings"):
                for diagnostic in cast(list[JsonObject], component[kind]):
                    diagnostics.append(
                        {
                            "household_id": household.id,
                            "component_id": component["component_id"],
                            "severity": "error" if kind == "blockers" else "warning",
                            "code": diagnostic["code"],
                            "message_key": diagnostic["message_key"],
                            "explain_ref": diagnostic.get("explain_ref"),
                        }
                    )
    result = cast(
        JsonObject,
        {
            "context_id": package.manifest.context_id,
            "generation_id": package.manifest.generation_id,
            "as_of_date": as_of_date.isoformat(),
            "entity_counts": dict(
                sorted(Counter(item.entity_type for item in entities).items())
            ),
            "assertion_counts": dict(
                sorted(Counter(item.predicate for item in current).items())
            ),
            "open_proposal_count": sum(
                item.status == "open" for item in package.proposals.records
            ),
            "account_balances": account_balances,
            "diagnostics": diagnostics,
        },
    )
    return result, explanations
