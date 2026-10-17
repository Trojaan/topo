"""Synthetic CLI journey for focused reads and partial updates."""

from pathlib import Path

from jsonschema import validate
from test_topo_v2_journey import run


def test_focused_read_patch_and_complete_update(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    options = ("--context", str(path))
    run("init", *options)
    schemas = run("contract")["result"]["commands"]
    request = {
        "accounts": {
            "add": [
                {
                    "id": "bank",
                    "label": "Synthetic",
                    "type": "savings",
                    "availability": "free",
                    "balance": "10",
                    "as_of": "2026-10-17",
                }
            ]
        },
        "transactions": {
            "add": [
                {
                    "id": "tx",
                    "account_id": "bank",
                    "booking_date": "2026-10-17",
                    "amount": "-1",
                    "currency": "EUR",
                    "description": "Synthetic",
                }
            ]
        },
    }
    request["confirmation_token"] = run("change", *options, request=request)["result"][
        "confirmation_token"
    ]
    run("change", *options, request=request)
    raw = path.read_bytes()
    selected = run("show", *options, "--sections", "accounts,cashflows,goals")["result"]
    assert set(selected) == {
        "schema_version",
        "context_id",
        "accounts",
        "cashflows",
        "goals",
    }
    assert selected["cashflows"] == [] and selected["goals"] == []
    validate(selected, schemas["show"]["output"])
    assert path.read_bytes() == raw
    patch = {"accounts": {"patch": [{"id": "bank", "balance": "20"}]}}
    validate(patch, schemas["change"]["input"])
    preview = run("change", *options, request=patch)["result"]
    assert preview["changes"][0]["after"]["availability"] == "free"
    assert path.read_bytes() == raw
    patch["confirmation_token"] = preview["confirmation_token"]
    run("change", *options, request=patch)
    assert run("show", *options)["result"]["transactions"][0]["id"] == "tx"
    patch.pop("confirmation_token")
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    noop = run("change", *options, request=patch)["result"]
    assert noop == {"status": "unchanged", "confirmation_token": None, "changes": []}
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    update = {
        "accounts": {
            "update": [{"id": "bank", "label": "Synthetic", "type": "savings"}]
        }
    }
    preview = run("change", *options, request=update)["result"]
    assert preview["changes"][0]["after"]["availability"] is None


def test_filtered_show_still_validates_transactions(tmp_path: Path) -> None:
    path = tmp_path / "synthetic-corrupt.json"
    path.write_text('{"context_id":"synthetic","transactions":[{"id":"broken"}]}')
    result = run(
        "show", "--context", str(path), "--sections", "accounts", success=False
    )
    assert result["error"]["code"] == "INVALID_DATA"


def test_help_version_and_invalid_sections_avoid_heavy_imports() -> None:
    import subprocess
    import sys

    for argument in (
        "--help",
        "--version",
        "show --help",
        "transactions --help",
        "show --sections unknown",
        "show --sections accounts,",
    ):
        code = f"""
import sys
from topo_v2.cli import main
try:
    main({argument.split()!r})
except SystemExit as result:
    assert result.code == {2 if "unknown" in argument or "accounts," in argument else 0}
assert 'pydantic' not in sys.modules
assert 'topo_v2.engine' not in sys.modules
"""
        process = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        assert process.returncode == 0, process.stdout + process.stderr
