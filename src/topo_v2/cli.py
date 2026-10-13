from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from topo_v2 import engine, storage
from topo_v2.models import (
    CONTRACT_VERSION,
    ChangeRequest,
    ChangeResult,
    Context,
    Summary,
)


def contract(command: str | None = None) -> dict[str, Any]:
    commands: dict[str, dict[str, Any]] = {
        "init": {"output": Context.model_json_schema(mode="serialization")},
        "show": {"output": Context.model_json_schema(mode="serialization")},
        "change": {
            "input": ChangeRequest.model_json_schema(),
            "output": ChangeResult.model_json_schema(mode="serialization"),
        },
        "summary": {"output": Summary.model_json_schema(mode="serialization")},
        "contract": {"description": "Discover command result and change input schemas"},
    }
    if command is not None:
        return commands[command]
    return {"contract_version": CONTRACT_VERSION, "commands": commands}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Topo 2: current wealth and goals")
    parser.add_argument(
        "--version", action="version", version=f"topo2 {version('topo-context-engine')}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "show", "change", "summary", "contract"):
        command = commands.add_parser(name)
        command.add_argument(
            "--json", action="store_true", help="Machine-readable output (default)"
        )
        if name == "contract":
            command.add_argument(
                "schema",
                nargs="?",
                choices=["init", "show", "change", "summary", "contract"],
            )
        else:
            command.add_argument("--context", type=Path, default=Path("context.json"))
        if name == "change":
            command.add_argument(
                "--request", type=Path, help="JSON request; otherwise read stdin"
            )
    args = parser.parse_args(argv)
    try:
        result: BaseModel | dict[str, Any]
        if args.command == "contract":
            result = contract(args.schema)
        elif args.command == "init":
            result = engine.initialize(args.context)
        elif args.command == "show":
            result = storage.read(args.context)[1]
        elif args.command == "summary":
            result = engine.summarize(storage.read(args.context)[1])
        else:
            payload = (
                args.request.read_text(encoding="utf-8")
                if args.request
                else sys.stdin.read()
            )
            result = engine.change(
                args.context, ChangeRequest.model_validate_json(payload)
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
