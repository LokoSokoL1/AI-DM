"""Internal UTC clock and timestamp normalization helpers."""

from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """Return the current aware UTC time behind one isolated clock boundary."""

    return datetime.now(timezone.utc)


def canonical_utc_datetime(value: Any, label: str) -> datetime:
    """Validate an aware datetime and return its canonical UTC equivalent."""

    if not isinstance(value, datetime):
        raise ValueError(f"{label} must be a timezone-aware datetime.")

    try:
        offset = value.utcoffset()
    except Exception as error:
        raise ValueError(
            f"{label} must be a valid timezone-aware datetime."
        ) from error

    if offset is None:
        raise ValueError(f"{label} must be timezone-aware.")

    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(
            f"{label} must be a valid timezone-aware datetime."
        ) from error


def serialize_utc_datetime(value: datetime) -> str:
    """Serialize one canonical UTC datetime with an explicit ``Z`` suffix."""

    canonical = canonical_utc_datetime(value, "UTC timestamp")
    return canonical.isoformat(timespec="microseconds").replace("+00:00", "Z")
