from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from topo_v2 import engine, storage
from topo_v2.cashflows import monthly_room
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
from topo_v2.reading import read_context
from topo_v2.report_files import publish_report
from topo_v2.report_html import render_report
from topo_v2.report_models import ReportRequest, ReportResult
from topo_v2.reports import build_report
from topo_v2.transactions import (
    TRANSACTIONS,
    aggregate_transactions,
    select_transactions,
)


def contract(command: str | None = None) -> dict[str, Any]:
    commands: dict[str, dict[str, Any]] = {
        "init": {"output": Context.model_json_schema(mode="serialization")},
        "context": {
            "input": ContextQuery.model_json_schema(),
            "output": CompactContext.model_json_schema(mode="serialization"),
        },
        "show": {"output": Context.model_json_schema(mode="serialization")},
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Topo 2: financial context, transactions and goals"
    )
    parser.add_argument(
        "--version", action="version", version=f"topo2 {version('topo-context-engine')}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    command_names = (
        "init",
        "show",
        "context",
        "change",
        "summary",
        "contract",
        "import-transactions",
        "transactions",
        "aggregate-transactions",
        "monthly-room",
        "report",
    )
    for name in command_names:
        command = commands.add_parser(name)
        command.add_argument(
            "--json", action="store_true", help="Machine-readable output (default)"
        )
        if name == "contract":
            command.add_argument(
                "schema",
                nargs="?",
                choices=command_names,
            )
        else:
            command.add_argument("--context", type=Path, default=Path("context.json"))
        if name == "report":
            command.add_argument("--output", required=True)
            command.add_argument("--from-date")
            command.add_argument("--to-date")
        if name in ("monthly-room", "report"):
            command.add_argument("--reference-date", required=True)
        if name == "context":
            command.add_argument("--reference-date")
            command.add_argument("--max-age-days", type=int)
        if name == "change":
            command.add_argument(
                "--request", type=Path, help="JSON request; otherwise read stdin"
            )
            command.add_argument(
                "--source",
                type=Path,
                action="append",
                default=[],
                help="Bind this source file to the preview; repeat for multiple sources",
            )
        if name == "import-transactions":
            command.add_argument("--file", type=Path, required=True)
            command.add_argument("--format", choices=["json", "csv"], required=True)
            command.add_argument("--confirmation-token")
            command.add_argument("--details", action="store_true")
        if name == "aggregate-transactions":
            command.add_argument(
                "--group-by", choices=["month", "category"], action="append", default=[]
            )
        if name in ("transactions", "aggregate-transactions"):
            command.add_argument("--account", dest="account_id")
            command.add_argument("--from-date")
            command.add_argument("--to-date")
            command.add_argument("--currency")
            command.add_argument("--category")
            command.add_argument("--min-amount")
            command.add_argument("--max-amount")
            command.add_argument("--search")
        if name == "transactions":
            command.add_argument(
                "--offset",
                type=int,
                default=TransactionQuery.model_fields["offset"].default,
            )
            command.add_argument(
                "--limit",
                type=int,
                default=TransactionQuery.model_fields["limit"].default,
            )
    args = parser.parse_args(argv)
    try:
        result: BaseModel | dict[str, Any]
        if args.command == "contract":
            result = contract(args.schema)
        elif args.command == "init":
            result = engine.initialize(args.context)
        elif args.command == "report":
            report_request = ReportRequest.model_validate(
                {key: getattr(args, key) for key in ReportRequest.model_fields}
            )
            raw, context = storage.read(args.context)
            report_data = build_report(context, raw, report_request)
            html_payload = render_report(report_data).encode("utf-8")
            output_path = Path(report_request.output).absolute()
            publish_report(output_path, html_payload)
            result = ReportResult(
                output=str(output_path),
                html_bytes=len(html_payload),
                metadata=report_data.metadata,
            )
        elif args.command == "show":
            result = storage.read(args.context)[1]
        elif args.command == "context":
            query_context = ContextQuery.model_validate(
                {
                    "reference_date": args.reference_date,
                    "max_age_days": args.max_age_days,
                }
            )
            result = read_context(storage.read(args.context)[1], query_context)
        elif args.command == "monthly-room":
            monthly_query = MonthlyRoomQuery.model_validate(
                {"reference_date": args.reference_date}
            )
            context = storage.read(args.context)[1]
            result = monthly_room(
                context.cashflows,
                context.cashflow_settings,
                next(
                    (item for item in context.inventories if item.id == "cashflows"),
                    None,
                ),
                monthly_query.reference_date,
            )
        elif args.command == "summary":
            result = engine.summarize(storage.read(args.context)[1])
        elif args.command == "aggregate-transactions":
            aggregate_query = TransactionAggregateQuery.model_validate(
                {
                    key: getattr(args, key)
                    for key in TransactionAggregateQuery.model_fields
                }
            )
            result = aggregate_transactions(
                storage.read(args.context)[1], aggregate_query
            )
        elif args.command == "transactions":
            query = TransactionQuery.model_validate(
                {key: getattr(args, key) for key in TransactionQuery.model_fields}
            )
            result = select_transactions(
                storage.read(args.context)[1].transactions, query
            )
        elif args.command == "import-transactions":
            options = TransactionImportOptions.model_validate(
                {
                    "format": args.format,
                    "confirmation_token": args.confirmation_token,
                    "details": args.details,
                }
            )
            result = engine.import_transactions(
                args.context, args.file.read_bytes(), options
            )
        else:
            payload = (
                args.request.read_text(encoding="utf-8")
                if args.request
                else sys.stdin.read()
            )
            result = engine.change(
                args.context, ChangeRequest.model_validate_json(payload), args.source
            )
        output = (
            result.model_dump(mode="json") if isinstance(result, BaseModel) else result
        )
        print(
            json.dumps(
                {
                    "contract_version": CONTRACT_VERSION,
                    "command": args.command,
                    "result": output,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (ValueError, OSError) as error:
        code = (
            "STALE_CONFIRMATION"
            if isinstance(error, engine.StaleConfirmation)
            else "INVALID_CHANGE"
            if isinstance(error, engine.ChangeError)
            else "INVALID_DATA"
            if isinstance(error, ValidationError)
            else "IO_ERROR"
            if isinstance(error, OSError)
            else "INVALID_DATA"
        )
        print(
            json.dumps(
                {
                    "contract_version": CONTRACT_VERSION,
                    "command": args.command,
                    "error": {"code": code, "message": str(error)},
                },
                ensure_ascii=False,
            )
        )
        return 1
