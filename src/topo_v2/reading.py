"""Compact current context with outcome-specific, non-blocking limitations."""

from __future__ import annotations

from topo_v2.cashflows import monthly_room
from topo_v2.engine import summarize
from topo_v2.models import (
    Account,
    Asset,
    CompactContext,
    Context,
    ContextQuery,
    CoverageState,
    Debt,
    Domain,
    InventoryState,
    Limitation,
    TransactionCoverage,
    ValueAge,
)

DOMAINS: tuple[Domain, ...] = ("accounts", "assets", "debts", "goals", "cashflows")


def read_context(context: Context, query: ContextQuery) -> CompactContext:
    declared = {record.id: record for record in context.inventories}
    inventories = [
        InventoryState(
            id=domain,
            status=declared[domain].status if domain in declared else "unknown",
            checked_on=declared[domain].checked_on if domain in declared else None,
        )
        for domain in DOMAINS
    ]
    limitations: list[Limitation] = []
    for state in inventories:
        if state.status == "complete":
            continue
        outcomes = {
            "accounts": ("wealth_overview", "net_wealth", "availability"),
            "assets": ("wealth_overview", "net_wealth", "availability"),
            "debts": ("net_wealth",),
            "goals": ("goal_progress",),
            "cashflows": ("monthly_room",),
        }
        for outcome in outcomes[state.id]:
            limitations.append(
                Limitation.model_validate(
                    {
                        "outcome": outcome,
                        "code": "inventory_" + state.status,
                        "ids": [state.id],
                    }
                )
            )
    ages: list[ValueAge] = []
    missing: list[str] = []
    records: list[Account | Asset | Debt] = [
        *context.accounts,
        *context.assets,
        *context.debts,
    ]
    for record in records:
        value = (
            record.balance
            if isinstance(record, Account)
            else record.value
            if isinstance(record, Asset)
            else record.amount
        )
        if value is None:
            missing.append(record.id)
        age = (
            (query.reference_date - record.as_of).days
            if query.reference_date is not None and record.as_of is not None
            else None
        )
        ages.append(
            ValueAge(
                id=record.id,
                age_days=age,
                stale=age > query.max_age_days
                if age is not None
                and query.max_age_days is not None
                and value is not None
                else None,
            )
        )
    stale = [age.id for age in ages if age.stale]
    debt_ids = {debt.id for debt in context.debts}
    for code, identifiers in (("missing_values", missing), ("stale_values", stale)):
        if identifiers:
            limitations.append(
                Limitation.model_validate(
                    {
                        "outcome": "net_wealth",
                        "code": code,
                        "ids": identifiers,
                    }
                )
            )
        wealth_ids = [item for item in identifiers if item not in debt_ids]
        if wealth_ids:
            for outcome in ("wealth_overview", "availability"):
                limitations.append(
                    Limitation.model_validate(
                        {
                            "outcome": outcome,
                            "code": code,
                            "ids": wealth_ids,
                        }
                    )
                )
        for goal in context.goals:
            affected = sorted(set(identifiers) & set(goal.account_ids + goal.asset_ids))
            if affected:
                limitations.append(
                    Limitation.model_validate(
                        {
                            "outcome": "goal_progress",
                            "code": code,
                            "ids": [goal.id, *affected],
                        }
                    )
                )
    by_account: dict[str, list[TransactionCoverage]] = {
        account.id: [] for account in context.accounts
    }
    # Group once; never infer coverage from transaction endpoints.
    for interval in context.transaction_coverage:
        by_account[interval.account_id].append(interval)
    coverage = []
    for account in context.accounts:
        intervals = sorted(
            by_account[account.id],
            key=lambda item: (item.from_date, item.to_date, item.id),
        )
        coverage.append(
            CoverageState(
                account_id=account.id,
                status="declared" if intervals else "unknown",
                intervals=intervals,
            )
        )
        limitations.append(
            Limitation(
                outcome="transaction_analysis",
                code="coverage_limited" if intervals else "coverage_unknown",
                ids=[account.id],
            )
        )
    unknown_availability = [
        record.id
        for record in [*context.accounts, *context.assets]
        if record.availability in (None, "unknown")
    ]
    if unknown_availability:
        limitations.append(
            Limitation(
                outcome="availability",
                code="availability_unknown",
                ids=unknown_availability,
            )
        )
    monthly = None
    if query.reference_date is not None:
        monthly = monthly_room(
            context.cashflows,
            context.cashflow_settings,
            declared.get("cashflows"),
            query.reference_date,
        )
        limitations.extend(
            item for item in monthly.limitations if item not in limitations
        )
    return CompactContext(
        context_id=context.context_id,
        accounts=context.accounts,
        assets=context.assets,
        debts=context.debts,
        goals=context.goals,
        cashflows=context.cashflows,
        cashflow_settings=context.cashflow_settings,
        monthly_room=monthly,
        summary=summarize(context),
        inventories=inventories,
        transaction_coverage=coverage,
        age_policy=query,
        value_age=ages,
        limitations=limitations,
    )
