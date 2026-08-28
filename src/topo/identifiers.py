from __future__ import annotations

import secrets
import threading
import time
import uuid

UUID7_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_lock = threading.Lock()
_last_millisecond = -1
_random_sequence = 0


def uuid7() -> str:
    """Return a lowercase, monotonically ordered RFC 9562 UUIDv7 string."""
    global _last_millisecond, _random_sequence

    with _lock:
        millisecond = time.time_ns() // 1_000_000
        if millisecond > _last_millisecond:
            _last_millisecond = millisecond
            _random_sequence = secrets.randbits(74)
        else:
            millisecond = _last_millisecond
            _random_sequence = (_random_sequence + 1) & ((1 << 74) - 1)
            if _random_sequence == 0:
                while millisecond <= _last_millisecond:
                    millisecond = time.time_ns() // 1_000_000
                _last_millisecond = millisecond
                _random_sequence = secrets.randbits(74)

        random_a = _random_sequence >> 62
        random_b = _random_sequence & ((1 << 62) - 1)
        value = (
            (millisecond << 80)
            | (0x7 << 76)
            | (random_a << 64)
            | (0b10 << 62)
            | random_b
        )
        return str(uuid.UUID(int=value))
