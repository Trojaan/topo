from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, cast

from topo_v2.models import Context


@contextmanager
def write_lock(path: Path) -> Iterator[None]:
    """A sidecar lock survives replacement of the context inode."""
    with path.with_name(path.name + ".lock").open("a+b") as handle:
        _lock(handle)
        try:
            yield
        finally:
            _unlock(handle)


def _lock(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        cast(Any, msvcrt).locking(handle.fileno(), cast(Any, msvcrt).LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        cast(Any, msvcrt).locking(handle.fileno(), cast(Any, msvcrt).LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read(path: Path) -> tuple[bytes, Context]:
    raw = path.read_bytes()
    return raw, Context.model_validate_json(raw)


def save(path: Path, context: Context) -> None:
    """Validate and flush a private sibling before atomic replacement."""
    context = Context.model_validate(context.model_dump())
    payload = context.model_dump_json(indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
