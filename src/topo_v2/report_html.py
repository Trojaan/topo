"""Offline HTML presentation. All dynamic text passes through HTML escaping."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from html import escape

from topo_v2.models import Limitation, MonthlyBand, TransactionTotals
from topo_v2.report_models import ReportData

CSS = """
:root{color-scheme:light;--ink:#17312e;--muted:#526860;--line:#d4dfd8;--accent:#116c59}
*{box-sizing:border-box}body{margin:0;background:#f3f5ef;color:var(--ink);font:16px/1.55 system-ui,sans-serif}
main{max-width:1200px;margin:auto;padding:40px 28px}header{border-top:6px solid var(--accent);padding-top:20px;margin-bottom:32px}
h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.12;margin:8px 0 20px;letter-spacing:-.035em}
h2{font-size:1.55rem;margin:0 0 12px}h3{font-size:1.1rem;margin:24px 0 8px}
section{background:#fff;border:1px solid var(--line);border-radius:12px;padding:26px;margin:22px 0}
p{margin:8px 0;overflow-wrap:anywhere}.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.1em;font-size:.78rem;text-transform:uppercase}
.note{color:var(--muted);font-size:.9rem}.limit{border-left:3px solid #ba8e44;padding:6px 12px;background:#faf7ef;font-size:.9rem}
table{width:100%;border-collapse:collapse;margin:12px 0 20px;font-size:.9rem;table-layout:fixed}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
th{background:#edf3ee;font-size:.8rem}td{font-variant-numeric:tabular-nums}caption{text-align:left;font-weight:700;margin:10px 0}
.empty{color:var(--muted);padding:6px 0}dl{display:grid;grid-template-columns:180px 1fr;gap:8px;font-size:.85rem}dt{font-weight:650}dd{margin:0;overflow-wrap:anywhere}
@media(max-width:650px){main{padding:22px 14px}section{padding:18px 14px}h1{font-size:2.1rem}thead{display:none}caption{display:block;width:100%}table,tbody,tr,td{display:block;width:100%}tr{border:1px solid var(--line);border-radius:6px;margin:12px 0;padding:6px}td{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:12px;border:0;padding:5px}td::before{content:attr(data-label);color:var(--muted);font-size:.8rem}dl{grid-template-columns:1fr;gap:3px}dd{margin-bottom:8px}}
@media print{body{background:white}main{padding:0}section{break-inside:avoid}header{margin-bottom:16px}}
"""
DOMAINS = {
    "accounts": "rekeningen",
    "assets": "bezittingen",
    "debts": "schulden",
    "goals": "doelen",
    "cashflows": "verwachtingen",
}
AVAILABILITY = {
    "free": "vrij",
    "restricted": "beperkt",
    "unknown": "onbekend",
    None: "onbekend",
}
STATUS = {
    "unknown": "onbekend",
    "partial": "gedeeltelijk",
    "complete": "compleet verklaard",
    "declared": "alleen verklaarde intervallen",
}


def text(value: object) -> str:
    return escape("onbekend" if value is None else str(value), quote=True)


def paragraph(value: object, kind: str = "note") -> str:
    return f'<p class="{kind}">{text(value)}</p>'


def table(title: str, headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    body = "".join(
        "<tr>"
        + "".join(
            f'<td data-label="{text(label)}">{text(value)}</td>'
            for label, value in zip(headers, row, strict=True)
        )
        + "</tr>"
        for row in rows
    )
    if not body:
        return f"<h3>{text(title)}</h3>" + paragraph(
            "Geen gegevens vastgelegd.", "empty"
        )
    return (
        f"<table><caption>{text(title)}</caption><thead><tr>"
        + "".join(f'<th scope="col">{text(h)}</th>' for h in headers)
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table>"
    )


def limitations(items: list[Limitation], outcome: str) -> str:
    messages = []
    grouped: dict[str, list[str]] = {}
    for item in items:
        if item.outcome == outcome:
            grouped.setdefault(item.code, []).extend(item.ids)
    for code, identifiers in grouped.items():
        names = ", ".join(DOMAINS.get(i, i) for i in dict.fromkeys(identifiers))
        wording = {
            "inventory_unknown": f"Inventaris onbekend: {names}; bekende posten blijven bruikbaar.",
            "inventory_partial": f"Inventaris gedeeltelijk: {names}; bekende posten blijven bruikbaar.",
            "missing_values": f"Bedrag onbekend: {names}.",
            "availability_unknown": f"Beschikbaarheid onbekend: {names}.",
            "stale_values": f"Waarde buiten opgegeven ouderdomsgrens: {names}.",
            "not_supported": f"Deze software berekent deze uitkomst nog niet: {names}.",
        }.get(code)
        if wording is not None:
            messages.append(wording)
    return "".join(paragraph(message, "limit") for message in messages)


def band(value: MonthlyBand | None) -> str:
    if value is None:
        return "onbekend"
    return (
        str(value.lower)
        if value.lower == value.upper
        else f"{value.lower} – {value.upper}"
    )


def movement_tables(
    title: str, records: Sequence[TransactionTotals], months: Sequence[str | None]
) -> str:
    if not records:
        return ""
    pairs = list(zip(records, months, strict=True))
    return (
        table(
            title + " · rekeningbewegingen",
            [
                "Maand",
                "Valuta",
                "Records",
                "Ontvangen",
                "Uitgestroomd",
                "Netto beweging",
            ],
            (
                (
                    month or "Gehele selectie",
                    r.currency,
                    r.count,
                    r.receipts,
                    r.outflows,
                    r.net_movement,
                )
                for r, month in pairs
            ),
        )
        + table(
            title + " · economische classificatie",
            [
                "Maand",
                "Valuta",
                "Inkomen",
                "Uitgaven",
                "Netto geclassificeerd",
                "Onbekende records",
            ],
            (
                (
                    month or "Gehele selectie",
                    r.currency,
                    r.income,
                    r.expenses,
                    r.classified_net_cashflow,
                    r.unknown_count,
                )
                for r, month in pairs
            ),
        )
        + table(
            title + " · transfers en onbekenden",
            [
                "Maand / valuta",
                "Soort",
                "Records",
                "Ontvangen",
                "Uitgestroomd",
                "Netto beweging",
            ],
            (
                (
                    f"{month or 'Gehele selectie'} / {r.currency}",
                    label,
                    movement.count,
                    movement.receipts,
                    movement.outflows,
                    movement.net_movement,
                )
                for r, month in pairs
                for label, movement in (
                    ("Interne transfers", r.internal_transfers),
                    ("Onbekend", r.unknown),
                )
            ),
        )
    )


def period_label(data: ReportData) -> str:
    metadata = data.metadata
    return (
        f"{metadata.from_date} t/m {metadata.to_date} (inclusief)"
        if metadata.from_date is not None
        else "Alle opgeslagen transacties; geen begrensde periode"
    )


def section(identifier: str, title: str) -> str:
    return f'<section id="{text(identifier)}"><h2>{text(title)}</h2>'


def photo_section(data: ReportData) -> str:
    context, summary = data.context, data.context.summary
    parts = [section("foto", "Financiële foto")]
    if not (context.accounts or context.assets or context.debts):
        return (
            "".join(parts)
            + paragraph("Geen gegevens vastgelegd.", "empty")
            + limitations(context.limitations, "net_wealth")
            + "</section>"
        )
    parts.append(
        paragraph(
            "Actuele opgeslagen waarden met hun eigen peildata; geen historische reconstructie op de referentiedatum."
        )
    )
    for title, records in (
        ("Rekeningen", context.accounts),
        ("Bezittingen", context.assets),
    ):
        parts.append(
            table(
                title,
                [
                    "Naam",
                    "Valuta",
                    "Bedrag",
                    "Peildatum",
                    "Beschikbaarheid",
                    "Toelichting",
                ],
                (
                    (
                        r.label,
                        r.currency,
                        getattr(r, "balance", getattr(r, "value", None)),
                        r.as_of,
                        AVAILABILITY[r.availability],
                        r.availability_note,
                    )
                    for r in records
                ),
            )
        )
    parts.append(
        table(
            "Schulden",
            ["Naam", "Valuta", "Stand", "Peildatum", "Al in rekeningsaldo"],
            (
                (
                    r.label,
                    r.currency,
                    r.amount,
                    r.as_of,
                    r.account_id or "Geen koppeling",
                )
                for r in context.debts
            ),
        )
    )
    parts.append(
        table(
            "Bekend nettovermogen",
            [
                "Valuta",
                "Rekeningen + bezittingen",
                "Afzonderlijke schulden",
                "Bekende nettosom",
            ],
            (
                (
                    r.currency,
                    r.known_account_asset_total,
                    r.known_debt_total,
                    r.known_total,
                )
                for r in summary.net_wealth.subtotals
            ),
        )
    )
    for r in summary.net_wealth.subtotals:
        if r.linked_debt_ids:
            parts.append(
                paragraph(
                    f"{r.currency}: gekoppelde roodstand {', '.join(r.linked_debt_ids)} telt al via het saldo mee; geen tweede schuldaftrek."
                )
            )
    parts.append(limitations(context.limitations, "net_wealth"))
    parts.append(
        table(
            "Expliciet bekende beschikbaarheid",
            ["Valuta", "Bekend vrij", "Bekend beperkt"],
            (
                (r.currency, r.known_free_total, r.known_restricted_total)
                for r in summary.availability
            ),
        )
    )
    parts.append(
        paragraph(
            "Vrije deelsommen zijn geen bestedingsruimte na schulden of reserveringen. Onbekende beschikbaarheid telt niet als vrij geld."
        )
    )
    parts.append(limitations(context.limitations, "availability"))
    return "".join(parts) + "</section>"


def realized_section(data: ReportData) -> str:
    metadata = data.metadata
    parts = [section("realisatie", "Maandbeeld · gerealiseerd")]
    if not data.realized.count and not data.realized.coverage:
        return (
            "".join(parts)
            + paragraph(
                "Geen gegevens vastgelegd binnen deze selectie. Dekking onbekend; geen volledige periode of maanddekking geclaimd.",
                "empty",
            )
            + "</section>"
        )
    parts.append(
        paragraph(
            f"Selectie: {period_label(data)}. Boekingsmaanden tonen uitsluitend aanwezige records; een ontbrekende maand is geen bekende nul."
        )
    )
    if data.realized.count:
        parts.append(
            paragraph(
                "Transacties veranderen opgeslagen saldi niet. Transfers en onbekenden blijven buiten economische inkomsten/uitgaven. Een transferhelft of nulsom bewijst geen paar."
            )
        )
    else:
        parts.append(
            paragraph(
                "Geen gegevens vastgelegd binnen deze selectie; dit bewijst geen nulomzet of volledige dekking.",
                "empty",
            )
        )
    parts.append(
        movement_tables(
            "Selectietotalen", data.realized.totals, [None] * len(data.realized.totals)
        )
    )
    parts.append(
        movement_tables(
            "Per boekingsmaand",
            data.realized.groups,
            [r.month for r in data.realized.groups],
        )
    )
    parts.append(
        paragraph(
            "Classificatie: "
            + (
                "geen geselecteerde records"
                if data.realized.classification_complete is None
                else "alle geselecteerde records geclassificeerd"
                if data.realized.classification_complete
                else "onbekende classificaties; economische totalen zijn deelsommen"
            ),
            "limit",
        )
    )
    parts.append(
        table(
            "Verklaarde transactiedekking · onafhankelijk van classificatie",
            ["Rekening", "Dekking selectie", "Expliciete intervallen"],
            (
                (
                    r.account_id,
                    STATUS[r.status],
                    "; ".join(
                        f"{i.from_date} t/m {i.to_date} (verklaard {i.checked_on})"
                        for i in r.intervals
                    )
                    or "onbekend",
                )
                for r in data.realized.coverage
            ),
        )
    )
    if metadata.from_date is None:
        parts.append(
            paragraph(
                "Zonder begrensde selectie wordt geen volledige periode of maanddekking geclaimd.",
                "limit",
            )
        )
    return "".join(parts) + "</section>"


def expectations_section(data: ReportData) -> str:
    context, metadata = data.context, data.metadata
    parts = [section("verwachtingen", "Maandbeeld · structurele verwachtingen")]
    if not data.expectations.currencies:
        return (
            "".join(parts)
            + paragraph(
                "Geen actieve verwachtingen of instellingen vastgelegd op de referentiedatum.",
                "empty",
            )
            + limitations(data.expectations.limitations, "monthly_room")
            + "</section>"
        )
    parts.append(
        paragraph(
            f"Alleen verwachtingen actief op {metadata.reference_date}. Structureel maandgemiddelde, geen betaalagenda en geen som met gerealiseerde transacties."
        )
    )
    labels = {r.id: r for r in context.cashflows}
    parts.append(
        table(
            "Bekende maandbedragen",
            [
                "Valuta",
                "Inkomen",
                "Uitgaven",
                "Voorzichtige bekende ruimte",
                "Bekende ruimteband",
                "Volledige ruimteband",
            ],
            (
                (
                    r.currency,
                    band(r.known_income),
                    band(r.known_expenses),
                    r.known_room.lower,
                    band(r.known_room),
                    band(r.room),
                )
                for r in data.expectations.currencies
            ),
        )
    )
    parts.append(
        paragraph(
            "De ondergrens is voorzichtige ruimte binnen bekende posten. Ontbrekende bedragen of inventaris beperken de volledige uitkomst; nooit het midden van een band aannemen."
        )
    )
    parts.append(
        table(
            "Actieve verwachtingen · genormaliseerd per maand",
            ["Naam / valuta", "Soort", "Maandbedrag", "Bron / selectie"],
            (
                (
                    f"{labels[r.id].label} / {currency.currency}",
                    "Inkomen" if r.kind == "income" else "Uitgave",
                    band(r.monthly_amount),
                    labels[r.id].source,
                )
                for currency in data.expectations.currencies
                for r in currency.records
            ),
        )
    )
    parts.append(limitations(data.expectations.limitations, "monthly_room"))
    parts.append(
        table(
            "Minimumreserve · afzonderlijke saldodrempel",
            ["Valuta", "Minimumreserve", "Toelichting"],
            (
                (r.currency, r.minimum_reserve, r.note)
                for r in data.expectations.currencies
            ),
        )
    )
    parts.append(
        paragraph(
            "Minimumreserve wordt niet maandelijks afgetrokken. Doelinleg is intentie en verlaagt dit maandbeeld niet nogmaals."
        )
    )
    return "".join(parts) + "</section>"


def goals_section(data: ReportData) -> str:
    context, summary = data.context, data.context.summary
    parts = [section("doelen", "Doelen")]
    if not summary.goals:
        return (
            "".join(parts)
            + paragraph("Geen doelen vastgelegd.", "empty")
            + limitations(context.limitations, "goal_progress")
            + "</section>"
        )
    parts.append(
        table(
            "Bestemmingen en voorgenomen inleg",
            [
                "Naam / valuta",
                "Streefbedrag",
                "Gewenste datum",
                "Expliciete reservering",
                "Resterend bedrag",
                "Voorgenomen maandinleg",
            ],
            (
                (
                    f"{r.name} / {r.currency}",
                    r.target_amount,
                    r.target_date,
                    r.reserved_amount,
                    r.remaining_amount,
                    r.monthly_contribution,
                )
                for r in summary.goals
            ),
        )
    )
    parts.append(
        paragraph(
            "Resterend bedrag volgt uitsluitend uit de expliciete reservering. Onbekende reservering is geen nul. Reservering bewijst geen aanwezige of exclusieve middelen; maandinleg is geen betaling."
        )
    )
    parts.append(
        table(
            "Oude gekoppelde waarde · afzonderlijk van reservering",
            [
                "Doel / valuta",
                "Bekende gekoppelde waarde",
                "Percentage gekoppeld",
                "Ontbrekende waarden",
            ],
            (
                (
                    f"{r.name} / {r.currency}",
                    r.linked_value.known_amount,
                    r.linked_value.percentage,
                    ", ".join(r.linked_value.missing_ids) or "Geen binnen koppelingen",
                )
                for r in summary.goals
            ),
        )
    )
    parts.append(limitations(context.limitations, "goal_progress"))
    parts.append(
        table(
            "Reserveringen tegenover bekende vrije waarde",
            [
                "Valuta",
                "Bekende reserveringen",
                "Bekende vrije waarde",
                "Mogelijke overschrijding",
                "Dekking onbekend",
            ],
            (
                (
                    r.currency,
                    r.known_reserved_total,
                    r.known_free_total,
                    "onbekend"
                    if r.possible_excess is None
                    else "ja"
                    if r.possible_excess
                    else "nee",
                    "ja" if r.coverage_unknown else "nee",
                )
                for r in summary.reservation_comparison
            ),
        )
    )
    for comparison in summary.reservation_comparison:
        if comparison.coverage_unknown:
            reasons = []
            if comparison.unknown_reservation_ids:
                reasons.append(
                    "reserveringen: " + ", ".join(comparison.unknown_reservation_ids)
                )
            if comparison.missing_value_ids:
                reasons.append("bedragen: " + ", ".join(comparison.missing_value_ids))
            if comparison.unknown_availability_ids:
                reasons.append(
                    "beschikbaarheid: " + ", ".join(comparison.unknown_availability_ids)
                )
            if comparison.known_free_total is None:
                reasons.append("geen bekende vrije vermogensdeelsom")
            reasons.extend(
                "inventaris " + DOMAINS[i.id]
                for i in comparison.inventories
                if i.status != "complete"
            )
            parts.append(
                paragraph(
                    f"{comparison.currency}: dekking onbekend door "
                    + "; ".join(reasons)
                    + ".",
                    "limit",
                )
            )
    parts.append(
        paragraph(
            "Deze vergelijking bewijst geen gezamenlijke of exclusieve dekking, ook wanneer geen overschrijding of onbekende dekking wordt gemeld. Minimumreserve blijft afzonderlijk."
        )
    )
    for goal in summary.goals:
        if goal.note is not None or goal.priority is not None:
            parts.append(
                paragraph(
                    f"{goal.name}: prioriteit {goal.priority or 'onbekend'}; toelichting {goal.note or 'onbekend'}."
                )
            )
    return "".join(parts) + "</section>"


def metadata_section(data: ReportData) -> str:
    metadata = data.metadata
    parts = [
        section("metadata", "Snapshot en metadata"),
        paragraph(
            "Identiteit van de eenmalig gelezen context. Dit rapport introduceert geen wijzigingshistorie. Bevat mogelijk gevoelige gegevens; bewaar buiten Git."
        ),
        "<dl>",
    ]
    for label, value in (
        ("Rapportcontract", metadata.report_version),
        ("CLI-contract", metadata.contract_version),
        ("Contextschema", metadata.context_schema),
        ("Contextidentiteit", metadata.context_id),
        ("SHA-256 snapshotbytes", metadata.context_sha256),
        ("Referentiedatum", metadata.reference_date),
        ("Selectie vanaf", metadata.from_date),
        ("Selectie t/m", metadata.to_date),
    ):
        parts.append(f"<dt>{text(label)}</dt><dd>{text(value)}</dd>")
    parts.append("</dl></section>")
    return "".join(parts)


def render_report(data: ReportData) -> str:
    parts = [
        '<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>Topo 2 · Financiële foto</title><style>',
        CSS,
        '</style></head><body><main><header><p class="eyebrow">Topo 2 · lokaal rapport</p><h1>Je financiële context</h1>',
        paragraph(f"Referentiedatum verwachtingen: {data.metadata.reference_date}."),
        paragraph(f"Transactieselectie: {period_label(data)}."),
        paragraph(
            "Bekende gegevens geven direct inzicht. Onbekend betekent dat persoonlijke gegevens ontbreken, niet dat je eerst alles moet invullen."
        ),
        "</header>",
    ]
    # Present useful sections before empty ones, without making data collection
    # a prerequisite. Order within each group stays predictable.
    sections = [
        (
            bool(data.context.accounts or data.context.assets or data.context.debts),
            photo_section,
        ),
        (bool(data.realized.count), realized_section),
        (bool(data.expectations.currencies), expectations_section),
        (bool(data.context.goals), goals_section),
    ]
    for available in (True, False):
        for has_data, renderer in sections:
            if has_data == available:
                parts.append(renderer(data))
    parts.extend([metadata_section(data), "</main></body></html>"])
    return "".join(parts)
