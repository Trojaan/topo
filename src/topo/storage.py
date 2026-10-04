from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Protocol, cast, runtime_checkable

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from topo.delta_storage import (
    CHECKPOINT_INTERVAL,
    FORMAT_VERSION,
    DeltaReader,
    decode_generation,
    encode_generation,
    validate_physical_current,
)
from topo.errors import PackageIntegrityError, StaleGenerationError


@dataclass(frozen=True)
class StoredPackageSnapshot:
    current_generation: str
    generation_files: dict[str, bytes]
    journal: bytes
    evidence_records: dict[str, bytes] = field(default_factory=dict)
    retained_generation_files: dict[str, dict[str, bytes]] | None = None
    parallel_retained_validation: bool = False


@dataclass(frozen=True)
class PackageCommit:
    generation_id: str
    generation_files: dict[str, bytes]
    journal: bytes
    evidence_records: dict[str, bytes] = field(default_factory=dict)
    evidence_inventory: bytes = b'{"paths":[]}\n'
    collection_changes: dict[str, object] | None = None


class StorageAdapter(Protocol):
    def load(self) -> StoredPackageSnapshot | None: ...

    def commit(
        self, publication: PackageCommit, *, expected_generation: str | None
    ) -> None: ...


@runtime_checkable
class CurrentStorage(Protocol):
    def load_current(self) -> StoredPackageSnapshot | None: ...


@runtime_checkable
class ValidatedHistoryStorage(Protocol):
    def load_verified_current(self) -> StoredPackageSnapshot | None: ...

    def remember_validated_history(self, *, expected_generation: str) -> None: ...


@runtime_checkable
class ExplanationStorage(Protocol):
    def store_explanations(self, records: dict[str, bytes]) -> None: ...

    def load_explanation(self, ref: str) -> bytes | None: ...


@runtime_checkable
class RetentionStorage(Protocol):
    def apply_retention(self, *, expected_generation: str) -> None: ...


@runtime_checkable
class PrivacyStorage(Protocol):
    def apply_privacy_scrub(
        self,
        *,
        expected_generation: str,
        generation_files: dict[str, dict[str, bytes]],
        journal: bytes,
        evidence_records: dict[str, bytes],
        evidence_inventories: dict[str, bytes],
    ) -> None: ...


def _write_durable(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _explanation_filename(ref: str) -> str:
    return hashlib.sha256(ref.encode("utf-8")).hexdigest() + ".json"


def _sync_directory(path: Path) -> None:
    if sys.platform == "win32":
        return
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _json_object(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return cast(dict[str, Any], value)


def _validate_generation_payloads(
    generation_id: str, generation_files: dict[str, bytes]
) -> dict[str, Any]:
    manifest_payload = generation_files.get("manifest.json")
    if manifest_payload is None:
        raise ValueError("generation has no manifest")
    manifest = _json_object(manifest_payload)
    if manifest.get("generation_id") != generation_id:
        raise ValueError("generation directory does not match its manifest")
    checksums = manifest.get("files")
    if not isinstance(checksums, dict):
        raise TypeError("manifest has no checksum mapping")
    if set(generation_files) != {"manifest.json", *checksums}:
        raise ValueError("generation has missing or unexpected files")
    for filename, expected in checksums.items():
        if not isinstance(filename, str) or not isinstance(expected, str):
            raise TypeError("manifest checksum mapping is invalid")
        actual = "sha256:" + hashlib.sha256(generation_files[filename]).hexdigest()
        if actual != expected:
            raise ValueError(f"checksum mismatch for {filename}")
    return manifest


def _read_generation(generation: Path) -> dict[str, bytes]:
    if generation.is_symlink() or not generation.is_dir():
        raise ValueError("generation must be a real directory")
    generation_files: dict[str, bytes] = {}
    for path in generation.iterdir():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"generation contains a non-file entry: {path.name}")
        generation_files[path.name] = path.read_bytes()
    return generation_files


def _physical_generation_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for filename, payload in sorted(files.items()):
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def _evidence_record_path(record_path: str) -> Path:
    path = Path(record_path)
    if (
        len(path.parts) != 3
        or path.parts[:2] != ("evidence", "records")
        or path.suffix != ".json"
        or path.name in {".", ".."}
    ):
        raise ValueError("invalid evidence record path")
    return path


def _read_evidence_records(
    package: Path, record_paths: set[str] | None = None
) -> dict[str, bytes]:
    records = package / "evidence" / "records"
    if records.is_symlink() or not records.is_dir():
        raise ValueError("evidence records must be a real directory")
    result: dict[str, bytes] = {}
    selected: list[tuple[str, str]] = []
    with os.scandir(records) as entries:
        for entry in entries:
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                raise ValueError("evidence records contain a non-file entry")
            record_path = f"evidence/records/{entry.name}"
            _evidence_record_path(record_path)
            if record_paths is None or record_path in record_paths:
                selected.append((record_path, entry.path))
    if record_paths is not None and {path for path, _ in selected} != record_paths:
        raise ValueError("evidence record does not exist")

    def read_record(item: tuple[str, str]) -> tuple[str, bytes]:
        record_path, path = item
        with open(path, "rb") as stream:
            return record_path, stream.read()

    loaded: Iterable[tuple[str, bytes]]
    if len(selected) < 64:
        loaded = map(read_record, selected)
    else:
        chunks = tuple(tuple(selected[offset::8]) for offset in range(8))

        def read_chunk(
            chunk: tuple[tuple[str, str], ...],
        ) -> tuple[tuple[str, bytes], ...]:
            return tuple(read_record(item) for item in chunk)

        with ThreadPoolExecutor(max_workers=8) as executor:
            loaded = tuple(
                record for chunk in executor.map(read_chunk, chunks) for record in chunk
            )
    for record_path, payload in loaded:
        result[record_path] = payload
    return result


def _referenced_evidence_record_paths(
    package: Path, published_generation_ids: set[str]
) -> set[str]:
    referenced: set[str] = set()
    inventory_directory = package / "history" / "evidence-inventory"
    if inventory_directory.is_symlink() or not inventory_directory.is_dir():
        raise ValueError("evidence inventory must be a real directory")
    for generation_id in published_generation_ids:
        matches = tuple(
            path
            for path in inventory_directory.iterdir()
            if path.name.startswith(generation_id + "-") and path.name.endswith(".json")
        )
        if len(matches) != 1 or matches[0].is_symlink() or not matches[0].is_file():
            raise ValueError("published generation has no unique evidence inventory")
        inventory_path = matches[0]
        inventory_payload = inventory_path.read_bytes()
        checksum = hashlib.sha256(inventory_payload).hexdigest()
        if inventory_path.name != f"{generation_id}-{checksum}.json":
            raise ValueError("evidence inventory checksum mismatch")
        referenced.update(_validate_evidence_inventory(inventory_payload))
    return referenced


def _validate_evidence_inventory(payload: bytes) -> tuple[str, ...]:
    inventory = _json_object(payload)
    if set(inventory) != {"paths"}:
        raise ValueError("evidence inventory shape is invalid")
    paths = inventory["paths"]
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise TypeError("evidence inventory paths are invalid")
    typed_paths = cast(list[str], paths)
    if typed_paths != sorted(set(typed_paths)):
        raise ValueError("evidence inventory paths must be unique and sorted")
    for record_path in typed_paths:
        _evidence_record_path(record_path)
    return tuple(typed_paths)


def _declared_removed_generations(entries: list[Any]) -> set[str] | None:
    removed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        if entry.get("operation") != "context.compact":
            continue
        result = entry.get("result")
        if not isinstance(result, dict):
            return None
        values = result.get("removed_generations")
        if not isinstance(values, list) or any(
            not isinstance(value, str) for value in values
        ):
            return None
        removed.update(cast(list[str], values))
    return removed


def _evidence_inventory_filename(generation_id: str, payload: bytes) -> str:
    checksum = hashlib.sha256(payload).hexdigest()
    return f"{generation_id}-{checksum}.json"


def _bootstrap_legacy_evidence_inventory(
    package: Path, published_generation_ids: set[str]
) -> bool:
    inventory_directory = package / "history" / "evidence-inventory"
    if inventory_directory.exists() or inventory_directory.is_symlink():
        return inventory_directory.is_dir() and not inventory_directory.is_symlink()
    evidence_records = package / "evidence" / "records"
    if evidence_records.is_symlink() or not evidence_records.is_dir():
        return False
    if any(evidence_records.iterdir()):
        return False
    empty_inventory = b'{"paths":[]}\n'
    temporary = Path(
        tempfile.mkdtemp(
            prefix=".evidence-inventory-", dir=str(inventory_directory.parent)
        )
    )
    os.chmod(temporary, 0o700)
    try:
        for generation_id in published_generation_ids:
            _write_durable(
                temporary
                / _evidence_inventory_filename(generation_id, empty_inventory),
                empty_inventory,
            )
        _sync_directory(temporary)
        os.replace(temporary, inventory_directory)
        _sync_directory(inventory_directory.parent)
        return True
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _remove_artifact(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        raise OSError(f"unsupported filesystem entry: {path}")


if sys.platform == "win32":

    def _lock_file(stream: BinaryIO) -> None:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        while True:
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.05)

    def _unlock_file(stream: BinaryIO) -> None:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

else:

    def _lock_file(stream: BinaryIO) -> None:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)

    def _unlock_file(stream: BinaryIO) -> None:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def _exclusive_file_lock(lock_path: Path) -> Iterator[None]:
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(str(lock_path), flags, 0o600)
    with os.fdopen(descriptor, "a+b") as stream:
        if hasattr(os, "fchmod"):
            os.fchmod(stream.fileno(), 0o600)
        _lock_file(stream)
        try:
            yield
        finally:
            _unlock_file(stream)


class FileSystemStorageAdapter:
    """Read and atomically publish opaque package bytes on the local filesystem."""

    def __init__(self, package: Path) -> None:
        self._package = package
        self._decoded_history: dict[str, dict[str, bytes]] | None = None

    def _delta_format(self) -> bool:
        marker = self._package / "storage-format.json"
        if not marker.exists() and not marker.is_symlink():
            return False
        if marker.is_symlink() or not marker.is_file():
            raise PackageIntegrityError("storage format marker is invalid")
        if _json_object(marker.read_bytes()) != {"schema_version": FORMAT_VERSION}:
            raise PackageIntegrityError("unsupported storage format")
        return True

    def _canonical_digest_locked(self) -> str:
        digest = hashlib.sha256()
        # DirEntry retains the directory-entry type, avoiding several redundant
        # metadata syscalls for each tiny evidence file. Every file's bytes are
        # still opened and hashed on every check; no mtime/size shortcut is used.
        paths: list[tuple[str, str, bytes]] = []

        def add_entry(entry: os.DirEntry[str], relative: str) -> None:
            if entry.is_symlink():
                raise PackageIntegrityError(
                    "canonical package contains a symbolic link"
                )
            if entry.is_dir(follow_symlinks=False):
                paths.append((relative, entry.path, b"D"))
                walk(entry.path, relative)
            elif entry.is_file(follow_symlinks=False):
                paths.append((relative, entry.path, b"F"))
            else:
                raise PackageIntegrityError(
                    "canonical package contains an invalid file"
                )

        def walk(directory: str, relative: str) -> None:
            with os.scandir(directory) as entries:
                for entry in entries:
                    add_entry(entry, f"{relative}/{entry.name}")

        for name in ("CURRENT", "storage-format.json"):
            path = self._package / name
            if path.is_symlink() or not path.is_file():
                raise PackageIntegrityError(
                    "canonical package contains an invalid file"
                )
            paths.append((name, str(path), b"F"))
        for relative in ("generations", "history", "evidence/records"):
            root = self._package / relative
            if root.is_symlink() or not root.is_dir():
                raise PackageIntegrityError(
                    "canonical package contains an invalid directory"
                )
            walk(str(root), relative)
        for relative, file_path, kind in sorted(paths):
            digest.update(kind)
            digest.update(relative.encode())
            digest.update(b"\0")
            if kind == b"F":
                with open(file_path, "rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
            digest.update(b"\0")
        return digest.hexdigest()

    def _receipt_matches_locked(self, generation_id: str) -> bool:
        receipt_path = self._package / "derived" / "validated-history.json"
        if receipt_path.is_symlink() or not receipt_path.is_file():
            return False
        try:
            return _json_object(receipt_path.read_bytes()) == {
                "generation_id": generation_id,
                "canonical_digest": self._canonical_digest_locked(),
            }
        except (OSError, TypeError, ValueError):
            return False

    def load_verified_current(self) -> StoredPackageSnapshot | None:
        if not self._package.exists() or not self._delta_format():
            return None
        with _exclusive_file_lock(self._package / "LOCK"):
            if self._has_recovery_artifacts():
                return None
            generation_id, _generations, history = self._current_paths_locked()
            if not self._receipt_matches_locked(generation_id):
                return None
            referenced = _referenced_evidence_record_paths(
                self._package, {generation_id}
            )
            return StoredPackageSnapshot(
                current_generation=generation_id,
                generation_files=self._current_logical_locked(generation_id),
                journal=(history / "journal.json").read_bytes(),
                evidence_records=_read_evidence_records(self._package, referenced),
            )

    def remember_validated_history(self, *, expected_generation: str) -> None:
        if not self._delta_format():
            return
        with _exclusive_file_lock(self._package / "LOCK"):
            current, _generations, _history = self._current_paths_locked()
            if current != expected_generation:
                raise StaleGenerationError(current)
            derived = self._package / "derived"
            derived.mkdir(mode=0o700, exist_ok=True)
            if derived.is_symlink():
                raise PackageIntegrityError("derived directory is a symbolic link")
            receipt = (
                json.dumps(
                    {
                        "generation_id": current,
                        "canonical_digest": self._canonical_digest_locked(),
                    },
                    sort_keys=True,
                )
                + "\n"
            ).encode()
            temporary = derived / ".validated-history.tmp"
            if temporary.exists() or temporary.is_symlink():
                _remove_artifact(temporary)
            _write_durable(temporary, receipt)
            os.replace(temporary, derived / "validated-history.json")
            _sync_directory(derived)

    def _logical_generations_locked(self) -> dict[str, dict[str, bytes]]:
        journal = _json_object(
            (self._package / "history" / "journal.json").read_bytes()
        )
        entries = journal.get("entries")
        if not isinstance(entries, list):
            raise PackageIntegrityError("invalid generation journal")
        generations = self._package / "generations"
        logical: dict[str, dict[str, bytes]] = {}
        reader = DeltaReader()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(
                entry.get("generation_after"), str
            ):
                raise PackageIntegrityError("invalid generation journal")
            generation_id = cast(str, entry["generation_after"])
            path = generations / generation_id
            if not path.exists():
                reader.reset()
                continue
            try:
                state = reader.read(generation_id, _read_generation(path))
            except (KeyError, TypeError, ValueError) as error:
                raise PackageIntegrityError(str(error)) from error
            logical[generation_id] = state
        return logical

    def _current_logical_locked(self, generation_id: str) -> dict[str, bytes]:
        cache = self._package / "derived" / "current" / generation_id
        physical = _read_generation(self._package / "generations" / generation_id)
        try:
            validate_physical_current(physical)
        except (KeyError, TypeError, ValueError) as error:
            raise PackageIntegrityError(str(error)) from error
        if cache.is_dir() and not cache.is_symlink():
            try:
                files = _read_generation(cache)
                marker = _json_object(files.pop("storage-cache.json"))
                if (
                    marker == {"physical_digest": _physical_generation_digest(physical)}
                    and files.get("manifest.json") == physical["manifest.json"]
                ):
                    _validate_generation_payloads(generation_id, files)
                    return files
            except (OSError, ValueError, TypeError):
                pass
        logical = self._logical_generations_locked()
        if generation_id not in logical:
            raise PackageIntegrityError("CURRENT has no generation")
        files = logical[generation_id]
        try:
            self._store_current_cache_locked(generation_id, files)
        except (OSError, PackageIntegrityError):
            pass
        return files

    def _store_current_cache_locked(
        self, generation_id: str, files: dict[str, bytes]
    ) -> None:
        root = self._package / "derived" / "current"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.is_symlink():
            raise PackageIntegrityError("current cache path is a symbolic link")
        destination = root / generation_id
        if destination.exists() or destination.is_symlink():
            _remove_artifact(destination)
        temporary = Path(tempfile.mkdtemp(prefix=".current-", dir=str(root)))
        os.chmod(temporary, 0o700)
        try:
            for filename, payload in files.items():
                _write_durable(temporary / filename, payload)
            physical = _read_generation(self._package / "generations" / generation_id)
            _write_durable(
                temporary / "storage-cache.json",
                (
                    json.dumps(
                        {"physical_digest": _physical_generation_digest(physical)}
                    )
                    + "\n"
                ).encode(),
            )
            _sync_directory(temporary)
            os.replace(temporary, destination)
            _sync_directory(root)
            for old in root.iterdir():
                if old != destination:
                    _remove_artifact(old)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def load(self) -> StoredPackageSnapshot | None:
        if not self._package.exists():
            return None
        if self._package.is_symlink():
            raise OSError("context package cannot be a symbolic link")

        with _exclusive_file_lock(self._package / "LOCK"):
            return self._load_full_locked()

    def load_current(self) -> StoredPackageSnapshot | None:
        if not self._package.exists():
            return None
        if self._package.is_symlink():
            raise OSError("context package cannot be a symbolic link")

        with _exclusive_file_lock(self._package / "LOCK"):
            if self._has_recovery_artifacts():
                return self._load_full_locked()
            generation_id, generations, history = self._current_paths_locked()
            journal_path = history / "journal.json"
            current_path = self._package / "CURRENT"
            if current_path.is_symlink() or journal_path.is_symlink():
                raise OSError("canonical package files cannot be symbolic links")
            referenced_evidence = _referenced_evidence_record_paths(
                self._package, {generation_id}
            )
            return StoredPackageSnapshot(
                current_generation=generation_id,
                generation_files=(
                    self._current_logical_locked(generation_id)
                    if self._delta_format()
                    else _read_generation(generations / generation_id)
                ),
                journal=journal_path.read_bytes(),
                evidence_records=_read_evidence_records(
                    self._package, referenced_evidence
                ),
                retained_generation_files=None,
            )

    def _load_full_locked(self) -> StoredPackageSnapshot:
        recovered = self._recover_and_validate_history()
        if self._delta_format() and not recovered:
            raise PackageIntegrityError("package history cannot be proven safe")
        generation_id, generations, history = self._current_paths_locked()
        if self._delta_format():
            all_files = dict(
                self._decoded_history
                if self._decoded_history is not None
                else self._logical_generations_locked()
            )
            self._decoded_history = None
            generation_files = all_files.pop(generation_id)
            retained_generation_files = all_files
        else:
            generation_files = _read_generation(generations / generation_id)
            retained_generation_files = {
                path.name: _read_generation(path)
                for path in generations.iterdir()
                if path.name != generation_id
            }
        return StoredPackageSnapshot(
            current_generation=generation_id,
            generation_files=generation_files,
            journal=(history / "journal.json").read_bytes(),
            evidence_records=_read_evidence_records(self._package),
            retained_generation_files=retained_generation_files,
            parallel_retained_validation=self._delta_format(),
        )

    def _current_paths_locked(self) -> tuple[str, Path, Path]:
        current_path = self._package / "CURRENT"
        generations = self._package / "generations"
        history = self._package / "history"
        if (
            current_path.is_symlink()
            or generations.is_symlink()
            or history.is_symlink()
        ):
            raise OSError("canonical package paths cannot be symbolic links")
        generation_id = current_path.read_text(encoding="utf-8").strip()
        generation_component = Path(generation_id)
        if len(generation_component.parts) != 1 or generation_component.name in {
            "",
            ".",
            "..",
        }:
            raise OSError("CURRENT contains an invalid generation id")
        return generation_id, generations, history

    def _has_recovery_artifacts(self) -> bool:
        staging = self._package / "staging"
        history = self._package / "history"
        if staging.is_symlink() or history.is_symlink():
            return True
        if any(staging.iterdir()):
            return True
        temporary_paths = (
            self._package / ".CURRENT.tmp",
            history / ".journal.tmp",
        )
        if any(path.exists() or path.is_symlink() for path in temporary_paths):
            return True
        return any(
            path.name.startswith(".evidence-inventory-") for path in history.iterdir()
        )

    def store_explanations(self, records: dict[str, bytes]) -> None:
        if not records:
            return
        with _exclusive_file_lock(self._package / "LOCK"):
            directory = self._package / "derived" / "explanations"
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.is_dir():
                raise OSError("explanation index must be a real directory")
            for ref, payload in sorted(records.items()):
                destination = directory / _explanation_filename(ref)
                if destination.exists():
                    if destination.is_symlink() or destination.read_bytes() != payload:
                        raise OSError(
                            "stored explanation does not match its stable ref"
                        )
                    continue
                _write_durable(destination, payload)
            _sync_directory(directory)

    def load_explanation(self, ref: str) -> bytes | None:
        with _exclusive_file_lock(self._package / "LOCK"):
            path = (
                self._package / "derived" / "explanations" / _explanation_filename(ref)
            )
            if not path.exists():
                return None
            if path.is_symlink() or not path.is_file():
                raise OSError("explanation record must be a real file")
            return path.read_bytes()

    def apply_retention(self, *, expected_generation: str) -> None:
        with _exclusive_file_lock(self._package / "LOCK"):
            current = (self._package / "CURRENT").read_text(encoding="utf-8").strip()
            if current != expected_generation:
                raise StaleGenerationError(current)
            if not self._recover_and_validate_history():
                raise PackageIntegrityError(
                    "package history cannot be proven safe for retention"
                )

    def apply_privacy_scrub(
        self,
        *,
        expected_generation: str,
        generation_files: dict[str, dict[str, bytes]],
        journal: bytes,
        evidence_records: dict[str, bytes],
        evidence_inventories: dict[str, bytes],
    ) -> None:
        with _exclusive_file_lock(self._package / "LOCK"):
            current = (self._package / "CURRENT").read_text(encoding="utf-8").strip()
            if current != expected_generation:
                raise StaleGenerationError(current)
            if not self._recover_and_validate_history():
                raise PackageIntegrityError(
                    "package history cannot be proven safe for privacy scrub"
                )
            generations = self._package / "generations"
            existing = {path.name for path in generations.iterdir()}
            if set(generation_files) != existing:
                raise PackageIntegrityError(
                    "privacy scrub must rewrite every retained generation"
                )
            if set(evidence_inventories) != existing:
                raise PackageIntegrityError(
                    "privacy scrub must rewrite every evidence inventory"
                )
            try:
                for generation_id, files in generation_files.items():
                    _validate_generation_payloads(generation_id, files)
                self._validate_journal_tip(journal, expected_generation)
                inventory_paths = {
                    path
                    for payload in evidence_inventories.values()
                    for path in _validate_evidence_inventory(payload)
                }
                if inventory_paths != set(evidence_records):
                    raise ValueError(
                        "privacy scrub evidence inventories do not match records"
                    )
            except (
                json.JSONDecodeError,
                UnicodeDecodeError,
                TypeError,
                ValueError,
            ) as error:
                raise PackageIntegrityError(str(error)) from error

            physical_generation_files = generation_files
            if self._delta_format():
                entries = _json_object(journal)["entries"]
                physical_generation_files = {}
                previous: dict[str, bytes] | None = None
                count = 0
                for entry in entries:
                    generation_id = entry["generation_after"]
                    logical_files = generation_files.get(generation_id)
                    if logical_files is None:
                        previous = None
                        continue
                    physical_generation_files[generation_id] = encode_generation(
                        logical_files,
                        previous,
                        checkpoint=previous is None or count % CHECKPOINT_INTERVAL == 0,
                    )
                    previous = logical_files
                    count += 1

            staging = self._package / "staging"
            temporary = Path(
                tempfile.mkdtemp(prefix="privacy-scrub-", dir=str(staging))
            )
            os.chmod(temporary, 0o700)
            try:
                staged_generations = temporary / "generations"
                staged_generations.mkdir(mode=0o700)
                for generation_id, files in physical_generation_files.items():
                    destination = staged_generations / generation_id
                    destination.mkdir(mode=0o700)
                    for filename, payload in files.items():
                        _write_durable(destination / filename, payload)
                    _sync_directory(destination)
                staged_inventory = temporary / "evidence-inventory"
                staged_inventory.mkdir(mode=0o700)
                for generation_id, payload in evidence_inventories.items():
                    _write_durable(
                        staged_inventory
                        / _evidence_inventory_filename(generation_id, payload),
                        payload,
                    )
                staged_records = temporary / "records"
                staged_records.mkdir(mode=0o700)
                for record_path, payload in evidence_records.items():
                    relative = _evidence_record_path(record_path)
                    _write_durable(staged_records / relative.name, payload)
                staged_journal = temporary / "journal.json"
                _write_durable(staged_journal, journal)

                for generation_id in sorted(generation_files):
                    destination = generations / generation_id
                    backup = temporary / f"old-generation-{generation_id}"
                    os.replace(destination, backup)
                    os.replace(staged_generations / generation_id, destination)
                    shutil.rmtree(backup)
                _sync_directory(generations)

                inventory_directory = self._package / "history" / "evidence-inventory"
                old_inventory = temporary / "old-evidence-inventory"
                os.replace(inventory_directory, old_inventory)
                os.replace(staged_inventory, inventory_directory)
                shutil.rmtree(old_inventory)

                records_directory = self._package / "evidence" / "records"
                old_records = temporary / "old-records"
                os.replace(records_directory, old_records)
                os.replace(staged_records, records_directory)
                shutil.rmtree(old_records)

                os.replace(staged_journal, self._package / "history" / "journal.json")
                derived = self._package / "derived"
                if derived.exists() or derived.is_symlink():
                    _remove_artifact(derived)
                _sync_directory(self._package / "history")
                _sync_directory(self._package / "evidence")
                _sync_directory(self._package)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
                _sync_directory(staging)

    def commit(
        self, publication: PackageCommit, *, expected_generation: str | None
    ) -> None:
        try:
            _validate_generation_payloads(
                publication.generation_id, publication.generation_files
            )
            self._validate_journal_tip(publication.journal, publication.generation_id)
            _validate_evidence_inventory(publication.evidence_inventory)
            for record_path in publication.evidence_records:
                _evidence_record_path(record_path)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            TypeError,
            ValueError,
        ) as error:
            raise PackageIntegrityError(str(error)) from error
        if expected_generation is None:
            initialization_lock = self._package.parent / f".{self._package.name}.lock"
            with _exclusive_file_lock(initialization_lock):
                if self._package.exists():
                    raise FileExistsError(str(self._package))
                self._publish_initial(publication)
            return
        with _exclusive_file_lock(self._package / "LOCK"):
            valid_receipt = (
                self._delta_format()
                and not self._has_recovery_artifacts()
                and self._receipt_matches_locked(expected_generation)
            )
            if not valid_receipt and not self._recover_and_validate_history():
                raise PackageIntegrityError(
                    "package history cannot be proven safe for publication"
                )
            if self._delta_format():
                previous = self._current_logical_locked(expected_generation)
                entries = _json_object(publication.journal)["entries"]
                checkpoint = len(entries) % CHECKPOINT_INTERVAL == 1 or (
                    isinstance(entries[-1], dict)
                    and entries[-1].get("operation") == "context.compact"
                )
                physical = encode_generation(
                    publication.generation_files,
                    previous,
                    checkpoint=checkpoint,
                    changes=publication.collection_changes,
                )
                if publication.collection_changes is not None:
                    reconstructed = decode_generation(
                        publication.generation_id, physical, previous
                    )
                    if reconstructed != publication.generation_files:
                        raise PackageIntegrityError(
                            "engine change set does not match validated state"
                        )
                self._publish_update(
                    PackageCommit(
                        generation_id=publication.generation_id,
                        generation_files=physical,
                        journal=publication.journal,
                        evidence_records=publication.evidence_records,
                        evidence_inventory=publication.evidence_inventory,
                    ),
                    expected_generation,
                    logical_files=publication.generation_files,
                )
                try:
                    self._store_current_cache_locked(
                        publication.generation_id, publication.generation_files
                    )
                except (OSError, PackageIntegrityError):
                    pass
            else:
                self._publish_update(publication, expected_generation)

    @staticmethod
    def _validate_journal_tip(journal: bytes, generation_id: str) -> None:
        value = _json_object(journal)
        entries = value.get("entries")
        if not isinstance(entries, list) or not entries:
            raise ValueError("journal has no entries")
        last = entries[-1]
        if not isinstance(last, dict) or last.get("generation_after") != generation_id:
            raise ValueError("journal does not end at the published generation")

    def _published_generation_ids(self, journal_path: Path) -> set[str] | None:
        try:
            self._decoded_history = None
            current_path = self._package / "CURRENT"
            if current_path.is_symlink() or journal_path.is_symlink():
                return None
            current = current_path.read_text(encoding="utf-8").strip()
            journal = _json_object(journal_path.read_bytes())
            entries = journal.get("entries")
            if not isinstance(entries, list) or not entries:
                return None

            removed = _declared_removed_generations(entries)
            if removed is None:
                return None

            published: set[str] = set()
            seen: set[str] = set()
            previous: str | None = None
            reader = DeltaReader()
            delta_format = self._delta_format()
            decoded: dict[str, dict[str, bytes]] = {}
            for entry_value in entries:
                if not isinstance(entry_value, dict):
                    return None
                generation_id = entry_value.get("generation_after")
                if not isinstance(generation_id, str) or generation_id in seen:
                    return None
                if entry_value.get("generation_before") != previous:
                    return None
                generation_path = self._package / "generations" / generation_id
                seen.add(generation_id)
                if generation_id in removed:
                    if generation_id == current:
                        return None
                    if delta_format and generation_path.exists():
                        reader.read(generation_id, _read_generation(generation_path))
                    else:
                        reader.reset()
                    previous = generation_id
                    continue
                generation_files = _read_generation(generation_path)
                if delta_format:
                    previous_files = reader.read(generation_id, generation_files)
                    manifest = _validate_generation_payloads(
                        generation_id, previous_files
                    )
                    decoded[generation_id] = previous_files
                else:
                    manifest = _validate_generation_payloads(
                        generation_id, generation_files
                    )
                if manifest.get("based_on") != previous:
                    return None
                if manifest.get("mutation_id") != entry_value.get("mutation_id"):
                    return None
                published.add(generation_id)
                previous = generation_id
            if previous != current:
                return None
            if not removed <= seen:
                return None
            if delta_format:
                self._decoded_history = decoded
            return published
        except (
            OSError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            TypeError,
            ValueError,
        ):
            return None

    def _recover_and_validate_history(self) -> bool:
        staging = self._package / "staging"
        generations = self._package / "generations"
        history = self._package / "history"
        if any(path.is_symlink() for path in (staging, generations, history)):
            return False
        for artifact in staging.iterdir():
            if artifact.name.startswith(".rebase-old-"):
                generation_id = artifact.name.removeprefix(".rebase-old-")
                original = generations / generation_id
                if not original.exists():
                    os.replace(artifact, original)
                    continue
            _remove_artifact(artifact)
        _sync_directory(staging)

        journal = history / "journal.json"
        journal_tmp = history / ".journal.tmp"
        for artifact in history.iterdir():
            if artifact.name.startswith(".evidence-inventory-"):
                _remove_artifact(artifact)
        _sync_directory(history)
        published = self._published_generation_ids(journal)
        if published is None and journal_tmp.is_file() and not journal_tmp.is_symlink():
            recovered = self._published_generation_ids(journal_tmp)
            if recovered is not None:
                os.replace(journal_tmp, journal)
                _sync_directory(journal.parent)
                published = recovered

        if published is None:
            return False

        if self._delta_format():
            try:
                entries = _json_object(journal.read_bytes())["entries"]
                removed = _declared_removed_generations(entries)
                if removed is None:
                    return False
                logical = self._decoded_history
                for index, entry in enumerate(entries):
                    generation_id = entry["generation_after"]
                    if generation_id in removed or index == 0:
                        continue
                    prior_id = entries[index - 1]["generation_after"]
                    if prior_id not in removed:
                        continue
                    current_path = generations / generation_id
                    if "storage.json" not in _read_generation(current_path):
                        continue
                    if logical is None:
                        logical = self._logical_generations_locked()
                    staged = staging / f".rebase-new-{generation_id}"
                    old = staging / f".rebase-old-{generation_id}"
                    staged.mkdir(mode=0o700)
                    for filename, payload in logical[generation_id].items():
                        _write_durable(staged / filename, payload)
                    _sync_directory(staged)
                    os.replace(current_path, old)
                    os.replace(staged, current_path)
                    _sync_directory(generations)
                    shutil.rmtree(old)
            except (KeyError, TypeError, ValueError, OSError, PackageIntegrityError):
                return False

        for artifact in generations.iterdir():
            if artifact.name not in published:
                _remove_artifact(artifact)
        _sync_directory(generations)

        try:
            inventory_directory = history / "evidence-inventory"
            if not _bootstrap_legacy_evidence_inventory(self._package, published):
                return False
            for artifact in inventory_directory.iterdir():
                if not any(
                    artifact.name.startswith(generation_id + "-")
                    for generation_id in published
                ):
                    _remove_artifact(artifact)
            _sync_directory(inventory_directory)
            referenced_evidence = _referenced_evidence_record_paths(
                self._package, published
            )
            evidence_records = self._package / "evidence" / "records"
            if evidence_records.is_symlink() or not evidence_records.is_dir():
                return False
            for artifact in evidence_records.iterdir():
                if artifact.is_symlink() or not artifact.is_file():
                    return False
                record_path = str(artifact.relative_to(self._package))
                _evidence_record_path(record_path)
                if record_path not in referenced_evidence:
                    artifact.unlink()
            _sync_directory(evidence_records)
        except (OSError, TypeError, ValueError):
            return False

        for temporary in (self._package / ".CURRENT.tmp", journal_tmp):
            if temporary.exists() or temporary.is_symlink():
                _remove_artifact(temporary)
        return True

    @staticmethod
    def _stage_generation(
        publication: PackageCommit,
        destination: Path,
        *,
        logical_files: dict[str, bytes] | None = None,
    ) -> None:
        destination.mkdir(mode=0o700)
        for filename, payload in publication.generation_files.items():
            _write_durable(destination / filename, payload)
        _sync_directory(destination)
        _validate_generation_payloads(
            publication.generation_id,
            logical_files or _read_generation(destination),
        )

    def _publish_update(
        self,
        publication: PackageCommit,
        expected_generation: str,
        *,
        logical_files: dict[str, bytes] | None = None,
    ) -> None:
        current = (self._package / "CURRENT").read_text(encoding="utf-8").strip()
        if current != expected_generation:
            raise StaleGenerationError(current)

        staging = self._package / "staging"
        generations = self._package / "generations"
        staged_generation = staging / publication.generation_id
        staged_evidence = staging / f"{publication.generation_id}.evidence"
        staged_inventory = staging / f"{publication.generation_id}.evidence-inventory"
        inventory_directory = self._package / "history" / "evidence-inventory"
        published_inventory = inventory_directory / _evidence_inventory_filename(
            publication.generation_id, publication.evidence_inventory
        )
        published_evidence: list[Path] = []
        current_switched = False
        try:
            _write_durable(staged_inventory, publication.evidence_inventory)
            if publication.evidence_records:
                staged_evidence.mkdir(mode=0o700)
                for record_path, payload in publication.evidence_records.items():
                    relative = _evidence_record_path(record_path)
                    _write_durable(staged_evidence / relative.name, payload)
                _sync_directory(staged_evidence)
            self._stage_generation(
                publication, staged_generation, logical_files=logical_files
            )
            os.replace(staged_generation, generations / publication.generation_id)
            _sync_directory(generations)
            os.replace(staged_inventory, published_inventory)
            _sync_directory(inventory_directory)

            for record_path in publication.evidence_records:
                relative = _evidence_record_path(record_path)
                destination = self._package / relative
                if destination.exists() or destination.is_symlink():
                    raise FileExistsError(str(destination))
                os.replace(staged_evidence / relative.name, destination)
                published_evidence.append(destination)
            if published_evidence:
                _sync_directory(self._package / "evidence" / "records")

            current = (self._package / "CURRENT").read_text(encoding="utf-8").strip()
            if current != expected_generation:
                raise StaleGenerationError(current)

            journal_tmp = self._package / "history" / ".journal.tmp"
            current_tmp = self._package / ".CURRENT.tmp"
            _write_durable(journal_tmp, publication.journal)
            _write_durable(
                current_tmp, (publication.generation_id + "\n").encode("ascii")
            )
            os.replace(current_tmp, self._package / "CURRENT")
            current_switched = True
            _sync_directory(self._package)
            os.replace(journal_tmp, self._package / "history" / "journal.json")
            _sync_directory(self._package / "history")
        finally:
            if staged_generation.exists():
                shutil.rmtree(staged_generation)
            if staged_evidence.exists():
                shutil.rmtree(staged_evidence)
            if staged_inventory.exists():
                staged_inventory.unlink()
            if not current_switched:
                for evidence_path in published_evidence:
                    if evidence_path.exists() and not evidence_path.is_symlink():
                        evidence_path.unlink()
                if published_evidence:
                    _sync_directory(self._package / "evidence" / "records")
                if (
                    published_inventory.exists()
                    and not published_inventory.is_symlink()
                ):
                    published_inventory.unlink()
                    _sync_directory(inventory_directory)

    def _publish_initial(self, publication: PackageCommit) -> None:
        parent = self._package.parent
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{self._package.name}.staging-", dir=str(parent))
        )
        os.chmod(temporary, 0o700)
        try:
            generations = temporary / "generations"
            staging = temporary / "staging"
            evidence_records = temporary / "evidence" / "records"
            history = temporary / "history"
            inventory_directory = history / "evidence-inventory"
            for directory in (
                generations,
                staging,
                evidence_records,
                history,
                inventory_directory,
            ):
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)

            _write_durable(temporary / "LOCK", b"")

            for record_path, payload in publication.evidence_records.items():
                _write_durable(temporary / _evidence_record_path(record_path), payload)
            if publication.evidence_records:
                _sync_directory(evidence_records)

            staged_generation = staging / publication.generation_id
            self._stage_generation(publication, staged_generation)

            os.replace(staged_generation, generations / publication.generation_id)
            _sync_directory(generations)
            _write_durable(
                inventory_directory
                / _evidence_inventory_filename(
                    publication.generation_id, publication.evidence_inventory
                ),
                publication.evidence_inventory,
            )
            _sync_directory(inventory_directory)
            _write_durable(history / "journal.json", publication.journal)
            _sync_directory(history)

            temporary_current = temporary / ".CURRENT.tmp"
            _write_durable(
                temporary_current,
                (publication.generation_id + "\n").encode("ascii"),
            )
            os.replace(temporary_current, temporary / "CURRENT")
            _sync_directory(temporary)

            if self._package.exists():
                raise FileExistsError(str(self._package))
            os.replace(temporary, self._package)
            _sync_directory(parent)
        except BaseException:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise


def migrate_storage(
    source: Path,
    destination: Path,
    *,
    validate: Callable[[StoredPackageSnapshot], object],
) -> tuple[str, int]:
    """Copy a verified legacy package to a new, atomically published delta package."""
    if source.is_symlink() or not source.is_dir():
        raise PackageIntegrityError("source package must be a real directory")
    if source.resolve() == destination.resolve():
        raise ValueError("storage migration requires a different output path")
    if destination.resolve().is_relative_to(source.resolve()):
        raise ValueError("storage migration output cannot be inside the source package")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(str(destination))
    if not destination.parent.is_dir():
        raise FileNotFoundError(str(destination.parent))
    source_adapter = FileSystemStorageAdapter(source)
    with _exclusive_file_lock(source / "LOCK"):
        if source_adapter._delta_format():
            raise ValueError("package already uses delta storage")
        snapshot = source_adapter._load_full_locked()
        validate(snapshot)
        all_files = {
            snapshot.current_generation: snapshot.generation_files,
            **(snapshot.retained_generation_files or {}),
        }
        temporary = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.staging-", dir=str(destination.parent)
            )
        )
        os.chmod(temporary, 0o700)
        try:
            for relative in (
                "generations",
                "staging",
                "history",
                "history/evidence-inventory",
                "evidence",
                "evidence/records",
            ):
                (temporary / relative).mkdir(mode=0o700)
            _write_durable(temporary / "LOCK", b"")
            _write_durable(
                temporary / "storage-format.json",
                (json.dumps({"schema_version": FORMAT_VERSION}) + "\n").encode(),
            )
            _write_durable(
                temporary / "CURRENT", (snapshot.current_generation + "\n").encode()
            )
            _write_durable(temporary / "history" / "journal.json", snapshot.journal)
            for record_path, payload in snapshot.evidence_records.items():
                _write_durable(temporary / _evidence_record_path(record_path), payload)
            source_inventories = source / "history" / "evidence-inventory"
            for path in source_inventories.iterdir():
                if not path.is_file() or path.is_symlink():
                    raise PackageIntegrityError("invalid evidence inventory")
                _write_durable(
                    temporary / "history" / "evidence-inventory" / path.name,
                    path.read_bytes(),
                )
            previous: dict[str, bytes] | None = None
            count = 0
            entries = _json_object(snapshot.journal)["entries"]
            for entry in entries:
                generation_id = entry["generation_after"]
                files = all_files.get(generation_id)
                if files is None:
                    previous = None
                    continue
                physical = encode_generation(
                    files,
                    previous,
                    checkpoint=previous is None or count % CHECKPOINT_INTERVAL == 0,
                )
                generation = temporary / "generations" / generation_id
                generation.mkdir(mode=0o700)
                for filename, payload in physical.items():
                    _write_durable(generation / filename, payload)
                _sync_directory(generation)
                previous = files
                count += 1
            for relative in (
                "generations",
                "history/evidence-inventory",
                "history",
                "evidence/records",
                "evidence",
                "staging",
            ):
                _sync_directory(temporary / relative)
            _sync_directory(temporary)
            migrated_adapter = FileSystemStorageAdapter(temporary)
            migrated = migrated_adapter.load()
            if migrated is None:
                raise PackageIntegrityError("migrated package is missing")
            validate(migrated)
            if migrated.generation_files != snapshot.generation_files:
                raise PackageIntegrityError("migration changed the current snapshot")
            try:
                migrated_adapter.remember_validated_history(
                    expected_generation=snapshot.current_generation
                )
            except (OSError, PackageIntegrityError):
                pass
            output_lock = destination.parent / f".{destination.name}.lock"
            with _exclusive_file_lock(output_lock):
                if destination.exists() or destination.is_symlink():
                    raise FileExistsError(str(destination))
                os.replace(temporary, destination)
                _sync_directory(destination.parent)
            return snapshot.current_generation, count
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
