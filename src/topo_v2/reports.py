"""Project one already-read snapshot using shared, tested engine outcomes."""

from __future__ import annotations

from hashlib import sha256

from topo_v2.cashflows import monthly_room
from topo_v2.models import Context, ContextQuery, TransactionAggregateQuery
from topo_v2.reading import read_context
from topo_v2.report_models import ReportData, ReportMetadata, ReportQuery
from topo_v2.transactions import aggregate_transactions


def build_report(context: Context, raw: bytes, query: ReportQuery) -> ReportData:
    return ReportData(
        metadata=ReportMetadata(
            **query.model_dump(include={"reference_date", "from_date", "to_date"}),
            context_schema=context.schema_version,
            context_id=context.context_id,
            context_sha256=sha256(raw).hexdigest(),
        ),
        context=read_context(context, ContextQuery()),
        expectations=monthly_room(
            context.cashflows,
            context.cashflow_settings,
            next(
                (item for item in context.inventories if item.id == "cashflows"), None
            ),
            query.reference_date,
        ),
        realized=aggregate_transactions(
            context,
            TransactionAggregateQuery(
                from_date=query.from_date, to_date=query.to_date, group_by=["month"]
            ),
        ),
    )
