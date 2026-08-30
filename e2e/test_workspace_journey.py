from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def run_topo(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "topo", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def body(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert process.stdout, process.stderr
    return cast(dict[str, Any], json.loads(process.stdout))


def test_user_initializes_an_agent_ready_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "household-finances"

    initialized = run_topo("init", str(workspace), "--json")
    assert initialized.returncode == 0, initialized.stderr
    init_body = body(initialized)
    assert init_body["command"] == "workspace.init"
    assert init_body["outcome"] == "succeeded"
    assert init_body["result"]["created_paths"] == [
        ".gitignore",
        "AGENTS.md",
        "CLAUDE.md",
        "context.topo/",
        "imports/",
    ]

    package = workspace / "context.topo"
    status = run_topo("context", "status", "--package", str(package), "--json")
    assert status.returncode == 0, status.stderr
    status_body = body(status)
    assert status_body["result"]["context_id"] == init_body["result"]["context_id"]
    assert (
        status_body["result"]["generation_id"] == init_body["result"]["generation_id"]
    )
    assert status_body["generation_before"] == status_body["generation_after"]

    repeated = run_topo("init", str(workspace), "--json")
    assert repeated.returncode == 0, repeated.stderr
    repeated_body = body(repeated)
    assert repeated_body["outcome"] == "no_change"
    assert repeated_body["generation_before"] == status_body["generation_after"]
    assert (workspace / "AGENTS.md").read_text().count("<!-- topo:start -->") == 1
    assert (workspace / "CLAUDE.md").read_text().count("<!-- topo:start -->") == 1
