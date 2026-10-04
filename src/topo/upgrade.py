"""Upgrade a standalone Topo executable from the official GitHub release."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import cast

from topo import __version__

RELEASE_API = "https://api.github.com/repos/Trojaan/topo/releases/latest"
RELEASE_DOWNLOAD = "https://github.com/Trojaan/topo/releases/download"
MAX_ARCHIVE_BYTES = 150_000_000
MAX_BINARY_BYTES = 300_000_000
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class UpgradeError(Exception):
    """An upgrade cannot be completed safely."""


def _version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise UpgradeError(f"Invalid release version: {value}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _platform_asset() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    os_name = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(system)
    arch = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine)
    if os_name is None or arch is None or (os_name == "windows" and arch != "amd64"):
        raise UpgradeError(f"Unsupported platform: {system} {machine}")
    return f"topo-{os_name}-{arch}.zip", "topo.exe" if system == "Windows" else "topo"


def _read_url(url: str, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"topo/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(limit + 1)
    except (OSError, urllib.error.URLError) as error:
        raise UpgradeError(f"Could not download {url}: {error}") from error
    if len(data) > limit:
        raise UpgradeError("Release download exceeds the size limit")
    return cast(bytes, data)


def _latest_version() -> str:
    try:
        payload = json.loads(_read_url(RELEASE_API, 1_000_000))
        tag = payload["tag_name"]
    except (ValueError, KeyError, TypeError) as error:
        raise UpgradeError("GitHub returned an invalid latest release") from error
    if not isinstance(tag, str):
        raise UpgradeError("GitHub returned an invalid latest release")
    _version(tag)
    return tag


def _verify_binary(path: Path, version: str) -> None:
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpgradeError(f"Downloaded executable cannot run: {error}") from error
    if result.returncode != 0 or result.stdout.strip() != f"topo {version}":
        raise UpgradeError("Downloaded executable reports a different version")


def _schedule_windows_replace(staged: Path, target: Path) -> None:
    # Windows keeps the running executable locked. A separate PowerShell process
    # waits for this process to exit, then replaces it in the same directory.
    script = staged.with_suffix(".upgrade.ps1")
    script.write_text(
        "param([int]$ParentPid, [string]$Staged, [string]$Target, [string]$Script)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "try { Wait-Process -Id $ParentPid -ErrorAction SilentlyContinue } catch {}\n"
        "try { [System.IO.File]::Replace($Staged, $Target, $null) }\n"
        "finally { Remove-Item -LiteralPath $Script -Force -ErrorAction SilentlyContinue }\n",
        encoding="utf-8",
    )
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-ParentPid",
                str(os.getpid()),
                "-Staged",
                str(staged),
                "-Target",
                str(target),
                "-Script",
                str(script),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    except OSError:
        script.unlink(missing_ok=True)
        raise


def upgrade() -> dict[str, str]:
    if not getattr(sys, "frozen", False):
        raise UpgradeError(
            "This Topo runs from Python. Update it with your package manager "
            "(for example: uv tool upgrade topo-context-engine)."
        )
    target = Path(sys.executable).resolve()
    asset, binary_name = _platform_asset()
    latest = _latest_version()
    if _version(latest) <= _version(__version__):
        return {"status": "current", "version": __version__, "path": str(target)}

    archive_bytes = _read_url(f"{RELEASE_DOWNLOAD}/{latest}/{asset}", MAX_ARCHIVE_BYTES)
    with tempfile.TemporaryDirectory(prefix="topo-upgrade-") as download_dir:
        archive = Path(download_dir) / asset
        archive.write_bytes(archive_bytes)
        try:
            with zipfile.ZipFile(archive) as source:
                members = source.infolist()
                if len(members) != 1 or members[0].filename != binary_name:
                    raise UpgradeError("Release archive has unexpected contents")
                if members[0].file_size > MAX_BINARY_BYTES:
                    raise UpgradeError("Release executable exceeds the size limit")
                staged_fd, staged_name = tempfile.mkstemp(
                    prefix=".topo-upgrade-", suffix=target.suffix, dir=target.parent
                )
                staged = Path(staged_name)
                try:
                    with (
                        os.fdopen(staged_fd, "wb") as output,
                        source.open(members[0]) as input_file,
                    ):
                        total = 0
                        while chunk := input_file.read(1024 * 1024):
                            total += len(chunk)
                            if total > MAX_BINARY_BYTES:
                                raise UpgradeError(
                                    "Release executable exceeds the size limit"
                                )
                            output.write(chunk)
                    staged.chmod(0o755)
                    _verify_binary(staged, latest.removeprefix("v"))
                    if os.name == "nt":
                        _schedule_windows_replace(staged, target)
                        status = "scheduled"
                    else:
                        os.replace(staged, target)
                        status = "upgraded"
                finally:
                    if (
                        os.name != "nt"
                        or not staged.with_suffix(".upgrade.ps1").exists()
                    ):
                        staged.unlink(missing_ok=True)
        except (OSError, zipfile.BadZipFile) as error:
            raise UpgradeError(f"Could not install release: {error}") from error
    return {"status": status, "version": latest.removeprefix("v"), "path": str(target)}
