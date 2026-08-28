from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from topo.errors import PackageIntegrityError, StaleGenerationError


@dataclass(frozen=True)
class StoredPackageSnapshot:
    current_generation: str
    generation_files: dict[str, bytes]
    journal: bytes
    retained_generation_files: dict[str, dict[str, bytes]] | None = None


@dataclass(frozen=True)
class PackageCommit:
    generation_id: str
    generation_files: dict[str, bytes]
    journal: bytes


class StorageAdapter(Protocol):
    def load(self) -> StoredPackageSnapshot | None: ...

    def commit(
        self, publication: PackageCommit, *, expected_generation: str | None
    ) -> None: ...


def _write_durable(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path: Path) -> None:
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


def _remove_artifact(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        raise OSError(f"unsupported filesystem entry: {path}")


@contextmanager
def _exclusive_file_lock(lock_path: Path) -> Iterator[None]:
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(str(lock_path), flags, 0o600)
    with os.fdopen(descriptor, "a+b") as stream:
        os.fchmod(stream.fileno(), 0o600)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class FileSystemStorageAdapter:
    """Read and atomically publish opaque package bytes on the local filesystem."""

    def __init__(self, package: Path) -> None:
        self._package = package

    def load(self) -> StoredPackageSnapshot | None:
        if not self._package.exists():
            return None
        if self._package.is_symlink():
            raise OSError("context package cannot be a symbolic link")

        with _exclusive_file_lock(self._package / "LOCK"):
            self._recover_and_validate_history()
            generation_id = (
                (self._package / "CURRENT").read_text(encoding="utf-8").strip()
            )
            generations = self._package / "generations"
            history = self._package / "history"
            if generations.is_symlink() or history.is_symlink():
                raise OSError("canonical package directories cannot be symbolic links")
            generation = generations / generation_id
            generation_files = _read_generation(generation)
            retained_generation_files = {
                path.name: _read_generation(path)
                for path in generations.iterdir()
                if path.name != generation_id
            }
            journal = (history / "journal.json").read_bytes()
        return StoredPackageSnapshot(
            current_generation=generation_id,
            generation_files=generation_files,
            journal=journal,
            retained_generation_files=retained_generation_files,
        )

    def commit(
        self, publication: PackageCommit, *, expected_generation: str | None
    ) -> None:
        try:
            _validate_generation_payloads(
                publication.generation_id, publication.generation_files
            )
            self._validate_journal_tip(publication.journal, publication.generation_id)
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
            if not self._recover_and_validate_history():
                raise PackageIntegrityError(
                    "package history cannot be proven safe for publication"
                )
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
            current_path = self._package / "CURRENT"
            if current_path.is_symlink() or journal_path.is_symlink():
                return None
            current = current_path.read_text(encoding="utf-8").strip()
            journal = _json_object(journal_path.read_bytes())
            entries = journal.get("entries")
            if not isinstance(entries, list) or not entries:
                return None

            published: set[str] = set()
            previous: str | None = None
            for entry_value in entries:
                if not isinstance(entry_value, dict):
                    return None
                generation_id = entry_value.get("generation_after")
                if not isinstance(generation_id, str) or generation_id in published:
                    return None
                if entry_value.get("generation_before") != previous:
                    return None
                generation_path = self._package / "generations" / generation_id
                generation_files = _read_generation(generation_path)
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
            _remove_artifact(artifact)
        _sync_directory(staging)

        journal = history / "journal.json"
        journal_tmp = history / ".journal.tmp"
        published = self._published_generation_ids(journal)
        if published is None and journal_tmp.is_file() and not journal_tmp.is_symlink():
            recovered = self._published_generation_ids(journal_tmp)
            if recovered is not None:
                os.replace(journal_tmp, journal)
                _sync_directory(journal.parent)
                published = recovered

        if published is None:
            return False

        for artifact in generations.iterdir():
            if artifact.name not in published:
                _remove_artifact(artifact)
        _sync_directory(generations)

        for temporary in (self._package / ".CURRENT.tmp", journal_tmp):
            if temporary.exists() or temporary.is_symlink():
                _remove_artifact(temporary)
        return True

    @staticmethod
    def _stage_generation(publication: PackageCommit, destination: Path) -> None:
        destination.mkdir(mode=0o700)
        for filename, payload in publication.generation_files.items():
            _write_durable(destination / filename, payload)
        _sync_directory(destination)
        _validate_generation_payloads(
            publication.generation_id, _read_generation(destination)
        )

    def _publish_update(
        self, publication: PackageCommit, expected_generation: str
    ) -> None:
        current = (self._package / "CURRENT").read_text(encoding="utf-8").strip()
        if current != expected_generation:
            raise StaleGenerationError(current)

        staging = self._package / "staging"
        generations = self._package / "generations"
        staged_generation = staging / publication.generation_id
        try:
            self._stage_generation(publication, staged_generation)
            os.replace(staged_generation, generations / publication.generation_id)
            _sync_directory(generations)

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
            _sync_directory(self._package)
            os.replace(journal_tmp, self._package / "history" / "journal.json")
            _sync_directory(self._package / "history")
        finally:
            if staged_generation.exists():
                shutil.rmtree(staged_generation)

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
            for directory in (generations, staging, evidence_records, history):
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)

            _write_durable(temporary / "LOCK", b"")

            staged_generation = staging / publication.generation_id
            self._stage_generation(publication, staged_generation)

            os.replace(staged_generation, generations / publication.generation_id)
            _sync_directory(generations)
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
