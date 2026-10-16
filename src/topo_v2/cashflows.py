"""Structural monthly averages from explicit expectations, never transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction

from topo_v2.models import (
    Cashflow,
    CashflowSettings,
    ExpectedRange,
    Inventory,
    InventoryState,
    Limitation,
    MonthlyBand,
    MonthlyCurrency,
    MonthlyRoom,
    NormalizedCashflow,
)

FACTORS = {
    "weekly": Fraction(52, 12),
    "four_weekly": Fraction(13, 12),
    "monthly": Fraction(1),
    "quarterly": Fraction(1, 3),
    "yearly": Fraction(1, 12),
}
SCALE = 100_000_000


def _bound(amount: Decimal, factor: Fraction, *, upper: bool) -> Decimal:
    # Integer division avoids an approximate factor and ambient Decimal rounding.
    value = Fraction(amount) * factor * SCALE
    units, remainder = divmod(value.numerator, value.denominator)
    if upper and remainder:
        units += 1
    digits = tuple(int(digit) for digit in str(units))
    return Decimal((0, digits, -8))


def monthly_room(
    cashflows: list[Cashflow],
    settings: dict[str, CashflowSettings],
    inventory: Inventory | None,
    reference_date: date,
) -> MonthlyRoom:
    state = InventoryState(
        id="cashflows",
        status=inventory.status if inventory is not None else "unknown",
        checked_on=inventory.checked_on if inventory is not None else None,
    )
    limitations: list[Limitation] = []
    if state.status != "complete":
        limitations.append(
            Limitation(
                outcome="monthly_room",
                code="inventory_partial"
                if state.status == "partial"
                else "inventory_unknown",
                ids=["cashflows"],
            )
        )
    groups: dict[str, list[Cashflow]] = {}
    for record in cashflows:
        if record.start_date <= reference_date and (
            record.end_date is None or reference_date <= record.end_date
        ):
            groups.setdefault(record.currency, []).append(record)
    currencies: list[MonthlyCurrency] = []
    # Inputs have at most 28 digits. Allow exact sums plus arbitrary record counts.
    with localcontext() as arithmetic:
        arithmetic.prec = 64 + len(str(len(cashflows)))
        for currency in sorted(groups.keys() | settings.keys()):
            totals = {
                "income": [Decimal(0), Decimal(0)],
                "expense": [Decimal(0), Decimal(0)],
            }
            normalized: list[NormalizedCashflow] = []
            missing: list[str] = []
            for record in sorted(groups.get(currency, []), key=lambda item: item.id):
                band = None
                if record.amount is None:
                    missing.append(record.id)
                else:
                    lower = (
                        record.amount.lower
                        if isinstance(record.amount, ExpectedRange)
                        else record.amount
                    )
                    upper = (
                        record.amount.upper
                        if isinstance(record.amount, ExpectedRange)
                        else record.amount
                    )
                    band = MonthlyBand(
                        lower=_bound(lower, FACTORS[record.frequency], upper=False),
                        upper=_bound(upper, FACTORS[record.frequency], upper=True),
                    )
                    totals[record.kind][0] += band.lower
                    totals[record.kind][1] += band.upper
                normalized.append(
                    NormalizedCashflow(
                        id=record.id,
                        kind=record.kind,
                        monthly_amount=band,
                    )
                )
            income = MonthlyBand(lower=totals["income"][0], upper=totals["income"][1])
            expenses = MonthlyBand(
                lower=totals["expense"][0], upper=totals["expense"][1]
            )
            known_room = MonthlyBand(
                lower=income.lower - expenses.upper, upper=income.upper - expenses.lower
            )
            preference = settings.get(currency)
            if missing:
                limitations.append(
                    Limitation(
                        outcome="monthly_room", code="missing_values", ids=missing
                    )
                )
            currencies.append(
                MonthlyCurrency(
                    currency=currency,
                    records=normalized,
                    known_income=income,
                    known_expenses=expenses,
                    known_room=known_room,
                    missing_ids=missing,
                    complete=not missing,
                    room=known_room
                    if not missing and state.status == "complete"
                    else None,
                    minimum_reserve=preference.minimum_reserve if preference else None,
                    note=preference.note if preference else None,
                )
            )
    return MonthlyRoom(
        reference_date=reference_date,
        inventory=state,
        currencies=currencies,
        limitations=limitations,
    )
