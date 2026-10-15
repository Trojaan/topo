"""Report contracts and presentation data; no financial calculations."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from topo_v2.models import (
    CONTRACT_VERSION,
    CompactContext,
    Model,
    MonthlyRoom,
    TransactionAggregateResult,
)


class ReportQuery(Model):
    reference_date: date
    from_date: date | None = None
    to_date: date | None = None

    @model_validator(mode="after")
    def bounded_period(self) -> Self:
        if (self.from_date is None) != (self.to_date is None):
            raise ValueError("from_date and to_date must be supplied together")
        if (
            self.from_date is not None
            and self.to_date is not None
            and self.from_date > self.to_date
        ):
            raise ValueError("from_date must not follow to_date")
        return self


class ReportRequest(ReportQuery):
    output: Annotated[str, Field(min_length=1)]


class ReportMetadata(ReportQuery):
    report_version: Literal["topo2.report/1"] = "topo2.report/1"
    contract_version: Literal["topo2.cli/3"] = CONTRACT_VERSION
    context_schema: str
    context_id: str
    context_sha256: str


class ReportData(Model):
    metadata: ReportMetadata
    context: CompactContext
    expectations: MonthlyRoom
    realized: TransactionAggregateResult


class ReportResult(Model):
    output: str
    html_bytes: Annotated[int, Field(ge=0)]
    metadata: ReportMetadata
