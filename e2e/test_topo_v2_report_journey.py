from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from jsonschema import validate
from test_topo_v2_aggregate_journey import fingerprint
from test_topo_v2_transactions_journey import run
from test_topo_v2_wealth_journey import apply
from topo2_cashflow_fixture import prepared_expectations, source_request
from topo2_input_fixture import FIXTURES, convert_export, export_change


class Tables(HTMLParser):
    """Inspect actual HTML cells, independently of the renderer."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.tables: dict[str, list[list[str]]] = {}
        self.caption = ""
        self.current = ""
        self.row: list[str] = []
        self.cell = ""
        self.capture: str | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("caption", "td"):
            self.capture, self.cell = tag, ""
        elif tag == "tr":
            self.row = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.cell += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "caption":
            self.current = self.cell
            self.tables[self.current] = []
            self.capture = None
        elif tag == "td":
            self.row.append(self.cell)
            self.capture = None
        elif tag == "tr" and self.row:
            self.tables[self.current].append(self.row)


def report(
    path: Path, output: Path, *args: str, success: bool = True
) -> dict[str, Any]:
    return run(
        "report",
        "--context",
        str(path),
        "--output",
        str(output),
        "--reference-date",
        "2026-10-15",
        *args,
        success=success,
    )


@pytest.mark.parametrize("version", range(1, 8))
def test_empty_old_context_reports_offline_without_mutation(
    tmp_path: Path, version: int
) -> None:
    path, output = tmp_path / "context.json", tmp_path / "report.html"
    path.write_text(
        json.dumps(
            {
                "schema_version": f"topo2.context/{version}",
                "context_id": "synthetic-empty",
            }
        )
    )
    before = fingerprint(path)
    result = report(path, output)["result"]
    validate(result, run("contract", "report")["result"]["output"])
    assert fingerprint(path) == before
    assert result["html_bytes"] == len(output.read_bytes())
    assert result["output"] == str(output.absolute())
    assert (
        result["metadata"]["context_sha256"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    html = output.read_text()
    assert "synthetic-empty" in html and "Geen gegevens vastgelegd" in html
    assert "Deze software berekent" not in html
    assert "EUR" not in html and "<script" not in html and "src=" not in html
    assert set(tmp_path.iterdir()) == {path, output}


def test_minimal_partial_unknown_zero_and_escaping(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    run("init", "--context", str(path))
    hostile = '<img src="https://example.invalid" onerror="alert(1)">&'
    apply(
        path,
        {
            "accounts": {
                "add": [
                    {"id": "unknown", "label": hostile, "type": "payment"},
                    {
                        "id": "zero",
                        "label": "Nul",
                        "type": "payment",
                        "balance": "0",
                        "currency": "USD",
                        "as_of": "2026-10-01",
                    },
                ]
            },
            "goals": {
                "add": [
                    {"id": "short", "name": "Verbouwing", "target_amount": "10000"},
                    {
                        "id": "zero_goal",
                        "name": "Nul reservering",
                        "target_amount": "100",
                        "reserved_amount": "0",
                        "currency": "USD",
                    },
                ]
            },
        },
    )
    before = fingerprint(path)
    output = tmp_path / "partial.html"
    report(path, output)
    assert fingerprint(path) == before
    html = output.read_text()
    tables = Tables(html).tables
    assert tables["Rekeningen"][0] == [
        hostile,
        "EUR",
        "onbekend",
        "onbekend",
        "onbekend",
        "onbekend",
    ]
    assert tables["Rekeningen"][1][2] == "0"
    goals = tables["Bestemmingen en voorgenomen inleg"]
    assert goals[0][3:] == ["onbekend", "onbekend", "onbekend"]
    assert goals[1][3:] == ["0", "100", "onbekend"]
    assert "&lt;img" in html and "<img src=" not in html
    assert "Inventaris onbekend" in html
    assert "geen begrensde periode" in html


def test_source_journey_report_matches_cli_outcomes_and_survives_reimport(
    tmp_path: Path,
) -> None:
    # Original synthetic sources, no inventory or preference questions. Tokens in
    # this black-box test exercise mechanics only, never human authorization.
    assert (
        "€10.000"
        in (
            Path(__file__).parent / "fixtures" / "topo2-goals" / "doel-kort.txt"
        ).read_text()
    )
    path = tmp_path / "context.json"
    run("init", "--context", str(path))
    request = source_request()
    apply(path, request)
    aggregate = run(
        "aggregate-transactions", "--context", str(path), "--group-by", "category"
    )["result"]
    expectations = prepared_expectations(aggregate)
    goal = run("show", "--context", str(path))["result"]["goals"][0]
    apply(
        path,
        {
            **expectations,
            "goals": {
                "update": [
                    {
                        **goal,
                        "reserved_amount": "4000",
                        "monthly_contribution": "200",
                        "priority": "high",
                        "note": "Buffer voor onderhoud",
                    }
                ]
            },
        },
    )
    before = fingerprint(path)
    summary = run("summary", "--context", str(path))["result"]
    monthly = run(
        "monthly-room", "--context", str(path), "--reference-date", "2026-10-15"
    )["result"]
    realized = run(
        "aggregate-transactions",
        "--context",
        str(path),
        "--from-date",
        "2026-10-01",
        "--to-date",
        "2026-10-31",
        "--group-by",
        "month",
    )["result"]
    output = tmp_path / "rich.html"
    result = report(
        path, output, "--from-date", "2026-10-01", "--to-date", "2026-10-31"
    )["result"]
    assert result["metadata"]["from_date"] == "2026-10-01"
    assert fingerprint(path) == before
    tables = Tables(output.read_text()).tables
    for row, subtotal in zip(
        tables["Bekend nettovermogen"], summary["net_wealth"]["subtotals"], strict=True
    ):
        assert row == [
            subtotal[k]
            for k in (
                "currency",
                "known_account_asset_total",
                "known_debt_total",
                "known_total",
            )
        ]
    for row, total in zip(
        tables["Selectietotalen · rekeningbewegingen"], realized["totals"], strict=True
    ):
        assert row == [
            "Gehele selectie",
            total["currency"],
            str(total["count"]),
            total["receipts"],
            total["outflows"],
            total["net_movement"],
        ]
    for row, total in zip(
        tables["Per boekingsmaand · economische classificatie"],
        realized["groups"],
        strict=True,
    ):
        assert row == [
            total["month"],
            total["currency"],
            total["income"],
            total["expenses"],
            total["classified_net_cashflow"],
            str(total["unknown_count"]),
        ]
    for row, currency in zip(
        tables["Bekende maandbedragen"], monthly["currencies"], strict=True
    ):
        assert row[3] == currency["known_room"]["lower"]
        assert row[5] == "onbekend"
    goal_result = summary["goals"][0]
    assert tables["Bestemmingen en voorgenomen inleg"][0] == [
        "Buffer / EUR",
        goal_result["target_amount"],
        goal_result["target_date"],
        "4000",
        "6000",
        "200",
    ]
    assert (
        tables["Oude gekoppelde waarde · afzonderlijk van reservering"][0][1]
        == "6400.00"
    )
    assert tables["Minimumreserve · afzonderlijke saldodrempel"][0][1] == "5000"
    assert "geen gezamenlijke of exclusieve dekking" in output.read_text()
    current = run("show", "--context", str(path))["result"]
    apply(path, export_change(current, convert_export(FIXTURES / "bank-updated.csv")))
    updated = tmp_path / "updated.html"
    report(path, updated)
    after_tables = Tables(updated.read_text()).tables
    for key in (
        "Bekend nettovermogen",
        "Bekende maandbedragen",
        "Bestemmingen en voorgenomen inleg",
        "Oude gekoppelde waarde · afzonderlijk van reservering",
    ):
        assert after_tables[key] == tables[key]
    assert (
        after_tables["Selectietotalen · rekeningbewegingen"]
        != tables["Selectietotalen · rekeningbewegingen"]
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ("--from-date", "2026-10-01"),
        ("--to-date", "2026-10-31"),
        ("--from-date", "2026-10-31", "--to-date", "2026-10-01"),
        ("--reference-date", "tomorrow"),
    ],
)
def test_invalid_queries_do_not_write(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    path, output = tmp_path / "context.json", tmp_path / "report.html"
    run("init", "--context", str(path))
    before = fingerprint(path)
    assert (
        report(path, output, *arguments, success=False)["error"]["code"]
        == "INVALID_DATA"
    )
    assert not output.exists() and fingerprint(path) == before


def test_output_failures_preserve_context_and_existing_output(tmp_path: Path) -> None:
    path, output = tmp_path / "context.json", tmp_path / "report.html"
    run("init", "--context", str(path))
    before = fingerprint(path)
    output.write_bytes(b"existing")
    previous_output = fingerprint(output)
    original_entries = set(tmp_path.iterdir())
    for target in (output, path, tmp_path / "absent" / "report.html", tmp_path):
        assert report(path, target, success=False)["error"]["code"] == "IO_ERROR"
        assert fingerprint(path) == before and fingerprint(output) == previous_output
    assert set(tmp_path.iterdir()) == original_entries
    path.write_text("not JSON")
    assert (
        report(path, tmp_path / "invalid.html", success=False)["error"]["code"]
        == "INVALID_DATA"
    )
    assert set(tmp_path.iterdir()) == original_entries


def test_required_arguments_keep_exit_code_two(tmp_path: Path) -> None:
    for args in (
        ("--output", str(tmp_path / "r.html")),
        ("--reference-date", "2026-10-15"),
    ):
        process = subprocess.run(
            [sys.executable, "-m", "topo_v2", "report", *args],
            capture_output=True,
            check=False,
        )
        assert process.returncode == 2
    assert list(tmp_path.iterdir()) == []
