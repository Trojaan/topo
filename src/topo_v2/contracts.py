from __future__ import annotations

from typing import Any

from topo_v2.models import (
    CONTRACT_VERSION,
    ChangeRequest,
    ChangeResult,
    CompactContext,
    Context,
    ContextQuery,
    MonthlyRoom,
    MonthlyRoomQuery,
    Summary,
    TransactionAggregateQuery,
    TransactionAggregateResult,
    TransactionImportOptions,
    TransactionImportResult,
    TransactionQuery,
    TransactionQueryResult,
)
from topo_v2.report_models import ReportRequest, ReportResult
from topo_v2.transactions import (
    TRANSACTIONS,
)


def contract(command: str | None = None) -> dict[str, Any]:
    commands: dict[str, dict[str, Any]] = {
        "init": {"output": Context.model_json_schema(mode="serialization")},
        "context": {
            "input": ContextQuery.model_json_schema(),
            "output": CompactContext.model_json_schema(mode="serialization"),
        },
        "show": {
            "description": "Full context by default; --sections returns identity and only selected data sections. Full storage validation is retained.",
            "options": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sections": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "enum": [
                                name
                                for name in Context.model_fields
                                if name not in ("schema_version", "context_id")
                            ]
                        },
                    }
                },
            },
            "output": Context.model_json_schema(mode="serialization"),
        },
        "change": {
            "input": ChangeRequest.model_json_schema(),
            "output": ChangeResult.model_json_schema(mode="serialization"),
            "options": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Repeat --source PATH to bind exact source bytes; relative paths use the working directory",
                    }
                },
            },
        },
        "report": {
            "description": "Offline HTML from one snapshot; explicit output/date; never overwrites. No period selects all stored transactions without claiming coverage.",
            "input": ReportRequest.model_json_schema(),
            "output": ReportResult.model_json_schema(mode="serialization"),
        },
        "summary": {"output": Summary.model_json_schema(mode="serialization")},
        "monthly-room": {
            "input": MonthlyRoomQuery.model_json_schema(),
            "output": MonthlyRoom.model_json_schema(mode="serialization"),
        },
        "import-transactions": {
            "description": (
                "Upsert by stable ID. Omitted category/source/kind and empty optional CSV "
                "cells preserve existing enrichments; JSON null clears, supplied labels "
                "replace. Other fields are required. change.update still replaces "
                "complete records. Identical effective imports do not write."
            ),
            "input": TRANSACTIONS.json_schema(),
            "options": TransactionImportOptions.model_json_schema(),
            "output": TransactionImportResult.model_json_schema(mode="serialization"),
        },
        "aggregate-transactions": {
            "input": TransactionAggregateQuery.model_json_schema(),
            "output": TransactionAggregateResult.model_json_schema(
                mode="serialization"
            ),
        },
        "transactions": {
            "input": TransactionQuery.model_json_schema(),
            "output": TransactionQueryResult.model_json_schema(mode="serialization"),
        },
        "contract": {"description": "Discover command result and change input schemas"},
    }
    if command is not None:
        return commands[command]
    return {"contract_version": CONTRACT_VERSION, "commands": commands}
