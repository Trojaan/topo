from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from topo_v2 import cli, reports, storage
from topo_v2.cashflows import monthly_room
from topo_v2.engine import summarize
from topo_v2.models import Context, TransactionAggregateQuery
from topo_v2.report_files import publish_report
from topo_v2.report_html import render_report
from topo_v2.report_models import ReportQuery
from topo_v2.reports import build_report
from topo_v2.transactions import aggregate_transactions


def synthetic(**patch: Any) -> Context:
    return Context.model_validate(
        {"schema_version": "topo2.context/7", "context_id": "synthetic", **patch}
    )


def rich() -> Context:
    dated = {"as_of": "2026-10-01"}
    return synthetic(
        accounts=[
            {
                "id": "bank",
                "label": "Bank",
                "type": "savings",
                "balance": "1000",
                "availability": "free",
                **dated,
            },
            {
                "id": "overdrawn",
                "label": "Roodstand",
                "type": "payment",
                "balance": "-50",
                **dated,
            },
            {
                "id": "zero",
                "label": "Nul",
                "type": "payment",
                "balance": "0",
                "currency": "USD",
                **dated,
            },
            {"id": "missing", "label": "Onbekend", "type": "payment"},
        ],
        assets=[
            {
                "id": "home",
                "label": "Woning",
                "type": "property",
                "value": "2000",
                "availability": "restricted",
                **dated,
            }
        ],
        debts=[
            {
                "id": "overdraft",
                "label": "Zelfde roodstand",
                "type": "overdraft",
                "amount": "50",
                "account_id": "overdrawn",
                **dated,
            },
            {"id": "loan", "label": "Lening", "type": "loan", "amount": "500", **dated},
        ],
        goals=[
            {
                "id": "goal",
                "name": "Verbouwing",
                "target_amount": "10000",
                "reserved_amount": "4000",
                "monthly_contribution": "200",
                "account_ids": ["bank"],
                "target_date": "2027-01-01",
            },
            {
                "id": "goal_zero",
                "name": "Nul reservering",
                "target_amount": "100",
                "reserved_amount": "0",
                "monthly_contribution": "0",
                "currency": "USD",
            },
            {
                "id": "goal_unknown",
                "name": "Onbekende reservering",
                "target_amount": "100",
            },
        ],
        cashflows=[
            {
                "id": "salary",
                "label": "Salaris",
                "kind": "income",
                "amount": "3000",
                "frequency": "four_weekly",
                "start_date": "2026-10-01",
            },
            {
                "id": "cost",
                "label": "Kosten",
                "kind": "expense",
                "amount": {"lower": "80", "upper": "120"},
                "frequency": "weekly",
                "start_date": "2026-10-01",
            },
            {
                "id": "missing_cost",
                "label": "Onbekende last",
                "kind": "expense",
                "frequency": "monthly",
                "start_date": "2026-10-01",
            },
        ],
        cashflow_settings={"EUR": {"minimum_reserve": "500", "note": "Reserve"}},
        transactions=[
            {
                "id": "tx1",
                "account_id": "bank",
                "booking_date": "2026-09-30",
                "amount": "3000",
                "currency": "EUR",
                "description": "Inkomen",
                "kind": "income",
            },
            {
                "id": "tx2",
                "account_id": "bank",
                "booking_date": "2026-10-01",
                "amount": "-100",
                "currency": "EUR",
                "description": "Uitgave",
                "kind": "expense",
            },
            {
                "id": "tx3",
                "account_id": "bank",
                "booking_date": "2026-10-31",
                "amount": "20",
                "currency": "EUR",
                "description": "Refund",
                "kind": "expense",
            },
            {
                "id": "tx4",
                "account_id": "bank",
                "booking_date": "2026-11-01",
                "amount": "-400",
                "currency": "EUR",
                "description": "Transferhelft",
                "kind": "internal_transfer",
            },
            {
                "id": "tx5",
                "account_id": "zero",
                "booking_date": "2026-10-01",
                "amount": "0",
                "currency": "USD",
                "description": "Nul",
            },
        ],
        transaction_coverage=[
            {
                "id": "coverage",
                "account_id": "bank",
                "from_date": "2026-10-01",
                "to_date": "2026-10-31",
                "checked_on": "2026-10-15",
            }
        ],
    )


def project(context: Context, **query: Any) -> Any:
    return build_report(
        context,
        context.model_dump_json().encode(),
        ReportQuery(reference_date=date(2026, 10, 15), **query),
    )


def test_exact_shared_outcomes_and_no_double_counting() -> None:
    context = rich()
    result = project(context)
    assert result.context.summary == summarize(context)
    assert result.expectations == monthly_room(
        context.cashflows, context.cashflow_settings, None, date(2026, 10, 15)
    )
    assert result.realized == aggregate_transactions(
        context, TransactionAggregateQuery(group_by=["month"])
    )
    assert result.context.summary.net_wealth.subtotals[0].known_total == Decimal(2450)
    assert result.context.summary.goals[0].linked_value.known_amount == Decimal(1000)
    assert result.context.summary.goals[0].remaining_amount == Decimal(6000)
    assert result.context.summary.goals[1].remaining_amount == Decimal(100)
    assert result.context.summary.goals[2].remaining_amount is None
    assert result.context.summary.reservation_comparison[0].possible_excess
    assert result.context.summary.reservation_comparison[0].coverage_unknown
    assert result.expectations.currencies[0].known_income.lower == Decimal(3250)
    assert result.expectations.currencies[0].minimum_reserve == Decimal(500)
    assert result.expectations.currencies[0].room is None
    assert result.realized.totals[0].expenses == Decimal(80)
    assert result.realized.totals[0].internal_transfers.count == 1
    context.goals[0].monthly_contribution = Decimal(99999)
    assert project(context).expectations == result.expectations


def test_period_is_inclusive_without_inferred_coverage() -> None:
    result = project(rich(), from_date=date(2026, 10, 1), to_date=date(2026, 10, 31))
    assert result.realized.count == 3
    assert [r.month for r in result.realized.groups] == ["2026-10", "2026-10"]
    assert result.realized.coverage[0].status == "complete"
    assert result.realized.coverage[-1].status == "unknown"
    all_records = project(rich())
    assert all_records.realized.count == 5
    assert all_records.metadata.from_date is None
    assert all_records.realized.coverage[0].status == "declared"
    assert "geen volledige periode" in render_report(all_records)


@pytest.mark.parametrize(
    "query",
    [
        {"from_date": "2026-10-01"},
        {"to_date": "2026-10-01"},
        {"from_date": "2026-10-02", "to_date": "2026-10-01"},
        {"reference_date": "yesterday"},
    ],
)
def test_invalid_query(query: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ReportQuery.model_validate({"reference_date": "2026-10-15", **query})


@pytest.mark.parametrize("version", range(1, 8))
def test_old_empty_contexts_have_no_invented_currency_or_zero(version: int) -> None:
    context = Context.model_validate(
        {"schema_version": f"topo2.context/{version}", "context_id": "empty"}
    )
    result = project(context)
    assert result.context.summary.net_wealth.subtotals == []
    assert result.realized.totals == []
    assert result.expectations.currencies == []
    html = render_report(result)
    assert "Geen gegevens vastgelegd" in html and "Inventaris onbekend" in html
    assert "Deze software berekent" not in html


def test_all_free_text_escaped_and_exact_decimal_display() -> None:
    value = '"><script>alert("x")</script>&\'escape'
    context = rich()
    context.context_id = value
    context.accounts[0].label = value
    context.accounts[0].availability_note = value
    context.goals[0].name = value
    context.goals[0].note = value
    context.cashflows[0].label = value
    context.cashflows[0].source = value
    context.cashflow_settings["EUR"].note = value
    context.accounts[0].balance = Decimal("99999999999999999999.12345678")
    html = render_report(project(context))
    assert value not in html
    assert "&lt;script&gt;" in html and "&quot;" in html and "&#x27;" in html
    assert "99999999999999999999.12345678" in html
    assert "<script" not in html and "<link" not in html and "src=" not in html
    assert "http://" not in html and "https://" not in html
    assert "Content-Security-Policy" in html


def test_projection_calls_shared_functions_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = rich()
    for name in ("read_context", "monthly_room", "aggregate_transactions"):
        spy = Mock(wraps=getattr(reports, name))
        monkeypatch.setattr(reports, name, spy)
    project(context)
    for name in ("read_context", "monthly_room", "aggregate_transactions"):
        getattr(reports, name).assert_called_once()


def test_cli_reads_one_snapshot_even_if_source_is_replaced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, output = tmp_path / "context.json", tmp_path / "report.html"
    original = rich().model_dump_json().encode()
    path.write_bytes(original)
    real_read = storage.read
    calls = []

    def read_once(source: Path) -> tuple[bytes, Context]:
        calls.append(source)
        snapshot = real_read(source)
        # Simulate an independent atomic writer after this reader took its snapshot.
        replacement = tmp_path / "replacement.json"
        replacement.write_text(synthetic().model_dump_json())
        os.replace(replacement, source)
        return snapshot

    monkeypatch.setattr(storage, "read", read_once)
    assert (
        cli.main(
            [
                "report",
                "--context",
                str(path),
                "--output",
                str(output),
                "--reference-date",
                "2026-10-15",
            ]
        )
        == 0
    )
    envelope = json.loads(capsys.readouterr().out)
    assert len(calls) == 1
    assert (
        envelope["result"]["metadata"]["context_sha256"]
        == hashlib.sha256(original).hexdigest()
    )
    assert "Verbouwing" in output.read_text()


@pytest.mark.parametrize("stage", ["write", "flush", "fsync", "link"])
def test_write_failures_leave_no_output_or_temporary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str
) -> None:
    output = tmp_path / "report.html"

    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("synthetic failure")

    if stage in ("write", "flush"):
        real_fdopen = os.fdopen

        class FailingHandle:
            def __enter__(self) -> Any:
                return self

            def __exit__(self, *args: object) -> None:
                self.handle.close()

            def __init__(self, descriptor: int, mode: str) -> None:
                self.handle = real_fdopen(descriptor, mode)

            def write(self, payload: bytes) -> Any:
                if stage == "write":
                    self.handle.write(payload[:3])
                    fail()
                return self.handle.write(payload)

            def flush(self) -> None:
                fail()

        monkeypatch.setattr(os, "fdopen", FailingHandle)
    else:
        monkeypatch.setattr(os, stage, fail)
    with pytest.raises(OSError, match="synthetic failure"):
        publish_report(output, b"complete HTML")
    assert list(tmp_path.iterdir()) == []


def test_no_clobber_even_if_target_appears_during_publication(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "report.html"
    original_link = os.link

    def race(source: str, target: Path) -> None:
        target.write_bytes(b"other writer")
        original_link(source, target)

    monkeypatch.setattr(os, "link", race)
    with pytest.raises(FileExistsError):
        publish_report(output, b"new report")
    assert output.read_bytes() == b"other writer"
    assert list(tmp_path.iterdir()) == [output]


def test_publish_is_private_and_refuses_dangling_symlink(tmp_path: Path) -> None:
    output = tmp_path / "report.html"
    publish_report(output, b"complete")
    assert output.read_bytes() == b"complete"
    if os.name != "nt":
        assert output.stat().st_mode & 0o777 == 0o600
    link = tmp_path / "dangling.html"
    link.symlink_to(tmp_path / "absent")
    with pytest.raises(FileExistsError):
        publish_report(link, b"new")
    assert link.is_symlink() and not (tmp_path / "absent").exists()


def test_minimal_goal_is_presented_before_empty_sections() -> None:
    data = project(
        synthetic(
            goals=[{"id": "short", "name": "Verbouwing", "target_amount": "10000"}]
        )
    )
    html = render_report(data)
    assert html.index('<section id="doelen">') < html.index('<section id="foto">')
    assert "Verbouwing / EUR" in html[: html.index('<section id="foto">')]
    assert "<caption>Rekeningen</caption>" not in html
    assert "<caption>Selectietotalen" not in html


def test_hundred_goals_still_use_one_transaction_scan() -> None:
    from collections.abc import Iterator

    from topo_v2.models import Goal, Transaction

    scans = []

    class CountingTransactions(list[Transaction]):
        def __iter__(self) -> Iterator[Transaction]:
            scans.append(1)
            return super().__iter__()

    context = rich()
    context.transactions = CountingTransactions(context.transactions)
    context.goals = [
        Goal(
            id=f"goal_{i}",
            name=f"Goal {i}",
            target_amount=Decimal(10000),
            reserved_amount=Decimal(0),
            account_ids=["bank"],
        )
        for i in range(100)
    ]
    # Serialization is outside projection and is not a scan of the query path.
    raw = context.model_dump_json().encode()
    scans.clear()
    result = build_report(context, raw, ReportQuery(reference_date=date(2026, 10, 15)))
    render_report(result)
    assert len(result.context.summary.goals) == 100
    assert len(scans) == 1
