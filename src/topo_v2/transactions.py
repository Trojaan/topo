from __future__ import annotations

import csv
import io
from decimal import localcontext
from typing import Literal

from pydantic import TypeAdapter

from topo_v2.models import (
    AggregateCoverage,
    Context,
    Movement,
    Transaction,
    TransactionAggregateQuery,
    TransactionAggregateResult,
    TransactionChanges,
    TransactionCoverage,
    TransactionFilters,
    TransactionGroup,
    TransactionQuery,
    TransactionQueryResult,
    TransactionTotals,
)

TRANSACTIONS = TypeAdapter(list[Transaction])
REQUIRED_COLUMNS = {
    "id",
    "account_id",
    "booking_date",
    "amount",
    "currency",
    "description",
}
OPTIONAL_COLUMNS = {"category", "source", "kind"}


def parse_transactions(raw: bytes, format: Literal["json", "csv"]) -> list[Transaction]:
    if format == "json":
        return TRANSACTIONS.validate_json(raw)
    reader = csv.DictReader(
        io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True
    )
    try:
        columns = reader.fieldnames
    except csv.Error as error:
        raise ValueError(f"Invalid CSV: {error}") from error
    if (
        columns is None
        or len(columns) != len(set(columns))
        or not REQUIRED_COLUMNS.issubset(columns)
        or not set(columns).issubset(REQUIRED_COLUMNS | OPTIONAL_COLUMNS)
    ):
        raise ValueError(
            "CSV requires unique id, account_id, booking_date, amount, currency, description columns; category, source and kind are optional"
        )
    try:
        records = []
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row {line} has the wrong number of fields")
            for key in OPTIONAL_COLUMNS & row.keys():
                if row[key] == "":
                    del row[key]
            records.append(Transaction.model_validate(row))
        return records
    except csv.Error as error:
        raise ValueError(f"Invalid CSV: {error}") from error


def prepare_import(
    existing: list[Transaction], records: list[Transaction]
) -> tuple[TransactionChanges, int]:
    """Resolve omissions before comparing; explicit null still clears a label."""
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate transaction IDs in import")
    current = {record.id: record for record in existing}
    changes = TransactionChanges()
    skipped = 0
    for record in records:
        previous = current.get(record.id)
        if previous is None:
            changes.add.append(record)
            continue
        effective = Transaction.model_validate(
            {
                **previous.model_dump(),
                **record.model_dump(exclude_unset=True),
            }
        )
        if effective == previous:
            skipped += 1
        else:
            changes.update.append(effective)
    return changes, skipped


def matches_transaction(record: Transaction, query: TransactionFilters) -> bool:
    needle = query.search.casefold() if query.search is not None else None
    return (
        (query.account_id is None or record.account_id == query.account_id)
        and (query.from_date is None or record.booking_date >= query.from_date)
        and (query.to_date is None or record.booking_date <= query.to_date)
        and (query.currency is None or record.currency == query.currency)
        and (query.category is None or record.category == query.category)
        and (query.min_amount is None or record.amount >= query.min_amount)
        and (query.max_amount is None or record.amount <= query.max_amount)
        and (
            needle is None
            or any(
                needle in value.casefold()
                for value in (
                    record.description,
                    record.category or "",
                    record.source or "",
                )
            )
        )
    )


def select_transactions(
    records: list[Transaction], query: TransactionQuery
) -> TransactionQueryResult:
    matched = [record for record in records if matches_transaction(record, query)]
    matched.sort(key=lambda record: (record.booking_date, record.id))
    return TransactionQueryResult(
        records=matched[query.offset : query.offset + query.limit],
        total=len(matched),
        offset=query.offset,
        limit=query.limit,
    )


def _add_movement(total: Movement, record: Transaction) -> None:
    total.count += 1
    total.net_movement += record.amount
    if record.amount > 0:
        total.receipts += record.amount
    elif record.amount < 0:
        total.outflows -= record.amount


def _add_total(total: TransactionTotals, record: Transaction) -> None:
    _add_movement(total, record)
    if record.kind in (None, "unknown"):
        total.unknown_count += 1
        _add_movement(total.unknown, record)
    else:
        total.classified_count += 1
        if record.kind == "income":
            total.income += record.amount
        elif record.kind == "expense":
            total.expenses -= record.amount
        else:
            _add_movement(total.internal_transfers, record)
    total.classified_net_cashflow = total.income - total.expenses
    total.classification_complete = total.unknown_count == 0


def aggregate_transactions(
    context: Context, query: TransactionAggregateQuery
) -> TransactionAggregateResult:
    """One transaction pass, with independent account coverage declarations."""
    totals: dict[str, TransactionTotals] = {}
    groups: dict[tuple[str, str | None, str | None], TransactionGroup] = {}
    with localcontext() as arithmetic:
        # Inputs allow 28 digits/8 places. Include headroom for mixed scales and N.
        arithmetic.prec = 40 + len(str(len(context.transactions)))
        for record in context.transactions:
            if not matches_transaction(record, query):
                continue
            if record.currency not in totals:
                totals[record.currency] = TransactionTotals(currency=record.currency)
            _add_total(totals[record.currency], record)
            if query.group_by:
                month = (
                    record.booking_date.isoformat()[:7]
                    if "month" in query.group_by
                    else None
                )
                category = record.category if "category" in query.group_by else None
                key = (record.currency, month, category)
                if key not in groups:
                    groups[key] = TransactionGroup(
                        currency=record.currency, month=month, category=category
                    )
                _add_total(groups[key], record)
    by_account: dict[str, list[TransactionCoverage]] = {}
    for account in context.accounts:
        if query.account_id is None or account.id == query.account_id:
            by_account[account.id] = []
    # Unknown explicit IDs stay visible instead of vacuously declaring coverage.
    if query.account_id is not None:
        by_account.setdefault(query.account_id, [])
    for interval in context.transaction_coverage:
        if interval.account_id in by_account:
            by_account[interval.account_id].append(interval)
    coverage = []
    for account_id, intervals in sorted(by_account.items()):
        intervals.sort(key=lambda item: (item.from_date, item.to_date, item.id))
        status: Literal["complete", "partial", "unknown", "declared"] = (
            "declared" if intervals else "unknown"
        )
        if query.from_date is not None and query.to_date is not None:
            start, end = query.from_date.toordinal(), query.to_date.toordinal()
            cursor = start
            intersects = False
            for interval in intervals:
                left = max(start, interval.from_date.toordinal())
                right = min(end, interval.to_date.toordinal())
                if left > right:
                    continue
                intersects = True
                if left <= cursor:
                    cursor = max(cursor, right + 1)
            status = (
                "complete" if cursor > end else "partial" if intersects else "unknown"
            )
        coverage.append(
            AggregateCoverage(account_id=account_id, status=status, intervals=intervals)
        )
    count = sum(item.count for item in totals.values())
    unknown = sum(item.unknown_count for item in totals.values())
    return TransactionAggregateResult(
        filters=query,
        count=count,
        classification_complete=unknown == 0 if count else None,
        totals=[totals[key] for key in sorted(totals)],
        groups=[
            groups[key]
            for key in sorted(
                groups,
                key=lambda key: (
                    key[0],
                    key[1] or "",
                    key[2] is not None,
                    key[2] or "",
                ),
            )
        ],
        coverage=coverage,
    )
