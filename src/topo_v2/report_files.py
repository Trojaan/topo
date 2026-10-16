"""Publish a private complete report, atomically and without replacement."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def publish_report(path: Path, payload: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # A same-filesystem hard link publishes the complete inode atomically.
        # Unlike replace(), it refuses any existing entry, including symlinks,
        # and cannot clobber a competing writer. Unsupported filesystems fail safe.
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
