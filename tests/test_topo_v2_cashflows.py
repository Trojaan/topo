from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from topo_v2 import engine, storage
from topo_v2.cashflows import monthly_room
from topo_v2.models import (
    Cashflow,
    CashflowSettings,
    ChangeRequest,
    Context,
    ContextQuery,
    Inventory,
    Transaction,
)

DAY = date(2026, 10, 14)


def flow(**patch: Any) -> Cashflow:
    return Cashflow.model_validate(
        {
            "id": "salary",
            "label": "Synthetic",
            "kind": "income",
            "amount": "3000",
            "frequency": "monthly",
            "start_date": "2026-10-14",
            **patch,
        }
    )


def inventory(status: str = "complete") -> Inventory:
    return Inventory.model_validate(
        {"id": "cashflows", "status": status, "checked_on": DAY}
    )


@pytest.mark.parametrize(
    ("frequency", "amount", "lower", "upper"),
    [
        ("weekly", "100", "433.33333333", "433.33333334"),
        ("four_weekly", "3000", "3250", "3250"),
        ("monthly", "1200", "1200", "1200"),
        ("quarterly", "100", "33.33333333", "33.33333334"),
        ("yearly", "1200", "100", "100"),
        ("yearly", "0.00000001", "0", "0.00000001"),
        ("yearly", "0", "0", "0"),
    ],
)
def test_factors_and_outward_rounding(
    frequency: str, amount: str, lower: str, upper: str
) -> None:
    result = monthly_room(
        [flow(frequency=frequency, amount=amount)], {}, inventory(), DAY
    )
    band = result.currencies[0].known_income
    assert band.lower == Decimal(lower) and band.upper == Decimal(upper)
    assert result.currencies[0].records[0].monthly_amount == band
    assert result.currencies[0].room == band


def test_ranges_missing_values_inventory_and_reserve() -> None:
    records = [
        flow(amount={"lower": "2800", "upper": "3200"}),
        flow(id="cost", kind="expense", amount={"lower": "800", "upper": "1100"}),
        flow(id="unknown", kind="expense", amount=None),
    ]
    settings = {"EUR": CashflowSettings(minimum_reserve=Decimal(5000), note="Flexibel")}
    for state in (None, inventory("partial"), inventory()):
        result = monthly_room(records, settings, state, DAY)
        eur = result.currencies[0]
        assert eur.known_room.lower == 1700 and eur.known_room.upper == 2400
        assert eur.minimum_reserve == 5000 and eur.note == "Flexibel"
        assert eur.missing_ids == ["unknown"] and not eur.complete and eur.room is None
        assert any(
            item.code == "missing_values" and item.ids == ["unknown"]
            for item in result.limitations
        )
    known = monthly_room(records[:2], {}, None, DAY).currencies[0]
    assert known.complete and known.room is None
    complete = monthly_room(records[:2], settings, inventory(), DAY).currencies[0]
    assert complete.room == complete.known_room  # Reserve is a stock threshold.


def test_validity_boundaries_and_currency_isolation() -> None:
    records = [
        flow(end_date=DAY),
        flow(id="future", start_date="2026-10-15"),
        flow(id="past", start_date="2026-01-01", end_date="2026-10-13"),
        flow(id="dollars", currency="USD", amount="10", kind="expense"),
    ]
    result = monthly_room(records, {}, inventory(), DAY)
    assert [item.currency for item in result.currencies] == ["EUR", "USD"]
    assert [item.id for item in result.currencies[0].records] == ["salary"]
    assert result.currencies[0].known_room.lower == 3000
    assert result.currencies[1].known_room.lower == -10
    assert monthly_room([records[1], records[2]], {}, None, DAY).currencies == []
    assert monthly_room(
        [flow(start_date=date.max, end_date=date.max)], {}, None, date.max
    ).currencies


def test_empty_unknown_zero_and_determinism() -> None:
    assert monthly_room([], {}, None, DAY).currencies == []
    assert monthly_room([], {}, inventory(), DAY).limitations == []
    zero = monthly_room([flow(amount="0")], {}, None, DAY).currencies[0]
    unknown = monthly_room([flow(amount=None)], {}, None, DAY).currencies[0]
    assert zero.complete and not unknown.complete
    assert zero.records[0].monthly_amount is not None
    assert unknown.records[0].monthly_amount is None
    records = [flow(id="z"), flow(id="a", kind="expense", amount="4000")]
    assert monthly_room(records, {}, None, DAY) == monthly_room(
        records[::-1], {}, None, DAY
    )
    assert monthly_room(records, {}, None, DAY).currencies[0].known_room.upper == -1000


def test_large_amounts_ignore_ambient_precision() -> None:
    with localcontext() as arithmetic:
        arithmetic.prec = 4
        result = monthly_room(
            [
                flow(
                    id="a", amount="99999999999999999999.12345678", frequency="weekly"
                ),
                flow(id="b", amount="0.00000001"),
            ],
            {},
            inventory(),
            DAY,
        ).currencies[0]
    assert result.known_income.lower == Decimal("433333333333333333329.53497939")
    assert result.known_income.upper == Decimal("433333333333333333329.53497939")


@pytest.mark.parametrize(
    "patch",
    [
        {"amount": "-1"},
        {"amount": 100},
        {"amount": {"lower": "2", "upper": "1"}},
        {"amount": {"lower": "1"}},
        {"amount": {"lower": "-1", "upper": "2"}},
        {"amount": "NaN"},
        {"amount": "0.000000001"},
        {"frequency": "daily"},
        {"kind": "internal_transfer"},
        {"end_date": "2026-10-13"},
    ],
)
def test_invalid_expectations(patch: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        flow(**patch)


def test_debt_links_and_global_ids() -> None:
    base: dict[str, Any] = {
        "schema_version": "topo2.context/6",
        "context_id": "synthetic",
        "debts": [{"id": "loan", "label": "Loan", "type": "loan", "currency": "EUR"}],
    }
    Context.model_validate({**base, "cashflows": [flow(debt_id="loan")]})
    for cashflow in (
        flow(debt_id="missing"),
        flow(debt_id="loan", currency="USD"),
        flow(id="loan"),
    ):
        with pytest.raises(ValidationError):
            Context.model_validate({**base, "cashflows": [cashflow]})


def test_joint_references_settings_and_tokens(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    engine.initialize(path)
    request = ChangeRequest.model_validate(
        {
            "debts": {"add": [{"id": "loan", "label": "Loan", "type": "loan"}]},
            "cashflows": {"add": [flow(debt_id="loan").model_dump(mode="json")]},
            "cashflow_settings": {"EUR": {"minimum_reserve": "500", "note": "Buffer"}},
        }
    )
    preview = engine.change(path, request)
    assert {item.section for item in preview.changes} == {
        "debts",
        "cashflows",
        "cashflow_settings",
    }
    modified = request.model_copy(
        update={
            "cashflow_settings": {
                "EUR": CashflowSettings(minimum_reserve=Decimal(501))
            },
            "confirmation_token": preview.confirmation_token,
        }
    )
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, modified)
    engine.change(
        path,
        request.model_copy(update={"confirmation_token": preview.confirmation_token}),
    )
    with pytest.raises(ValidationError):
        engine.change(
            path, ChangeRequest.model_validate({"debts": {"delete": ["loan"]}})
        )
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    repeat = ChangeRequest.model_validate(
        {
            "cashflows": {"update": [flow(debt_id="loan")]},
            "cashflow_settings": {"EUR": {"minimum_reserve": "500", "note": "Buffer"}},
        }
    )
    assert engine.change(path, repeat).status == "unchanged"
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    for patch in (
        {"USD": {"note": "Separate"}},
        {"EUR": {"note": "Replaced"}},
        {"USD": None},
    ):
        change = ChangeRequest.model_validate({"cashflow_settings": patch})
        preview = engine.change(path, change)
        engine.change(
            path,
            change.model_copy(
                update={"confirmation_token": preview.confirmation_token}
            ),
        )
    assert storage.read(path)[1].cashflow_settings == {
        "EUR": CashflowSettings(note="Replaced")
    }
    delete = ChangeRequest.model_validate(
        {
            "cashflows": {"delete": ["salary"]},
            "debts": {"delete": ["loan"]},
            "cashflow_settings": {"EUR": None},
        }
    )
    preview = engine.change(path, delete)
    engine.change(
        path,
        delete.model_copy(update={"confirmation_token": preview.confirmation_token}),
    )
    assert storage.read(path)[1].schema_version == "topo2.context/6"


def test_monthly_projection_never_iterates_transactions() -> None:
    from topo_v2.reading import read_context

    class UnreadableTransactions(list[Transaction]):
        def __iter__(self) -> Iterator[Transaction]:
            raise AssertionError("Monthly normalization must not scan transactions")

    context = Context(
        schema_version="topo2.context/6", context_id="synthetic", cashflows=[flow()]
    )
    context = context.model_copy(update={"transactions": UnreadableTransactions()})
    result = read_context(context, ContextQuery(reference_date=DAY, max_age_days=30))
    assert result.monthly_room is not None
    assert result.monthly_room.currencies[0].known_room.lower == 3000
