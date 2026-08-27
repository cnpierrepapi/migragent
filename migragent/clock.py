"""One clock, so every stored timestamp has the same shape.

Every module used to carry its own `def _now(): return datetime.now(timezone.utc)
.isoformat(timespec="seconds")`. Fifteen copies of the same line is fifteen
chances for one of them to drift to local time or drop the timezone.
"""
from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """UTC, to the second, ISO 8601 with the offset. What every row stores."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def now() -> datetime:
    """The same instant as an aware datetime, for arithmetic before formatting."""
    return datetime.now(timezone.utc)
