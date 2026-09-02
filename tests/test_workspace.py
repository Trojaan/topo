from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from topo.workspace import AGENT_BLOCK, TOPO_END, TOPO_START, merge_managed_block

PROJECT_ROOT = Path(__file__).parents[1]


def run_topo(*args: str, cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "topo", *args],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def response(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(process.stdout))


def test_managed_block_preserves_user_content_and_line_endings() -> None:
    existing = "# Existing\r\n\r\nCustom instructions.\r\n"

    merged = merge_managed_block(existing, AGENT_BLOCK)
    updated = merge_managed_block(merged, AGENT_BLOCK)

    assert merged.startswith(existing)
    assert "\n" not in merged.replace("\r\n", "")
    assert merged.count(TOPO_START) == 1
    assert merged.count(TOPO_END) == 1
    assert updated == merged


@pytest.mark.parametrize(
    "existing",
    (
        f"{TOPO_START}\nmissing end\n",
        f"{TOPO_END}\n",
        f"{TOPO_START}\na\n{TOPO_END}\n{TOPO_START}\nb\n{TOPO_END}\n",
    ),
)
def test_managed_block_rejects_incomplete_or_duplicate_markers(existing: str) -> None:
    with pytest.raises(ValueError, match="incomplete or duplicate"):
        merge_managed_block(existing, AGENT_BLOCK)


def test_workspace_init_is_agent_ready_and_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "finances"

    initialized = run_topo("init", str(workspace), "--json")

    assert initialized.returncode == 0, initialized.stderr
    first = response(initialized)
    assert first["command"] == "workspace.init"
    assert first["outcome"] == "succeeded"
    assert first["result"]["context_created"] is True
    generation = first["result"]["generation_id"]
    assert (workspace / "context.topo" / "CURRENT").read_text().strip() == generation
    assert (workspace / "imports").is_dir()
    for filename in ("AGENTS.md", "CLAUDE.md"):
        content = (workspace / filename).read_text(encoding="utf-8")
        assert content.count(TOPO_START) == 1
        assert "Never edit files inside `context.topo/` directly" in content
        assert "Ask the user for meaningful missing information" in content
        assert "Do not inspect Topo's implementation" in content
        assert "use unrelated transactions as evidence" in content
        assert "report the contract gap" in content
        assert "Check the installed version with `topo --version`" in content
        assert (
            "curl -fsSL https://raw.githubusercontent.com/Trojaan/topo/main/install.sh"
            in content
        )
        assert (
            "irm https://raw.githubusercontent.com/Trojaan/topo/main/install.ps1 | iex"
            in content
        )
    gitignore = (workspace / ".gitignore").read_text(encoding="utf-8")
    assert "context.topo/" in gitignore
    assert "imports/" in gitignore

    repeated = run_topo("init", str(workspace), "--json")

    assert repeated.returncode == 0, repeated.stderr
    second = response(repeated)
    assert second["outcome"] == "no_change"
    assert second["generation_before"] == generation
    assert second["generation_after"] == generation
    assert second["result"]["context_created"] is False
    assert second["result"]["created_paths"] == []
    assert second["result"]["updated_paths"] == []


def test_workspace_init_updates_only_managed_agent_blocks(tmp_path: Path) -> None:
    workspace = tmp_path / "existing"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text(
        "# My project\n\nKeep this.\n", encoding="utf-8"
    )
    (workspace / "CLAUDE.md").write_text("Claude-specific.\n", encoding="utf-8")

    initialized = run_topo("init", str(workspace), "--json")

    assert initialized.returncode == 0, initialized.stderr
    assert (workspace / "AGENTS.md").read_text().startswith("# My project\n")
    assert "Keep this." in (workspace / "AGENTS.md").read_text()
    assert (workspace / "CLAUDE.md").read_text().startswith("Claude-specific.\n")

    (workspace / "AGENTS.md").write_text(
        (workspace / "AGENTS.md")
        .read_text()
        .replace("## Topo financial context", "## Stale Topo text"),
        encoding="utf-8",
    )
    refreshed = run_topo("init", str(workspace), "--json")
    assert refreshed.returncode == 0, refreshed.stderr
    assert "## Topo financial context" in (workspace / "AGENTS.md").read_text()
    assert response(refreshed)["result"]["updated_paths"] == ["AGENTS.md"]


def test_workspace_init_defaults_to_current_directory(tmp_path: Path) -> None:
    initialized = run_topo("init", "--json", cwd=tmp_path)

    assert initialized.returncode == 0, initialized.stderr
    assert response(initialized)["result"]["workspace"] == str(tmp_path)
    assert (tmp_path / "context.topo" / "CURRENT").is_file()


def test_workspace_init_preserves_existing_gitignore_content(tmp_path: Path) -> None:
    workspace = tmp_path / "existing-ignore"
    workspace.mkdir()
    gitignore = workspace / ".gitignore"
    gitignore.write_text(".venv/\ncustom-secret.txt\n", encoding="utf-8")

    initialized = run_topo("init", str(workspace), "--json")

    assert initialized.returncode == 0, initialized.stderr
    content = gitignore.read_text(encoding="utf-8")
    assert content.startswith(".venv/\ncustom-secret.txt\n")
    assert content.count(TOPO_START) == 1
    assert "context.topo/" in content
    assert "imports/" in content


def test_workspace_init_preserves_existing_crlf_files(tmp_path: Path) -> None:
    workspace = tmp_path / "crlf"
    workspace.mkdir()
    agents = workspace / "AGENTS.md"
    agents.write_bytes(b"# Existing\r\n\r\nKeep this.\r\n")

    initialized = run_topo("init", str(workspace), "--json")

    assert initialized.returncode == 0, initialized.stderr
    content = agents.read_bytes()
    assert b"Keep this.\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")


def test_workspace_init_refuses_marker_conflict_before_creating_context(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "conflict"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text(f"{TOPO_START}\n", encoding="utf-8")

    completed = run_topo("init", str(workspace), "--json")

    assert completed.returncode == 2
    assert response(completed)["diagnostics"][0]["code"] == "COMMAND_NOT_EXECUTABLE"
    assert not (workspace / "context.topo").exists()


def test_workspace_init_refuses_non_topo_context_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "not-topo"
    package = workspace / "context.topo"
    package.mkdir(parents=True)
    marker = package / "personal.txt"
    marker.write_text("preserve", encoding="utf-8")

    completed = run_topo("init", str(workspace), "--json")

    assert completed.returncode == 2
    assert (
        "not a Topo context package"
        in response(completed)["diagnostics"][0]["params"]["reason"]
    )
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert list(package.iterdir()) == [marker]


def test_workspace_init_refuses_a_corrupted_topo_package(tmp_path: Path) -> None:
    workspace = tmp_path / "corrupted"
    initialized = run_topo("init", str(workspace), "--json")
    assert initialized.returncode == 0, initialized.stderr
    generation = (workspace / "context.topo" / "CURRENT").read_text().strip()
    manifest = workspace / "context.topo" / "generations" / generation / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    before = manifest.read_bytes()

    repeated = run_topo("init", str(workspace), "--json")

    assert repeated.returncode == 2
    assert response(repeated)["diagnostics"][0]["code"] == "PACKAGE_INTEGRITY_FAILED"
    assert manifest.read_bytes() == before


def test_workspace_init_has_human_output_and_context_status_contract(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "human"
    initialized = run_topo("init", str(workspace))

    assert initialized.returncode == 0, initialized.stderr
    assert initialized.stdout.startswith(f"Initialized: {workspace}")
    assert "topo context status --package ./context.topo --json" in initialized.stdout

    status = run_topo(
        "context", "status", "--package", str(workspace / "context.topo"), "--json"
    )
    assert status.returncode == 0, status.stderr
    body = response(status)
    assert body["command"] == "context.status"
    assert body["outcome"] == "succeeded"
    assert body["generation_before"] == body["generation_after"]
    assert body["result"]["context_id"] == body["context_id"]
    assert body["result"]["person_id"]
    assert body["result"]["household_id"]
    assert body["result"]["modules"]
