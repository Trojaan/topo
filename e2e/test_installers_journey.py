from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from importlib.metadata import version
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.name == "nt",
    reason="Unix shell installer; Windows release has native smoke tests",
)


def release(
    directory: Path, command: str, version: str = "0.6.0", platform: str = "linux-amd64"
) -> None:
    with zipfile.ZipFile(directory / f"{command}-{platform}.zip", "w") as archive:
        archive.writestr(command, f"#!/bin/sh\necho '{command} {version}'\n")


def install(
    tmp_path: Path,
    version: str = "v0.6.0",
    system: str = "Linux",
    machine: str = "x86_64",
) -> subprocess.CompletedProcess[str]:
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir(exist_ok=True)
    curl = fakebin / "curl"
    curl.write_text(
        f"#!{sys.executable}\n"
        "import json, shutil, sys\n"
        "from pathlib import Path\n"
        f"directory = Path({str(tmp_path)!r})\n"
        "args = sys.argv[1:]\n"
        "if '-o' not in args:\n"
        "    print(json.dumps({'tag_name': 'v0.6.0'}))\n"
        "else:\n"
        "    url = next(arg for arg in args if arg.startswith('https://'))\n"
        "    source = directory / url.rsplit('/', 1)[-1]\n"
        "    if not source.exists():\n"
        "        sys.exit(22)\n"
        "    shutil.copyfile(source, args[args.index('-o') + 1])\n"
    )
    curl.chmod(0o755)
    uname = fakebin / "uname"
    uname.write_text(
        f'#!/bin/sh\ncase "$1" in -s) echo {system};; -m) echo {machine};; *) exit 1;; esac\n'
    )
    uname.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{fakebin}{os.pathsep}{os.environ['PATH']}",
        "TOPO_VERSION": version,
        "TOPO_INSTALL_DIR": str(tmp_path / "installed"),
        "GITHUB_ACTIONS": "true",
        "GITHUB_PATH": str(tmp_path / "github-path"),
    }
    return subprocess.run(
        ["bash", str(ROOT / "install.sh")],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


@pytest.mark.parametrize(
    ("system", "machine", "platform"),
    [("Linux", "x86_64", "linux-amd64"), ("Darwin", "arm64", "macos-arm64")],
)
def test_installer_delivers_both_commands(
    tmp_path: Path, system: str, machine: str, platform: str
) -> None:
    for command in ("topo", "topo2"):
        release(tmp_path, command, platform=platform)
    process = install(tmp_path, system=system, machine=machine)
    assert process.returncode == 0, process.stdout + process.stderr
    for command in ("topo", "topo2"):
        result = subprocess.run(
            [str(tmp_path / "installed" / command), "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == f"{command} 0.6.0"
    assert not list((tmp_path / "installed").glob(".*.new"))


def test_latest_version_installs_both_commands(tmp_path: Path) -> None:
    release(tmp_path, "topo")
    release(tmp_path, "topo2")
    process = install(tmp_path, version="")
    assert process.returncode == 0, process.stdout + process.stderr
    assert (tmp_path / "installed" / "topo2").exists()


def test_older_pinned_release_needs_only_topo(tmp_path: Path) -> None:
    release(tmp_path, "topo", version="0.5.0")
    process = install(tmp_path, version="v0.5.0")
    assert process.returncode == 0, process.stdout + process.stderr
    assert (tmp_path / "installed" / "topo").exists()
    assert not (tmp_path / "installed" / "topo2").exists()


@pytest.mark.parametrize("failure", ["missing", "wrong_version", "wrong_member"])
def test_invalid_second_download_preserves_existing_commands(
    tmp_path: Path, failure: str
) -> None:
    release(tmp_path, "topo")
    if failure == "wrong_version":
        release(tmp_path, "topo2", version="0.5.0")
    elif failure == "wrong_member":
        with zipfile.ZipFile(tmp_path / "topo2-linux-amd64.zip", "w") as archive:
            archive.writestr("unexpected", "not the executable")
    target = tmp_path / "installed"
    target.mkdir()
    for command in ("topo", "topo2"):
        (target / command).write_text(f"original {command}")
    process = install(tmp_path)
    assert process.returncode != 0
    for command in ("topo", "topo2"):
        assert (target / command).read_text() == f"original {command}"
    assert not list(target.glob(".*.new"))


def test_invalid_version_is_rejected_without_installation(tmp_path: Path) -> None:
    process = install(tmp_path, version="not-a-version")
    assert process.returncode != 0 and "invalid release version" in process.stderr
    assert not (tmp_path / "installed").exists()


def test_topo2_reports_package_version() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "topo_v2", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert process.stdout.strip() == f"topo2 {version('topo-context-engine')}"


def folder_release(
    directory: Path, release_version: str, marker: str, *, broken: bool = False
) -> None:
    runtime = f"_topo2_runtime_{release_version}"
    program = (
        "#!/bin/sh\n"
        f'test "$(cat "$(dirname "$0")/{runtime}/marker")" = "{marker}" || exit 1\n'
        f'echo "topo2 {release_version}"\n'
    )
    with zipfile.ZipFile(directory / "topo2-linux-amd64.zip", "w") as archive:
        archive.writestr("topo2", program)
        if not broken:
            archive.writestr(runtime + "/marker", marker)


def test_folder_install_upgrade_reinstall_and_failed_upgrade(tmp_path: Path) -> None:
    release(tmp_path, "topo", "0.9.0")
    folder_release(tmp_path, "0.9.0", "first")
    process = install(tmp_path, version="v0.9.0")
    assert process.returncode == 0, process.stdout + process.stderr
    target = tmp_path / "installed"
    assert (target / "_topo2_runtime_0.9.0" / "marker").read_text() == "first"
    assert install(tmp_path, version="v0.9.0").returncode == 0
    original = (target / "topo2").read_bytes()
    # A conflicting runtime cannot overwrite files used by the current version.
    folder_release(tmp_path, "0.9.0", "conflicting")
    assert install(tmp_path, version="v0.9.0").returncode != 0
    assert (target / "topo2").read_bytes() == original
    assert (target / "_topo2_runtime_0.9.0" / "marker").read_text() == "first"
    release(tmp_path, "topo", "0.10.0")
    folder_release(tmp_path, "0.10.0", "second", broken=True)
    assert install(tmp_path, version="v0.10.0").returncode != 0
    assert (target / "topo2").read_bytes() == original
    folder_release(tmp_path, "0.10.0", "second")
    process = install(tmp_path, version="v0.10.0")
    assert process.returncode == 0, process.stdout + process.stderr
    assert (target / "_topo2_runtime_0.9.0" / "marker").read_text() == "first"
    assert (target / "_topo2_runtime_0.10.0" / "marker").read_text() == "second"
    assert not list(target.glob(".*.new"))


def test_upgrade_from_single_binary_to_folder(tmp_path: Path) -> None:
    release(tmp_path, "topo")
    release(tmp_path, "topo2")
    assert install(tmp_path).returncode == 0
    release(tmp_path, "topo", "0.9.0")
    folder_release(tmp_path, "0.9.0", "synthetic")
    process = install(tmp_path, version="v0.9.0")
    assert process.returncode == 0, process.stdout + process.stderr
