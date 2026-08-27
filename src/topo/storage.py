from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from topo.errors import StaleGenerationError


@dataclass(frozen=True)
class StoredPackageSnapshot:
    current_generation: str
    generation_files: dict[str, bytes]
    journal: bytes


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


class FileSystemStorageAdapter:
    """Read and atomically publish opaque package bytes on the local filesystem."""

    def __init__(self, package: Path) -> None:
        self._package = package

    def load(self) -> StoredPackageSnapshot | None:
        if not self._package.exists():
            return None

        generation_id = (self._package / "CURRENT").read_text(encoding="utf-8").strip()
        generation = self._package / "generations" / generation_id
        generation_files: dict[str, bytes] = {}
        for path in generation.iterdir():
            if not path.is_file():
                raise IsADirectoryError(str(path))
            generation_files[path.name] = path.read_bytes()
        return StoredPackageSnapshot(
            current_generation=generation_id,
            generation_files=generation_files,
            journal=(self._package / "history" / "journal.json").read_bytes(),
        )

    def commit(
        self, publication: PackageCommit, *, expected_generation: str | None
    ) -> None:
        if expected_generation is None:
            self._publish_initial(publication)
            return
        with self._exclusive_lock():
            self._publish_update(publication, expected_generation)

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        lock_path = self._package / "LOCK"
        with lock_path.open("a+b") as stream:
            os.chmod(lock_path, 0o600)
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _publish_update(
        self, publication: PackageCommit, expected_generation: str
    ) -> None:
        current = (self._package / "CURRENT").read_text(encoding="utf-8").strip()
        if current != expected_generation:
            raise StaleGenerationError(current)

        staging = self._package / "staging"
        generations = self._package / "generations"
        staged_generation = staging / publication.generation_id
        staged_generation.mkdir(mode=0o700)
        try:
            for filename, payload in publication.generation_files.items():
                _write_durable(staged_generation / filename, payload)
            _sync_directory(staged_generation)
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

            staged_generation = staging / publication.generation_id
            staged_generation.mkdir(mode=0o700)
            for filename, payload in publication.generation_files.items():
                _write_durable(staged_generation / filename, payload)
            _sync_directory(staged_generation)

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
