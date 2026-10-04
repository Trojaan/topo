"""Synthetic storage benchmark, with a conservative full-validation reference.

The reference uses the same invariants and publication logic, but disables typed
record reuse, collection-byte reuse and the supplied delta change set. It also uses the previous metadata traversal and retains
the new engine's change-set calculation, so is not a pristine pre-change binary.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast

from benchmark_reads import _build_fixture, _operation_id, _package_bytes, _records

from topo.errors import PackageIntegrityError

ROOT = Path(__file__).resolve().parents[1]
SHIM = """
import cProfile, json, pstats, resource, runpy, sys
profile = cProfile.Profile()
profile.enable()
sys.argv = ['topo', *sys.argv[1:]]
try:
    runpy.run_module('topo', run_name='__main__')
finally:
    profile.disable()
    phases = dict.fromkeys(['read', 'parse', 'semantic', 'serialize', 'storage_sync', 'other'], 0.0)
    stats = pstats.Stats(profile).stats
    for (filename, line, name), (cc, nc, tt, ct, callers) in stats.items():
        phase = 'other'
        if name in {'read', 'read_bytes', 'read_text', '<built-in method io.open>', '<built-in method _io.open>', "<method 'read' of '_io.BufferedReader' objects>", "<method '__exit__' of '_io._IOBase' objects>"}:
            phase = 'read'
        elif 'validate_json' in name or filename.endswith('/json/decoder.py') or name in {'loads', 'load'}:
            phase = 'parse'
        elif filename.endswith('/json/encoder.py') or name in {'dumps', 'model_dump', 'to_python'}:
            phase = 'serialize'
        elif filename.endswith('/canonical_validation.py') or '/jsonschema/' in filename:
            phase = 'semantic'
        elif filename.endswith('/storage.py') or name in {'fsync', 'write', 'replace'}:
            phase = 'storage_sync'
        phases[phase] += tt
    print('__PROFILE__=' + json.dumps({'exclusive_seconds': phases, 'peak_rss': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'top_exclusive': [{'function': key[2], 'file': key[0].split('/')[-1], 'seconds': value[2]} for key, value in sorted(stats.items(), key=lambda item: item[1][2], reverse=True)[:20]]}), file=sys.stderr)
"""


def _reference_canonical_digest(package: Path) -> str:
    digest = hashlib.sha256()
    paths = [package / "CURRENT", package / "storage-format.json"]
    for relative in ("generations", "history", "evidence/records"):
        for path in (package / relative).rglob("*"):
            if path.is_symlink():
                raise PackageIntegrityError(
                    "canonical package contains a symbolic link"
                )
            paths.append(path)
    for path in sorted(paths):
        if path.is_symlink():
            raise PackageIntegrityError("canonical package contains an invalid file")
        digest.update(b"D" if path.is_dir() else b"F")
        digest.update(str(path.relative_to(package)).encode())
        digest.update(b"\0")
        if path.is_file():
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        elif not path.is_dir():
            raise PackageIntegrityError("canonical package contains an invalid file")
        digest.update(b"\0")
    return digest.hexdigest()


def invoke(
    package: Path,
    words: tuple[str, ...],
    request: dict[str, Any] | None,
    source: Path,
    *,
    profile: bool = False,
) -> tuple[dict[str, Any], float, dict[str, Any] | None]:
    env = {**os.environ, "PYTHONPATH": str(source)}
    command = (
        [sys.executable, "-c", SHIM] if profile else [sys.executable, "-m", "topo"]
    )
    started = time.perf_counter()
    completed = subprocess.run(
        [*command, *words, "--package", str(package), "--json"],
        input=json.dumps(request or {"contract_version": "topo.cli/0.1"}),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode:
        raise RuntimeError(completed.stdout or completed.stderr)
    measurement = None
    for line in completed.stderr.splitlines():
        if line.startswith("__PROFILE__="):
            measurement = json.loads(line.removeprefix("__PROFILE__="))
            measurement["peak_rss_mib"] = measurement.pop("peak_rss") / (
                1024 * 1024 if platform.system() == "Darwin" else 1024
            )
    return cast(dict[str, Any], json.loads(completed.stdout)), elapsed, measurement


def mutation(identity: dict[str, Any], index: int, offset: int) -> dict[str, Any]:
    return {
        "contract_version": "topo.cli/0.1",
        "operation_id": _operation_id(900000 + index),
        "context_id": identity["context_id"],
        "expected_generation": identity["generation_id"],
        "actor": {
            "actor_type": "source_adapter",
            "actor_id": "adapter.synthetic-performance",
        },
        "reason": "Synthetic mutation benchmark",
        "adapter": {
            "adapter_id": "adapter.synthetic-performance",
            "adapter_version": "0.1.0",
        },
        "records": _records(offset, 1),
        "authorization": None,
    }


def authorize(package: Path, request: dict[str, Any], source: Path) -> float:
    preview, seconds, _ = invoke(package, ("source", "import"), request, source)
    request["authorization"] = {
        "preview_ref": preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "benchmark"},
        "authorized_at": "2026-10-04T12:00:00Z",
    }
    return seconds


def measure_submit_round(fixture: Path, work: Path) -> dict[str, Any]:
    """Compare ten equal proposal inputs through individual and batch submission."""
    source = ROOT / "src"
    package = work / "submit-base.topo"
    invoke(
        fixture, ("context", "storage-migrate", "--output", str(package)), None, source
    )
    invoke(package, ("context", "verify"), None, source)
    invoke(package, ("context", "status"), None, source)
    journal = json.loads((fixture / "history" / "journal.json").read_bytes())
    first = journal["entries"][0]
    generation = (fixture / "CURRENT").read_text().strip()
    context_id = json.loads(
        (fixture / "generations" / generation / "manifest.json").read_bytes()
    )["context_id"]
    evidence_id = json.loads(
        (
            fixture / "generations" / first["generation_after"] / "evidence.json"
        ).read_bytes()
    )["records"][0]["id"]
    proposal = {
        "proposal_type": "assertion",
        "producer": {
            "producer_type": "agent",
            "producer_id": "agent.synthetic",
            "producer_version": "0.1",
        },
        "proposed_assertion": {
            "subject_ref": {"ref_type": "entity", "id": first["result"]["person_id"]},
            "predicate": "domain.cashflow/monthly_salary",
            "object_value": {
                "value_type": "money",
                "value": {"amount": "1000.00", "currency": "EUR"},
            },
            "valid_time": {"start": "2026-01-01", "end_exclusive": None},
            "knowledge_type": "inferred",
            "module_data": {},
        },
        "evidence_refs": [{"ref_type": "evidence", "id": evidence_id}],
        "reason_ref": "synthetic:submit-round",
    }
    metadata = {
        "contract_version": "topo.cli/0.1",
        "context_id": context_id,
        "expected_generation": generation,
        "actor": {"actor_type": "agent", "actor_id": "agent.synthetic"},
        "reason": "Synthetic submit round",
    }
    individual, bulk = work / "individual.topo", work / "bulk.topo"
    shutil.copytree(package, individual)
    shutil.copytree(package, bulk)
    times = []
    for index in range(10):
        request = {
            **metadata,
            "operation_id": _operation_id(950000 + index),
            "proposal": proposal,
        }
        result, seconds, _ = invoke(individual, ("proposal", "submit"), request, source)
        metadata["expected_generation"] = result["generation_after"]
        times.append(seconds)
    request = {
        **metadata,
        "expected_generation": generation,
        "operation_id": _operation_id(960000),
        "proposals": [proposal] * 10,
        "authorization": None,
    }
    preview, preview_seconds, _ = invoke(
        bulk, ("proposal", "submit-batch"), request, source
    )
    request["authorization"] = {
        "preview_ref": preview["result"]["preview_ref"],
        "authorized_by": {"actor_type": "human", "actor_id": "benchmark"},
        "authorized_at": "2026-10-04T12:00:00Z",
    }
    result, bulk_seconds, _ = invoke(
        bulk, ("proposal", "submit-batch"), request, source
    )
    assert len(result["result"]["items"]) == 10
    return {
        "individual_mutation_seconds": times,
        "individual_round_seconds": sum(times),
        "bulk_mutation_seconds": bulk_seconds,
        "bulk_preview_seconds": preview_seconds,
        "bulk_round_seconds": bulk_seconds + preview_seconds,
        "individual_generations_added": 10,
        "bulk_generations_added": 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package", type=Path, help="reuse a synthetic full-format fixture"
    )
    parser.add_argument("--records", type=int, default=7500)
    parser.add_argument("--generations", type=int, default=21)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--submit-round",
        action="store_true",
        help="compare ten proposals with one authorized batch",
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="elapsed times only; use for an isolated repeat",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="topo-mutation-benchmark-") as directory:
        work = Path(directory)
        fixture = args.package or work / "fixture.topo"
        if args.package is None:
            _build_fixture(fixture, args.records, args.generations)
        first = json.loads((fixture / "history" / "journal.json").read_bytes())[
            "entries"
        ][0]
        current = (fixture / "CURRENT").read_text().strip()
        manifest = json.loads(
            (fixture / "generations" / current / "manifest.json").read_bytes()
        )
        identity = {"context_id": manifest["context_id"], "generation_id": current}
        reference = work / "reference-src"
        shutil.copytree(ROOT / "src", reference)
        validation = reference / "topo" / "canonical_validation.py"
        validation.write_text(
            validation.read_text().replace(
                "incremental: bool = True", "incremental: bool = False"
            )
        )
        engine = reference / "topo" / "engine.py"
        engine_source = engine.read_text()
        needle = "reuse_collections = operation not in"
        if needle not in engine_source:
            raise RuntimeError("reference serializer switch no longer matches engine")
        engine.write_text(
            engine_source.replace(
                needle, "reuse_collections = False and operation not in"
            )
        )
        decoder = reference / "topo" / "delta_storage.py"
        decoder.write_text(
            decoder.read_text().replace(
                "cached_fragments=(None if checkpoint else self.fragments)",
                "cached_fragments=None",
            )
        )
        storage = reference / "topo" / "storage.py"
        storage.write_text(
            storage.read_text().replace(
                "changes=publication.collection_changes", "changes=None"
            )
        )
        storage.write_text(
            storage.read_text()
            + "\n"
            + inspect.getsource(_reference_canonical_digest)
            + "\nFileSystemStorageAdapter._canonical_digest_locked = lambda self: _reference_canonical_digest(self._package)\n"
        )
        results: dict[str, Any] = {
            "records": args.records,
            "generations": args.generations,
            "python": sys.version,
            "platform": platform.platform(),
            "reference_limitation": __doc__,
        }
        for label, source in (("reference", reference), ("optimized", ROOT / "src")):
            package = work / f"{label}.topo"
            invoke(
                fixture,
                ("context", "storage-migrate", "--output", str(package)),
                None,
                source,
            )
            _, verify_seconds, _ = invoke(package, ("context", "verify"), None, source)
            verify_profile = None
            if not args.no_profile:
                _, _, verify_profile = invoke(
                    package, ("context", "verify"), None, source, profile=True
                )
            status = invoke(package, ("context", "status"), None, source)[1]
            scope = {
                "scope_type": "household",
                "entity_id": first["result"]["household_id"],
            }
            base = {
                "contract_version": "topo.cli/0.1",
                "context_id": identity["context_id"],
                "analysis_id": "analysis.net_worth",
                "analysis_scope": scope,
                "as_of_date": "2026-10-04",
            }
            reads = {
                "context.status": status,
                "workflow.next": invoke(package, ("workflow", "next"), base, source)[1],
                "analyze.run": invoke(
                    package,
                    ("analyze", "run"),
                    {
                        **base,
                        "analysis_contract_version": "0.1",
                        "period": None,
                        "reporting_currency": None,
                        "scenario": None,
                    },
                    source,
                )[1],
            }
            size = _package_bytes(package) / 1024**2
            canonical_size = (
                sum(
                    path.stat().st_size
                    for path in package.rglob("*")
                    if path.is_file()
                    and "derived" not in path.relative_to(package).parts
                )
                / 1024**2
            )
            round_identity = dict(identity)
            timings, previews = [], []
            for index in range(10):
                request = mutation(round_identity, index, args.records + index)
                previews.append(authorize(package, request, source))
                result, seconds, _ = invoke(
                    package, ("source", "import"), request, source
                )
                timings.append(seconds)
                round_identity["generation_id"] = result["generation_after"]
            mutation_profile = None
            if not args.no_profile:
                request = mutation(round_identity, 10, args.records + 10)
                authorize(package, request, source)
                _, _, mutation_profile = invoke(
                    package, ("source", "import"), request, source, profile=True
                )
            results[label] = {
                "package_mib": size,
                "canonical_package_mib": canonical_size,
                "verify_seconds": verify_seconds,
                "verify_profile": verify_profile,
                "reads_seconds": reads,
                "mutation_seconds": timings,
                "ten_mutations_seconds": sum(timings),
                "preview_seconds": previews,
                "round_including_previews_seconds": sum(timings + previews),
                "mutation_profile": mutation_profile,
            }
            print(json.dumps({label: results[label]}, indent=2), flush=True)
        if getattr(args, "submit_round", False):
            results["submit_round"] = measure_submit_round(fixture, work)
        if args.output:
            args.output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
