from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from topo import upgrade as updater


@pytest.fixture(autouse=True)
def installed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    # Upgrade scenarios must not depend on the version of the test checkout.
    monkeypatch.setattr(updater, "__version__", "0.4.0")


def _archive(name: str, contents: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        output.writestr(name, contents)
    return buffer.getvalue()


def test_python_install_refuses_self_update(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    with pytest.raises(updater.UpgradeError, match="package manager"):
        updater.upgrade()


@pytest.mark.skipif(os.name == "nt", reason="Unix executable replacement")
def test_upgrade_replaces_only_after_verifying_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "topo"
    current.write_text("old binary", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(current))
    asset, binary = updater._platform_asset()
    metadata = json.dumps({"tag_name": "v0.5.0"}).encode()
    executable = b"#!/bin/sh\necho 'topo 0.5.0'\n"
    release = _archive(binary, executable)
    downloaded_urls: list[str] = []

    def download(url: str, limit: int) -> bytes:
        assert limit > 0
        downloaded_urls.append(url)
        return metadata if url == updater.RELEASE_API else release

    monkeypatch.setattr(updater, "_read_url", download)
    result = updater.upgrade()
    assert result == {"status": "upgraded", "version": "0.5.0", "path": str(current)}
    assert current.read_bytes() == executable
    assert not list(tmp_path.glob(".topo-upgrade-*"))
    assert downloaded_urls == [
        updater.RELEASE_API,
        f"{updater.RELEASE_DOWNLOAD}/v0.5.0/{asset}",
    ]


@pytest.mark.skipif(os.name == "nt", reason="Unix executable replacement")
def test_bad_release_does_not_replace_installed_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "topo"
    current.write_text("old binary", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(current))
    monkeypatch.setattr(
        updater,
        "_read_url",
        lambda url, limit: (
            b'{"tag_name":"v0.5.0"}'
            if url == updater.RELEASE_API
            else _archive("unexpected", b"bad binary")
        ),
    )
    with pytest.raises(updater.UpgradeError, match="unexpected contents"):
        updater.upgrade()
    assert current.read_text(encoding="utf-8") == "old binary"
    assert not list(tmp_path.glob(".topo-upgrade-*"))


@pytest.mark.skipif(os.name == "nt", reason="Unix executable replacement")
def test_version_mismatch_does_not_replace_installed_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "topo"
    current.write_text("old binary", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(current))
    _, binary = updater._platform_asset()
    monkeypatch.setattr(
        updater,
        "_read_url",
        lambda url, limit: (
            b'{"tag_name":"v0.5.0"}'
            if url == updater.RELEASE_API
            else _archive(binary, b"#!/bin/sh\necho 'topo 0.6.0'\n")
        ),
    )
    with pytest.raises(updater.UpgradeError, match="different version"):
        updater.upgrade()
    assert current.read_text(encoding="utf-8") == "old binary"
    assert not list(tmp_path.glob(".topo-upgrade-*"))


def test_current_version_skips_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    current = tmp_path / "topo"
    current.write_text("old binary", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(current))
    monkeypatch.setattr(updater, "_platform_asset", lambda: ("topo-test.zip", "topo"))

    def download(url: str, limit: int) -> bytes:
        assert url == updater.RELEASE_API
        return b'{"tag_name":"v0.4.0"}'

    monkeypatch.setattr(updater, "_read_url", download)
    assert updater.upgrade()["status"] == "current"
    assert current.read_text(encoding="utf-8") == "old binary"


def test_windows_helper_waits_for_cli_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = tmp_path / ".topo-upgrade-test.exe"
    target = tmp_path / "topo.exe"
    launched: list[list[str]] = []

    def launch(arguments: list[str], **kwargs: object) -> object:
        assert kwargs["close_fds"] is True
        launched.append(arguments)
        return object()

    monkeypatch.setattr(subprocess, "Popen", launch)
    updater._schedule_windows_replace(staged, target)
    script = staged.with_suffix(".upgrade.ps1")
    contents = script.read_text(encoding="utf-8")
    assert "Wait-Process -Id $ParentPid" in contents
    assert "[System.IO.File]::Replace($Staged, $Target, $null)" in contents
    assert launched[0][0] == "powershell.exe"
    assert launched[0][launched[0].index("-Staged") + 1] == str(staged)
    assert launched[0][launched[0].index("-Target") + 1] == str(target)
