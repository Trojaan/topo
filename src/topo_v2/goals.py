"""Goal destinations and linked value; no transactions or allocation rules."""

from __future__ import annotations

from decimal import Decimal, localcontext

from topo_v2.models import (
    AvailabilitySubtotal,
    Domain,
    Goal,
    GoalLinkedValue,
    GoalProgress,
    Inventory,
    InventoryState,
    ReservationComparison,
)


def goal_summary(
    goals: list[Goal],
    amounts: dict[str, Decimal | None],
    availability: list[AvailabilitySubtotal],
    inventories: list[Inventory],
) -> tuple[list[GoalProgress], list[ReservationComparison]]:
    with localcontext() as arithmetic:
        arithmetic.prec = 100
        progress: list[GoalProgress] = []
        by_currency: dict[str, list[Goal]] = {}
        for goal in goals:
            by_currency.setdefault(goal.currency, []).append(goal)
            ids = list(dict.fromkeys([*goal.account_ids, *goal.asset_ids]))
            missing = [identifier for identifier in ids if amounts[identifier] is None]
            total = sum((amounts[item] or Decimal(0) for item in ids), Decimal(0))
            linked = GoalLinkedValue(
                known_amount=total,
                percentage=total / goal.target_amount * 100,
                missing_ids=missing,
                complete=not missing,
            )
            progress.append(
                GoalProgress(
                    id=goal.id,
                    name=goal.name,
                    currency=goal.currency,
                    target_amount=goal.target_amount,
                    target_date=goal.target_date,
                    **linked.model_dump(),
                    linked_value=linked,
                    reserved_amount=goal.reserved_amount,
                    monthly_contribution=goal.monthly_contribution,
                    priority=goal.priority,
                    note=goal.note,
                    remaining_amount=max(
                        goal.target_amount - goal.reserved_amount, Decimal(0)
                    )
                    if goal.reserved_amount is not None
                    else None,
                )
            )
        declared = {item.id: item for item in inventories}
        domains: tuple[Domain, ...] = ("accounts", "assets", "goals")
        states = [
            InventoryState(
                id=domain,
                status=declared[domain].status if domain in declared else "unknown",
                checked_on=declared[domain].checked_on if domain in declared else None,
            )
            for domain in domains
        ]
        available = {item.currency: item for item in availability}
        comparisons: list[ReservationComparison] = []
        for currency, records in sorted(by_currency.items()):
            total_reserved = sum(
                (
                    item.reserved_amount
                    for item in records
                    if item.reserved_amount is not None
                ),
                Decimal(0),
            )
            unknown = [item.id for item in records if item.reserved_amount is None]
            base = available.get(currency)
            free = base.known_free_total if base else None
            comparisons.append(
                ReservationComparison(
                    currency=currency,
                    goal_ids=[item.id for item in records],
                    known_reserved_total=total_reserved,
                    unknown_reservation_ids=unknown,
                    known_free_total=free,
                    missing_value_ids=base.missing_ids if base else [],
                    unknown_availability_ids=base.unknown_availability_ids
                    if base
                    else [],
                    inventories=states,
                    possible_excess=total_reserved > free if free is not None else None,
                    coverage_unknown=bool(
                        unknown
                        or base is None
                        or base.missing_ids
                        or base.unknown_availability_ids
                        or any(item.status != "complete" for item in states)
                    ),
                )
            )
        return progress, comparisons
