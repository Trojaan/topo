from __future__ import annotations

import csv
import io
from typing import Literal

from pydantic import TypeAdapter

from topo_v2.models import (
    Transaction,
    TransactionQuery,
    TransactionQueryResult,
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
OPTIONAL_COLUMNS = {"category", "source"}


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
            "CSV requires unique id, account_id, booking_date, amount, currency, description columns; category and source are optional"
        )
    try:
        records = []
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row {line} has the wrong number of fields")
            for key in OPTIONAL_COLUMNS & row.keys():
                if row[key] == "":
                    row[key] = None
            records.append(Transaction.model_validate(row))
        return records
    except csv.Error as error:
        raise ValueError(f"Invalid CSV: {error}") from error


def select_transactions(
    records: list[Transaction], query: TransactionQuery
) -> TransactionQueryResult:
    needle = query.search.casefold() if query.search is not None else None
    matched = [
        record
        for record in records
        if (query.account_id is None or record.account_id == query.account_id)
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
    ]
    matched.sort(key=lambda record: (record.booking_date, record.id))
    return TransactionQueryResult(
        records=matched[query.offset : query.offset + query.limit],
        total=len(matched),
        offset=query.offset,
        limit=query.limit,
    )
